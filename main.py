import datetime
import logging
import os
import random
import sched
import sys
import time

from cloudfoundry_client.client import CloudFoundryClient
import yaml

from notifications_utils.clients.statsd.statsd_client import StatsdClient


class App:
    def __init__(self, name, min_instance_count, max_instance_count, buffer_instances=0):
        self.name = name
        self.min_instance_count = min_instance_count
        self.max_instance_count = max_instance_count
        self.buffer_instances = buffer_instances


class ScheduledJobApp(App):
    def __init__(self, name, items_per_instance, min_instance_count, max_instance_count):
        super().__init__(name, min_instance_count, max_instance_count)
        self.items_per_instance = items_per_instance


class AutoScaler:
    def __init__(self, sqs_apps, elb_apps, scheduled_job_apps):
        self.scheduled_job_apps = scheduled_job_apps

        self.schedule_interval = int(os.environ['SCHEDULE_INTERVAL']) + 0.0
        self.scheduled_scale_factor = float(os.environ['SCHEDULED_SCALE_FACTOR'])
        self.cooldown_seconds_after_scale_up = int(os.environ['COOLDOWN_SECONDS_AFTER_SCALE_UP'])
        self.cooldown_seconds_after_scale_down = int(os.environ['COOLDOWN_SECONDS_AFTER_SCALE_DOWN'])
        self.schedule_delay = random.random() * self.schedule_interval
        self.scheduler = sched.scheduler(time.time, time.sleep)

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
        self.load_schedule()

    def load_schedule(self):
        self.autoscaler_schedule = {}
        try:
            autoscaler_schedule = None
            with open("schedule.yml") as f:
                autoscaler_schedule = yaml.safe_load(f)
        except Exception as e:
            msg = "Could not load schedule: {}".format(str(e))
            logging.error(msg)
        else:
            self.autoscaler_schedule = autoscaler_schedule

    def should_scale_on_schedule(self, app_name):
        if app_name not in self.autoscaler_schedule:
            return False

        now = datetime.datetime.now()
        week_part = "workdays" if now.weekday() in range(5) else "weekends"  # Monday = 0, sunday = 6

        if week_part not in self.autoscaler_schedule[app_name]:
            return False

        for time_range_string in self.autoscaler_schedule[app_name][week_part]:
            # convert the time range string to time objects
            start, end = [datetime.datetime.strptime(i, '%H:%M').time() for i in time_range_string.split('-')]

            if datetime.datetime.combine(now, start) <= now <= datetime.datetime.combine(now, end):
                return True

        return False

    def get_cloudfoundry_client(self):
        if self.cf_client is None:
            proxy = dict(http=os.environ.get('HTTP_PROXY', ''), https=os.environ.get('HTTPS_PROXY', ''))
            cf_client = CloudFoundryClient(self.cf_api_url, proxy=proxy)
            try:
                cf_client.init_with_user_credentials(self.cf_username, self.cf_password)
                self.cf_client = cf_client
            except BaseException as e:
                msg = 'Failed to authenticate: {}, waiting 5 minutes and exiting'.format(str(e))
                logging.error(msg)
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
                msg = 'Failed to get stats for app {}: {}'.format(app['entity']['name'], str(e))
                logging.error(msg)
                self.reset_cloudfoundry_client()

        return instances

    def scale_paas_apps(self, app, paas_app, current_instance_count, desired_instance_count):
        scheduled_desired_instance_count = 0
        if self.should_scale_on_schedule(app.name):

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
            msg = 'Failed to scale {}: {}'.format(app.name, str(e))
            logging.error(msg)

    def recent_scale(self, app_name, last_scale, timeout):
        # if we redeployed the app and we lost the last scale time
        if not last_scale.get(app_name):
            last_scale[app_name] = datetime.datetime.now()

        return last_scale[app_name] > datetime.datetime.now() - datetime.timedelta(seconds=timeout)

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
max_instance_count_medium = int(os.environ['CF_MAX_INSTANCE_COUNT_MEDIUM'])
max_instance_count_low = int(os.environ['CF_MAX_INSTANCE_COUNT_LOW'])
min_instance_count_high = int(os.environ['CF_MIN_INSTANCE_COUNT_HIGH'])
min_instance_count_low = int(os.environ['CF_MIN_INSTANCE_COUNT_LOW'])
buffer_instances = int(os.environ['BUFFER_INSTANCES'])

sqs_apps = []
sqs_apps.append(SQSApp('notify-delivery-worker-database', ['database-tasks'], 250, min_instance_count_low, max_instance_count_high))
sqs_apps.append(SQSApp('notify-delivery-worker', ['notify-internal-tasks', 'retry-tasks', 'job-tasks'], 250, min_instance_count_low, max_instance_count_low))
sqs_apps.append(SQSApp('notify-delivery-worker-sender', ['send-sms-tasks', 'send-email-tasks'], 250, min_instance_count_high, max_instance_count_high))
sqs_apps.append(SQSApp('notify-delivery-worker-research', ['research-mode-tasks'], 250, min_instance_count_low, max_instance_count_low))
sqs_apps.append(SQSApp('notify-delivery-worker-priority', ['priority-tasks'], 250, min_instance_count_low, max_instance_count_low))
sqs_apps.append(SQSApp('notify-delivery-worker-periodic', ['periodic-tasks', 'statistics-tasks'], 250, min_instance_count_low, max_instance_count_low))
sqs_apps.append(SQSApp('notify-delivery-worker-receipts', ['ses-callbacks'], 250, min_instance_count_low, max_instance_count_v_high))
sqs_apps.append(SQSApp('notify-template-preview', ['create-letters-pdf-tasks'], 10, min_instance_count_low, max_instance_count_medium))

elb_apps = []
elb_apps.append(ELBApp('notify-api', 'notify-paas-proxy', 2000, min_instance_count_high, max_instance_count_high, buffer_instances))

scheduled_job_apps = []
scheduled_job_apps.append(ScheduledJobApp('notify-delivery-worker-database', 250, min_instance_count_low, max_instance_count_high))
scheduled_job_apps.append(ScheduledJobApp('notify-delivery-worker', 250, min_instance_count_low, max_instance_count_low))
scheduled_job_apps.append(ScheduledJobApp('notify-delivery-worker-sender', 250, min_instance_count_high, max_instance_count_high))
scheduled_job_apps.append(ScheduledJobApp('notify-delivery-worker-research', 250, min_instance_count_low, max_instance_count_low))
scheduled_job_apps.append(ScheduledJobApp('notify-delivery-worker-priority', 250, min_instance_count_low, max_instance_count_low))
scheduled_job_apps.append(ScheduledJobApp('notify-delivery-worker-periodic', 250, min_instance_count_low, max_instance_count_low))
scheduled_job_apps.append(ScheduledJobApp('notify-delivery-worker-receipts', 250, min_instance_count_low, max_instance_count_v_high))
scheduled_job_apps.append(ScheduledJobApp('notify-template-preview', 10, min_instance_count_low, max_instance_count_medium))

logging.basicConfig(
    level=logging.WARNING,
    handlers=[
        logging.FileHandler('/home/vcap/logs/app.log'),
        logging.StreamHandler(sys.stdout),
    ])
autoscaler = AutoScaler(sqs_apps, elb_apps, scheduled_job_apps)
autoscaler.run()
