import os
import boto3
import base64
import math
import sched
import time
import random
from cloudfoundry_client.client import CloudFoundryClient

class App:
    def __init__(self, name, queues, messages_per_instance, min_instance_count, max_instance_count):
        self.name = name
        self.queues = queues
        self.messages_per_instance = messages_per_instance
        self.min_instance_count = min_instance_count
        self.max_instance_count = max_instance_count

class AutoScaler:
    def __init__(self, apps):
        self.apps = apps

        self.schedule_interval = int(os.environ['SCHEDULE_INTERVAL']) + 0.0
        self.schedule_delay = random.random() * self.schedule_interval
        self.scheduler = sched.scheduler(time.time, time.sleep)

        self.aws_region = os.environ['AWS_REGION']
        self.aws_account_id = boto3.client('sts', region_name=self.aws_region).get_caller_identity()['Account']

        self.sqs_client = boto3.client('sqs', region_name=self.aws_region)
        self.sqs_queue_prefix = os.environ['SQS_QUEUE_PREFIX']

        self.cf_username = os.environ['CF_USERNAME']
        self.cf_password = os.environ['CF_PASSWORD']
        self.cf_api_url = os.environ['CF_API_URL']
        self.cf_org = os.environ['CF_ORG']
        self.cf_space = os.environ['CF_SPACE']
        self.cf_client = None

    def get_cloudfoundry_client(self):
        if self.cf_client is None:
            proxy = dict(http=os.environ.get('HTTP_PROXY', ''), https=os.environ.get('HTTPS_PROXY', ''))
            cf_client = CloudFoundryClient(self.cf_api_url, proxy=proxy)
            try:
                cf_client.init_with_user_credentials(self.cf_username, self.cf_password)
                self.cf_client = cf_client
            except BaseException as e:
                print('Failed to authenticate: {}, waiting 5 minutes and exiting'.format(str(e)))
                # The sleep is added to avoid automatically banning the user for too many failed login attempts
                time.sleep(5 * 60)

        return self.cf_client

    def reset_cloudfoundry_client(self):
        self.cf_client = None

    def get_paas_apps(self):
        instances = {}

        cf_client = self.get_cloudfoundry_client()
        if cf_client is not None:
            try:
                for organization in self.cf_client.organizations:
                    if organization['entity']['name'] != self.cf_org:
                        continue
                    for space in organization.spaces():
                        if space['entity']['name'] != self.cf_space:
                            continue
                        for app in space.apps():
                            instances[app['entity']['name']] = {
                                'name': app['entity']['name'],
                                'guid': app['metadata']['guid'],
                                'instances': app['entity']['instances']
                            }
            except BaseException as e:
                print('Failed to get stats for app {}: {}'.format(app['entity']['name'], str(e)))
                self.reset_cloudfoundry_client()

        return instances

    def get_sqs_url(self, name):
        return "https://sqs.{}.amazonaws.com/{}/{}{}".format(
            self.aws_region, self.aws_account_id, self.sqs_queue_prefix, name)

    def get_sqs_message_count(self, name):
        response = self.sqs_client.get_queue_attributes(
            QueueUrl=self.get_sqs_url("db-email"),
            AttributeNames=['ApproximateNumberOfMessages'])
        result = int(response['Attributes']['ApproximateNumberOfMessages'])
        print('Messages in {}: {}'.format(name, result))
        return result

    def get_highest_message_count(self, queues):
        result = 0
        for queue in queues:
            result = max(result, self.get_sqs_message_count(queue))
        return result

    def scale_app(self, app, paas_app):
        print('Processing {}'.format(app.name))
        highest_message_count = self.get_highest_message_count(app.queues)
        print('Highest message count: {}'.format(highest_message_count))
        desired_instance_count = int(max(app.min_instance_count, math.ceil(highest_message_count / float(app.messages_per_instance))))
        print('Current/desired instance count: {}/{}'.format(paas_app['instances'], desired_instance_count))

        if paas_app['instances'] != desired_instance_count:
            print('Scaling {} from {} to {}'.format(app.name, paas_app['instances'], desired_instance_count))
            try:
                self.cf_client.apps._update(paas_app['guid'], {'instances': desired_instance_count})
            except BaseException as e:
                print('Failed to scale {}: {}'.format(app.name, str(e)))

    def schedule(self):
        current_time = time.time()
        run_at = current_time + self.schedule_interval - ((current_time - self.schedule_delay) % self.schedule_interval)
        self.scheduler.enterabs(run_at, 1, self.run_task)

    def run_task(self):
        paas_apps = self.get_paas_apps()

        for app in self.apps:
            if not app.name in paas_apps:
                print("Application {} does not exist".format(app.name))
                continue
            self.scale_app(app, paas_apps[app.name])

        self.schedule()

    def run(self):
        print('API endpoint:   {}'.format(self.cf_api_url))
        print('User:           {}'.format(self.cf_username))
        print('Org:            {}'.format(self.cf_org))
        print('Space:          {}'.format(self.cf_space))

        self.schedule()
        while True:
            self.scheduler.run()

min_instance_count = int(os.environ['CF_MIN_INSTANCE_COUNT'])

apps = []
apps.append(App('notify-delivery-worker-database', ['db-sms','db-email','db-letter'], 2000, min_instance_count, 20))
apps.append(App('notify-delivery-worker', ['send-sms','send-email'], 2000, min_instance_count, 20))
autoscaler = AutoScaler(apps)
autoscaler.run()
