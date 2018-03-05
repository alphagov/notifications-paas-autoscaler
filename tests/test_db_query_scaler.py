from app.scheduled_jobs_scaler import ScheduledJobsScaler


class TestDbQueryScaler:
    def test_init_assigns_basic_values(self):
        input_attrs = {
            'min_instances': 1,
            'max_instances': 2,
            'threshold': 1500,
            'extra_field_1': 'some_value'
        }
        scheduled_job_scaler = ScheduledJobsScaler(**input_attrs)

        assert scheduled_job_scaler.min_instances == input_attrs['min_instances']
        assert scheduled_job_scaler.max_instances == input_attrs['max_instances']
        assert scheduled_job_scaler.threshold == input_attrs['threshold']
        assert scheduled_job_scaler.query == """
        SELECT COALESCE(SUM(notification_count), 0)
        FROM jobs
        WHERE scheduled_for - current_timestamp < interval '1 minute' AND
        job_status = 'scheduled';
        """
