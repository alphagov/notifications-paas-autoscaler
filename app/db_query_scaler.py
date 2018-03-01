from app.base_scalers import BaseScaler


class DbQueryScaler(BaseScaler):
    scheduled_job_interval = '1 minute'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        query = """
        SELECT COALESCE(SUM(notification_count), 0)
        FROM jobs
        WHERE scheduled_for - current_timestamp < interval '{}' AND
        job_status = 'scheduled';
        """
        self.query = query.format(self.scheduled_job_interval)

    def estimate_instance_count(self):
        pass
