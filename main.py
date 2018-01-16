import boto3
import datetime
import json
import math
import os
import psycopg2
import random
import sched
import time

from cloudfoundry_client.client import CloudFoundryClient

from notifications_utils.clients.statsd.statsd_client import StatsdClient


class App:
    def __init__(self, name, min_instance_count, max_instance_count, buffer_instances=0):
        self.name = name
        self.min_instance_count = min_instance_count
        self.max_instance_count = max_instance_count
        self.buffer_instances = buffer_instances


class SQSApp(App):
    def __init__(self, name, queues, messages_per_instance, min_instance_count, max_instance_count):
        super().__init__(name, min_instance_count, max_instance_count)
        self.queues = queues
        self.messages_per_instance = messages_per_instance


class ELBApp(App):
    def __init__(self, name, load_balancer_name, request_per_instance, min_instance_count,
                 max_instance_count, buffer_instances):
        super().__init__(name, min_instance_count, max_instance_count, buffer_instances)
        self.load_balancer_name = load_balancer_name
        self.request_per_instance = request_per_instance


class ScheduledJobApp(App):
    def __init__(self, name, items_per_instance, min_instance_count, max_instance_count):
        super().__init__(name, min_instance_count, max_instance_count)
        self.items_per_instance = items_per_instance


class AutoScaler:
    def __init__(self, sqs_apps, elb_apps, scheduled_job_apps):
        self.sqs_apps = sqs_apps
        self.elb_apps = elb_apps
        self.scheduled_job_apps = scheduled_job_apps

        self.schedule_interval = int(os.environ['SCHEDULE_INTERVAL']) + 0.0
        self.cooldown_seconds_after_scale_up = int(os.environ['COOLDOWN_SECONDS_AFTER_SCALE_UP'])
        self.cooldown_seconds_after_scale_down = int(os.environ['COOLDOWN_SECONDS_AFTER_SCALE_DOWN'])
        self.schedule_delay = random.random() * self.schedule_interval
        self.scheduler = sched.scheduler(time.time, time.sleep)

        self.aws_region = os.environ['AWS_REGION']
        self.aws_account_id = boto3.client('sts', region_name=self.aws_region).get_caller_identity()['Account']

        self.sqs_client = boto3.client('sqs', region_name=self.aws_region)
        self.sqs_queue_prefix = os.environ['SQS_QUEUE_PREFIX']

        self.cloudwatch_client = boto3.client('cloudwatch', region_name=self.aws_region)

        self.cf_username = os.environ['CF_USERNAME']
        self.cf_password = os.environ['CF_PASSWORD']
        self.cf_api_url = os.environ['CF_API_URL']
        self.cf_org = os.environ['CF_ORG']
        self.cf_space = os.environ['CF_SPACE']
        self.cf_client = None
        self.config = {}
        self.config.update({
            'STATSD_ENABLED': os.environ['STATSD_ENABLED'],
            'NOTIFY_ENVIRONMENT': os.environ['CF_SPACE'],
            'NOTIFY_APP_NAME': 'autoscaler',
            'STATSD_HOST': 'statsd.hostedgraphite.com',
            'STATSD_PORT': '8125',
            'STATSD_PREFIX': os.environ['STATSD_PREFIX']
        })
        self.statsd_client = StatsdClient()
        self.statsd_client.init_app(self)
        self.last_scale_up = {}
        self.last_scale_down = {}

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

    def get_sqs_queue_name(self, name):
        return "{}{}".format(self.sqs_queue_prefix, name)

    def get_sqs_queue_url(self, name):
        return "https://sqs.{}.amazonaws.com/{}/{}".format(
            self.aws_region, self.aws_account_id, name)

    def get_sqs_message_count(self, name):
        response = self.sqs_client.get_queue_attributes(
            QueueUrl=self.get_sqs_queue_url(name),
            AttributeNames=['ApproximateNumberOfMessages'])
        result = int(response['Attributes']['ApproximateNumberOfMessages'])
        print('Messages in {}: {}'.format(name, result))
        return result

    def get_message_count(self, queue):
        queue_name = self.get_sqs_queue_name(queue)
        message_count = self.get_sqs_message_count(queue_name)
        self.statsd_client.incr("{}.queue-length".format(queue_name), message_count)
        return message_count

    def get_total_message_count(self, queues):
        return sum(self.get_message_count(queue) for queue in queues)

    def scale_sqs_app(self, app, paas_app):
        print('Processing {}'.format(app.name))
        total_message_count = self.get_total_message_count(app.queues)
        print('Total message count: {}'.format(total_message_count))
        desired_instance_count = int(math.ceil(total_message_count / float(app.messages_per_instance)))
        self.scale_paas_apps(app, paas_app, paas_app['instances'], desired_instance_count)

    def get_load_balancer_request_counts(self, load_balancer_name):
        start_time = datetime.datetime.now() - datetime.timedelta(minutes=5)
        end_time = datetime.datetime.now()
        result = self.cloudwatch_client.get_metric_statistics(
            Namespace='AWS/ELB',
            MetricName='RequestCount',
            Dimensions=[
                {
                    'Name': 'LoadBalancerName',
                    'Value': load_balancer_name
                },
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=60,
            Statistics=['Sum'],
            Unit='Count'
        )
        datapoints = result['Datapoints']
        datapoints = sorted(datapoints, key=lambda x: x['Timestamp'])
        return [row['Sum'] for row in datapoints]

    def scale_elb_app(self, app, paas_app):
        print('Processing {}'.format(app.name))
        request_counts = self.get_load_balancer_request_counts(app.load_balancer_name)
        if len(request_counts) == 0:
            request_counts = [0]
        print('Request counts (5 min): {}'.format(request_counts))

        # We make sure we keep the highest instance count for 5 minutes
        highest_request_count = max(request_counts)
        print('Highest request count (5 min): {}'.format(highest_request_count))

        desired_instance_count = int(math.ceil(highest_request_count / float(app.request_per_instance)))
        self.statsd_client.gauge("{}.request-count".format(app.name), highest_request_count)
        self.scale_paas_apps(app, paas_app, paas_app['instances'], desired_instance_count)

    def get_scheduled_jobs_items_count(self):
        interval = '1 minute'
        db_uri = json.loads(os.environ['VCAP_SERVICES'])['postgres'][0]['credentials']['uri']
        with psycopg2.connect(db_uri) as conn:
            with conn.cursor() as cursor:
                # Use coalesce to avoid null values when nothing is scheduled
                # https://stackoverflow.com/a/6530371/1477072
                q = ("SELECT COALESCE(SUM(notification_count), 0) "
                     "FROM jobs "
                     "WHERE scheduled_for - current_timestamp < interval '{}' AND "
                     "job_status = 'scheduled';".format(interval))

                cursor.execute(q)
                items_count = cursor.fetchone()[0]

                print("Items scheduled in the next {}: {}".format(
                      interval, items_count))

                return items_count

    def scale_schedule_job_app(self, app, paas_app, scheduled_items):
        # use only a third of the items because not everything gets put on the queue at once
        scale_items = scheduled_items / 3
        desired_instance_count = int(math.ceil(scale_items / float(app.items_per_instance)))
        self.scale_paas_apps(app, paas_app, paas_app['instances'], desired_instance_count)

    def scale_paas_apps(self, app, paas_app, current_instance_count, desired_instance_count):
        desired_instance_count = min(app.max_instance_count, desired_instance_count)
        desired_instance_count = max(app.min_instance_count, desired_instance_count)

        print('Desired instance count: {} ({} + {})'.format(desired_instance_count + app.buffer_instances, desired_instance_count, app.buffer_instances))
        desired_instance_count += app.buffer_instances

        if current_instance_count == desired_instance_count:
            self.statsd_client.gauge("{}.instance-count".format(app.name), current_instance_count)
            return

        is_scale_up = True if desired_instance_count > current_instance_count else False
        is_scale_down = not is_scale_up  # for readability

        if is_scale_up:
            self.last_scale_up[app.name] = datetime.datetime.now()

        if is_scale_down:
            if self.recent_scale_up(app.name):
                print("Skipping scale down due to recent scale up event")
                return

            if self.recent_scale_down(app.name):
                print("Skipping scale down due to a recent scale down event")
                return

            # Make sure we don't remove more than 1 instance at a time, and only downscale when under 1000 messages
            if current_instance_count - desired_instance_count >= 2:
                desired_instance_count = current_instance_count - 1
                self.last_scale_down[app.name] = datetime.datetime.now()

        print('Current/desired instance count: {}/{}'.format(current_instance_count, desired_instance_count))
        print('Scaling {} from {} to {}'.format(app.name, current_instance_count, desired_instance_count))
        self.statsd_client.gauge("{}.instance-count".format(app.name), desired_instance_count)
        try:
            self.cf_client.apps._update(paas_app['guid'], {'instances': desired_instance_count})
        except BaseException as e:
            print('Failed to scale {}: {}'.format(app.name, str(e)))

    def recent_scale_up(self, app_name):
        # if we redeployed the app and we lost the last scale up time
        if not self.last_scale_up.get(app_name):
            self.last_scale_up[app_name] = datetime.datetime.now()

        return (self.last_scale_up[app_name] + datetime.timedelta(seconds=self.COOLDOWN_SECONDS_AFTER_SCALE_UP) >
                datetime.datetime.now())

    def recent_scale_down(self, app_name):
        # if we redeployed the app and we lost the last scale down time
        if not self.last_scale_down.get(app_name):
            self.last_scale_down[app_name] = datetime.datetime.now()

        return (self.last_scale_down[app_name] + datetime.timedelta(seconds=self.COOLDOWN_SECONDS_AFTER_SCALE_DOWN) >
                datetime.datetime.now())

    def schedule(self):
        current_time = time.time()
        run_at = current_time + self.schedule_interval - ((current_time - self.schedule_delay) % self.schedule_interval)
        print('Next run time {}'.format(str(run_at)))
        self.scheduler.enterabs(run_at, 1, self.run_task)

    def run_task(self):
        paas_apps = self.get_paas_apps()

        for app in self.elb_apps:
            if app.name not in paas_apps:
                print("Application {} does not exist".format(app.name))
                continue
            self.scale_elb_app(app, paas_apps[app.name])

        scheduled_items = self.get_scheduled_jobs_items_count()
        for app in self.scheduled_job_apps:
            if app.name not in paas_apps:
                print("Application {} does not exist".format(app.name))
                continue
            self.scale_schedule_job_app(app, paas_apps[app.name], scheduled_items)

        for app in self.sqs_apps:
            if app.name not in paas_apps:
                print("Application {} does not exist".format(app.name))
                continue
            self.scale_sqs_app(app, paas_apps[app.name])

        self.schedule()

    def run(self):
        print('API endpoint:   {}'.format(self.cf_api_url))
        print('User:           {}'.format(self.cf_username))
        print('Org:            {}'.format(self.cf_org))
        print('Space:          {}'.format(self.cf_space))

        self.schedule()
        while True:
            self.scheduler.run()


max_instance_count_v_high = int(os.environ['CF_MAX_INSTANCE_COUNT_V_HIGH'])
max_instance_count_high = int(os.environ['CF_MAX_INSTANCE_COUNT_HIGH'])
max_instance_count_low = int(os.environ['CF_MAX_INSTANCE_COUNT_LOW'])
min_instance_count_high = int(os.environ['CF_MIN_INSTANCE_COUNT_HIGH'])
min_instance_count_low = int(os.environ['CF_MIN_INSTANCE_COUNT_LOW'])
buffer_instances = int(os.environ['CF_BUFFER_INSTANCES'])

sqs_apps = []
sqs_apps.append(SQSApp('notify-delivery-worker-database', ['database-tasks'], 250, min_instance_count_low, max_instance_count_high))
sqs_apps.append(SQSApp('notify-delivery-worker', ['notify-internal-tasks', 'retry-tasks', 'job-tasks'], 250, min_instance_count_low, max_instance_count_low))
sqs_apps.append(SQSApp('notify-delivery-worker-sender', ['send-sms-tasks', 'send-email-tasks'], 250, min_instance_count_high, max_instance_count_high))
sqs_apps.append(SQSApp('notify-delivery-worker-research', ['research-mode-tasks'], 250, min_instance_count_low, max_instance_count_low))
sqs_apps.append(SQSApp('notify-delivery-worker-priority', ['priority-tasks'], 250, min_instance_count_low, max_instance_count_low))
sqs_apps.append(SQSApp('notify-delivery-worker-periodic', ['periodic-tasks', 'statistics-tasks'], 250, min_instance_count_low, max_instance_count_low))
sqs_apps.append(SQSApp('notify-delivery-worker-receipts', ['ses-callbacks'], 250, min_instance_count_low, max_instance_count_v_high))

elb_apps = []
elb_apps.append(ELBApp('notify-api', 'notify-paas-proxy', 1500, min_instance_count_high, max_instance_count_high, buffer_instances))

scheduled_job_apps = []
scheduled_job_apps.append(ScheduledJobApp('notify-delivery-worker-database', 250, min_instance_count_low, max_instance_count_high))
scheduled_job_apps.append(ScheduledJobApp('notify-delivery-worker', 250, min_instance_count_low, max_instance_count_low))
scheduled_job_apps.append(ScheduledJobApp('notify-delivery-worker-sender', 250, min_instance_count_high, max_instance_count_high))
scheduled_job_apps.append(ScheduledJobApp('notify-delivery-worker-research', 250, min_instance_count_low, max_instance_count_low))
scheduled_job_apps.append(ScheduledJobApp('notify-delivery-worker-priority', 250, min_instance_count_low, max_instance_count_low))
scheduled_job_apps.append(ScheduledJobApp('notify-delivery-worker-periodic', 250, min_instance_count_low, max_instance_count_low))
scheduled_job_apps.append(ScheduledJobApp('notify-delivery-worker-receipts', 250, min_instance_count_low, max_instance_count_v_high))

autoscaler = AutoScaler(sqs_apps, elb_apps, scheduled_job_apps)
autoscaler.run()
