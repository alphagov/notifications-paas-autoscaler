import math

from app.base_scalers import DbQueryScaler


class ScheduledJobsScaler(DbQueryScaler):
    scheduled_job_interval = '1 minute'

    def __init__(self, **kwargs):
        # Use coalesce to avoid null values when nothing is scheduled
        # https://stackoverflow.com/a/6530371/1477072
        query = """
        SELECT COALESCE(SUM(notification_count), 0)
        FROM jobs
        WHERE scheduled_for - current_timestamp < interval '{}' AND
        job_status = 'scheduled';
        """
        self.query = query.format(self.scheduled_job_interval)

        super().__init__(**kwargs)

    def estimate_instance_count(self):
        scheduled_items = self.run_query()
        # use only a third of the items because not everything gets put on the queue at once
        scale_items = scheduled_items / 3
        desired_instance_count = int(math.ceil(scale_items / float(self.threshold)))
        return self.normalize_desired_instance_count(desired_instance_count)
