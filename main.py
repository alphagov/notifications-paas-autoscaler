import logging
import os
import random
import sched
import sys
import time

from notifications_utils.clients.statsd.statsd_client import StatsdClient


class App:
    def __init__(self, name, min_instance_count, max_instance_count, buffer_instances=0):
        self.name = name
        self.min_instance_count = min_instance_count
        self.max_instance_count = max_instance_count
        self.buffer_instances = buffer_instances


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
