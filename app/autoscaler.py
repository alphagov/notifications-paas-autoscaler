import datetime
import logging
import os
import sched
import time

from cloudfoundry_client.errors import InvalidStatusCode
from redis import Redis

from app.app import App
from app.config import config
from app.exceptions import CannotLoadConfig
from app.paas_client import PaasClient
from app.utils import get_statsd_client


class Autoscaler:
    def __init__(self):
        self.last_scale_up = {}
        self.last_scale_down = {}
        self.scheduler = sched.scheduler(self._now, time.sleep)
        self.schedule_interval_seconds = config['GENERAL']['SCHEDULE_INTERVAL_SECONDS']
        self.cooldown_seconds_after_scale_up = config['GENERAL']['COOLDOWN_SECONDS_AFTER_SCALE_UP']
        self.cooldown_seconds_after_scale_down = config['GENERAL']['COOLDOWN_SECONDS_AFTER_SCALE_DOWN']
        self.statsd_client = get_statsd_client()
        self.paas_client = PaasClient()
        self.redis_client = Redis.from_url(os.environ['REDIS_URL'])
        self._load_autoscaler_apps()

    def _load_autoscaler_apps(self):
        apps = []
        for app in config['APPS']:
            try:
                apps.append(App(**app))
            except Exception as e:
                msg = "Could not load {}: The error was: {}".format(app, e)
                logging.critical(msg, exc_info=True)
                raise CannotLoadConfig(msg)
        self.autoscaler_apps = apps

    def _now(self):
        return datetime.datetime.utcnow().timestamp()

    def _schedule(self):
        current_time = self._now()
        run_at = current_time + self.schedule_interval_seconds
        logging.debug('Next run time {}'.format(str(run_at)))

        # Copying from docs: https://docs.python.org/3/library/sched.html#sched.scheduler.run
        #
        # If a sequence of events takes longer to run than the time available before the next event,
        # the scheduler will simply fall behind, no events will be dropped.
        self.scheduler.enterabs(run_at, 1, self.run_task)

    def run(self):
        print('API endpoint:   {}'.format(self.paas_client.api_url))
        print('User:           {}'.format(self.paas_client.username))
        print('Org:            {}'.format(self.paas_client.org))
        print('Space:          {}'.format(self.paas_client.space))

        self._schedule()
        while True:
            self.scheduler.run()

    def run_task(self):
        paas_apps = self.paas_client.get_paas_apps()

        for app in self.autoscaler_apps:
            if app.name not in paas_apps:
                logging.warning("Application {} does not exist, check the config and ensure it is deployed".format(
                    app.name
                ))
                continue
            app.refresh_cf_info(paas_apps[app.name])
            self.scale(app)

        self._schedule()

    def _do_scale(self, app, new_instance_count):
        try:
            self.paas_client.update(app.cf_attributes['guid'], new_instance_count)
        except InvalidStatusCode as e:
            if e.body.get('error_code') == 'CF-ScaleDisabledDuringDeployment':
                msg = 'Cannot scale during deployment {}'.format(app.name)
                logging.info(msg)
            else:
                msg = 'Failed to scale {}: {}'.format(app.name, str(e))
                logging.error(msg)

    def get_new_instance_count(self, current, desired, app_name):
        new_instance_count = current

        # scale down
        if desired < current:

            if self._recent_scale(app_name, 'last_scale_up', self.cooldown_seconds_after_scale_up):
                logging.info("Skipping scale down due to recent scale up event")
                return current

            if self._recent_scale(app_name, 'last_scale_down', self.cooldown_seconds_after_scale_down):
                logging.info("Skipping scale down due to a recent scale down event")
                return current

            self._set_last_scale('last_scale_down', app_name, self._now())
            new_instance_count = current - 1

        # scale up
        elif desired > current:
            self._set_last_scale('last_scale_up', app_name, self._now())
            new_instance_count = desired

        return new_instance_count

    def scale(self, app):
        app_name = app.name
        desired_instance_count = app.get_desired_instance_count()
        current_instance_count = app.cf_attributes['instances']

        new_instance_count = self.get_new_instance_count(current_instance_count, desired_instance_count, app_name)
        if current_instance_count != new_instance_count:
            logging.info('Scaling {} from {} to {}'.format(app.name, current_instance_count, new_instance_count))
            self._do_scale(app, new_instance_count)

        self.statsd_client.gauge("{}.instance-count".format(app_name), new_instance_count)

    def _recent_scale(self, app_name, redis_key, timeout):
        # if we redeployed autoscaler and we lost the last scale time
        now = self._now()

        try:
            last_scale = self.redis_client.hget(redis_key, app_name)
        except Exception as e:
            logging.warning("Could not retrieve data from redis for {}. Error was \
                    {}".format(app_name, e))
            last_scale = None

        if not last_scale:
            last_scale = now
            self._set_last_scale(redis_key, app_name, last_scale)
        else:
            last_scale = float(last_scale)

        return now < (last_scale + timeout)

    def _set_last_scale(self, key, app_name, timestamp):
        try:
            self.redis_client.hset(key, app_name, timestamp)
        except Exception as e:
            logging.warning("Could not set {} for {}. Error was \
                    {}".format(key, app_name, e))
