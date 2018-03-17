from unittest.mock import Mock

from app.scheduled_jobs_scaler import ScheduledJobsScaler


class TestScheduledJobsScaler:
    def test_init_assigns_basic_values(self):
        input_attrs = {
            'min_instances': 1,
            'max_instances': 2,
            'threshold': 1500,
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

    def test_get_desired_instance_count(self):
        input_attrs = {
            'min_instances': 1,
            'max_instances': 5,
            'threshold': 1500,
        }
        scheduled_job_scaler = ScheduledJobsScaler(**input_attrs)
        scheduled_job_scaler.run_query = Mock(return_value=10000)

        # 10k items * 0.3 = 3k => 2 instances
        assert scheduled_job_scaler.get_desired_instance_count() == 2
