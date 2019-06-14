import math

from app.base_scalers import DbQueryScaler


class ScheduledJobsScaler(DbQueryScaler):
    scheduled_job_lookahead = '1 minute'
    # use only a third of the items because not everything gets put on the queue at once
    scheduled_items_factor = 0.3

    def __init__(self, app_name, min_instances, max_instances, **kwargs):
        super().__init__(app_name, min_instances, max_instances)
        # Use coalesce to avoid null values when nothing is scheduled
        # https://stackoverflow.com/a/6530371/1477072
        query = """
        SELECT COALESCE(SUM(notification_count), 0)
        FROM jobs
        WHERE scheduled_for - current_timestamp < interval '{}' AND
        job_status = 'scheduled';
        """
        self.query = query.format(self.scheduled_job_lookahead)
        self.threshold = kwargs['threshold']

    def _get_desired_instance_count(self):
        scheduled_items = self.run_query()
        scale_items = scheduled_items * self.scheduled_items_factor
        desired_instance_count = int(math.ceil(scale_items / float(self.threshold)))
        return desired_instance_count
