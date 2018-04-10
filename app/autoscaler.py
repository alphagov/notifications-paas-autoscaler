import logging
import sched
import time

from app.cf import Cf


class Autoscaler:
    statsd_client = None

    def __init__(self):
        self.last_scale_up = {}
        self.last_scale_down = {}
        self.scheduler = sched.scheduler(self._now, time.sleep)
        self.cf = Cf()

    def _now(self):
        return time.time()

    def _schedule(self):
        current_time = time.time()
        run_at = current_time + self.schedule_interval - ((current_time - self.schedule_delay) % self.schedule_interval)
        print('Next run time {}'.format(str(run_at)))

        # Copying from docs: https://docs.python.org/3/library/sched.html#sched.scheduler.run
        #
        # If a sequence of events takes longer to run than the time available before the next event,
        # the scheduler will simply fall behind, no events will be dropped.
        self.scheduler.enterabs(run_at, 1, self.run_task)

    def run(self):
        print('API endpoint:   {}'.format(self.cf.api_url))
        print('User:           {}'.format(self.cf.username))
        print('Org:            {}'.format(self.cf.org))
        print('Space:          {}'.format(self.cf.space))

        self._schedule()
        while True:
            self.scheduler.run()

    def run_task(self):
        paas_apps = self.cf.get_paas_apps()

        for app in self.autoscaler_apps:
            if app.name not in paas_apps:
                print("Application {} does not exist".format(app.name))
                continue
            app.refresh_cf_info(paas_apps[app.name])
            self.scale(app)

        self._schedule()

    def scale(self, app):
        app_name = app.name
        desired_instance_count = app.get_desired_instance_count()
        current_instance_count = app.cf_attributes['instances']

        is_scale_up = True if desired_instance_count > current_instance_count else False

        if is_scale_up:
            self.last_scale_up[app_name] = self._now()

        if self._should_skip_scale(app_name, current_instance_count, desired_instance_count):
            self.statsd_client.gauge("{}.instance-count".format(app_name), current_instance_count)
            return

        # Make sure we don't remove more than 1 instance at a time
        if current_instance_count - desired_instance_count >= 2:
            desired_instance_count = current_instance_count - 1
            self.last_scale_down[app_name] = self._now()

        print('Scaling {} from {} to {}'.format(app_name, current_instance_count, desired_instance_count))
        self.statsd_client.gauge("{}.instance-count".format(app_name), desired_instance_count)
        try:
            self.cf.apps._update(app.cf_attributes['guid'], {'instances': desired_instance_count})
        except BaseException as e:
            msg = 'Failed to scale {}: {}'.format(app_name, str(e))
            logging.error(msg)

    def _should_skip_scale(self, app_name, current_instance_count, desired_instance_count):
        if current_instance_count == desired_instance_count:
            return True

        # we never block scaling up
        if desired_instance_count > current_instance_count:
            return False

        # the following are only checked before scaling down
        if self._recent_scale(app_name, self.last_scale_up, self.cooldown_seconds_after_scale_up):
            print("Skipping scale down due to recent scale up event")
            return True

        if self._recent_scale(app_name, self.last_scale_down, self.cooldown_seconds_after_scale_down):
            print("Skipping scale down due to a recent scale down event")
            return True

    def _recent_scale(self, app_name, last_scale, timeout):
        # if we redeployed the app and we lost the last scale time
        now = self._now()
        if not last_scale.get(app_name):
            last_scale[app_name] = now

        return last_scale[app_name] > now - timeout
