import logging
import sched
import time

# from cloudfoundry_client.client import CloudFoundryClient


class Autoscaler:
    statsd_client = None
    cf_client = None

    def __init__(self):
        self.last_scale_up = {}
        self.last_scale_down = {}
        self.scheduler = sched.scheduler(self._now, time.sleep)

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
        print('API endpoint:   {}'.format(self.cf_api_url))
        print('User:           {}'.format(self.cf_username))
        print('Org:            {}'.format(self.cf_org))
        print('Space:          {}'.format(self.cf_space))

        self._schedule()
        while True:
            self.scheduler.run()

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

        self._schedule()

    def scale_paas_apps(self, app_name, paas_app, current_instance_count, desired_instance_count):
        print('{}: Desired instance count: {}'.format(app_name, desired_instance_count))

        if current_instance_count == desired_instance_count:
            self.statsd_client.gauge("{}.instance-count".format(app_name), current_instance_count)
            return

        is_scale_up = True if desired_instance_count > current_instance_count else False
        is_scale_down = not is_scale_up  # for readability

        if is_scale_up:
            self.last_scale_up[app_name] = self._now()

        if is_scale_down:
            if self._recent_scale(app_name, self.last_scale_up, self.cooldown_seconds_after_scale_up):
                print("Skipping scale down due to recent scale up event")
                self.statsd_client.gauge("{}.instance-count".format(app_name), current_instance_count)
                return

            if self._recent_scale(app_name, self.last_scale_down, self.cooldown_seconds_after_scale_down):
                print("Skipping scale down due to a recent scale down event")
                self.statsd_client.gauge("{}.instance-count".format(app_name), current_instance_count)
                return

            # Make sure we don't remove more than 1 instance at a time
            if current_instance_count - desired_instance_count >= 2:
                desired_instance_count = current_instance_count - 1
                self.last_scale_down[app_name] = self._now()

        print('Current/desired instance count: {}/{}'.format(current_instance_count, desired_instance_count))
        print('Scaling {} from {} to {}'.format(app_name, current_instance_count, desired_instance_count))
        self.statsd_client.gauge("{}.instance-count".format(app_name), desired_instance_count)
        try:
            self.cf_client.apps._update(paas_app['guid'], {'instances': desired_instance_count})
        except BaseException as e:
            msg = 'Failed to scale {}: {}'.format(app_name, str(e))
            logging.error(msg)

    def _recent_scale(self, app_name, last_scale, timeout):
        # if we redeployed the app and we lost the last scale time
        now = self._now()
        if not last_scale.get(app_name):
            last_scale[app_name] = now

        return last_scale[app_name] > now - timeout
