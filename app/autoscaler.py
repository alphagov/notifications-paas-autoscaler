import datetime
import logging
import sched
import time

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
        self._load_autoscaler_apps()

    def _load_autoscaler_apps(self):
        apps = []
        for app in config['APPS']:
            try:
                apps.append(App(**app))
            except Exception as e:
                msg = "Could not load {}: The error was: {}".format(app, e)
                logging.critical(msg)
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
                logging.warning("Application {} does not exist, check the config and \
                        ensure it is deployed".format(app.name))
                continue
            app.refresh_cf_info(paas_apps[app.name])
            self.scale(app)

        self._schedule()

    def _do_scale(self, app, new_instance_count):
        try:
            self.paas_client.apps._update(app.cf_attributes['guid'], {'instances': new_instance_count})
        except BaseException as e:
            msg = 'Failed to scale {}: {}'.format(app.name, str(e))
            logging.error(msg)

    def get_new_instance_count(self, current, desired, app_name):
        new_instance_count = current

        # scale down
        if desired < current:
            if self._recent_scale(app_name, self.last_scale_up, self.cooldown_seconds_after_scale_up):
                logging.info("Skipping scale down due to recent scale up event")
                return current

            if self._recent_scale(app_name, self.last_scale_down, self.cooldown_seconds_after_scale_down):
                logging.info("Skipping scale down due to a recent scale down event")
                return current

            self.last_scale_down[app_name] = self._now()
            new_instance_count = current - 1

        # scale up
        elif desired > current:
            self.last_scale_down[app_name] = self._now()
            new_instance_count = desired

        return new_instance_count

    def scale(self, app):
        app_name = app.name
        desired_instance_count = app.get_desired_instance_count()
        current_instance_count = app.cf_attributes['instances']

        new_instance_count = self.get_new_instance_count(current_instance_count, desired_instance_count, app_name)
        self.statsd_client.gauge("{}.instance-count".format(app_name), new_instance_count)

        if current_instance_count != new_instance_count:
            logging.info('Scaling {} from {} to {}'.format(app.name, current_instance_count, new_instance_count))
            self._do_scale(app, new_instance_count)

    def _recent_scale(self, app_name, last_scale, timeout):
        # if we redeployed the app and we lost the last scale time
        now = self._now()
        if not last_scale.get(app_name):
            last_scale[app_name] = now

        return now < (last_scale[app_name] + timeout)
