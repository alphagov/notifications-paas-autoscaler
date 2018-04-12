import datetime

from unittest.mock import patch, Mock
import yaml

from app.autoscaler import Autoscaler
from app.elb_scaler import ElbScaler
from app.schedule_scaler import ScheduleScaler
from app.app import App


@patch('app.autoscaler.Cf')
@patch('app.autoscaler.get_statsd_client')
class TestAutoscaler:
    def test_scale_paas_app_same_instance_count(self, mock_get_statsd_client, mock_cf):
        app_name = 'app-name-1'
        app_guid = '11111-11111-11111111-1111'
        app = App(app_name, ['ElbScaler'])
        app.get_desired_instance_count = Mock(return_value=4)
        cf_info = {'name': app_name, 'instances': 4, 'guid': app_guid}
        app.refresh_cf_info(cf_info)

        autoscaler = Autoscaler()
        autoscaler.scale(app)
        mock_get_statsd_client.return_value.gauge.assert_called_once_with("{}.instance-count".format(app_name), 4)
        mock_cf.return_value.assert_not_called()

    def test_scale_paas_app_more_instances(self, mock_get_statsd_client, mock_cf):
        app_guid = '11111-11111-11111111-1111'
        app_name = 'app-name-1'
        app = App(app_name, ['ElbScaler'])
        app.get_desired_instance_count = Mock(return_value=6)
        cf_info = {'name': app_name, 'instances': 4, 'guid': app_guid}
        app.refresh_cf_info(cf_info)

        autoscaler = Autoscaler()
        autoscaler.scale(app)
        mock_get_statsd_client.return_value.gauge.assert_called_once_with("{}.instance-count".format(app_name), 6)
        mock_cf.return_value.apps._update.assert_called_once_with(app_guid, {'instances': 6})

    def test_scale_paas_app_much_fewer_instances(self, mock_get_statsd_client, mock_cf):
        app_guid = '11111-11111-11111111-1111'
        app_name = 'app-name-1'
        app = App(app_name, ['ElbScaler'])
        app.get_desired_instance_count = Mock(return_value=1)
        cf_info = {'name': app_name, 'instances': 4, 'guid': app_guid}
        app.refresh_cf_info(cf_info)

        autoscaler = Autoscaler()
        autoscaler.cooldown_seconds_after_scale_up = 300
        autoscaler.cooldown_seconds_after_scale_down = 60
        autoscaler.last_scale_up[app_name] = 1000
        autoscaler.last_scale_down[app_name] = 800
        autoscaler._now = Mock(return_value=1500)
        autoscaler.scale(app)
        mock_get_statsd_client.return_value.gauge.assert_called_once_with("{}.instance-count".format(app_name), 3)
        mock_cf.return_value.apps._update.assert_called_once_with(app_guid, {'instances': 3})

    def test_scale_paas_app_fewer_instances_recent_scale_up(self, mock_get_statsd_client, mock_cf):
        app_guid = '11111-11111-11111111-1111'
        app_name = 'app-name-1'
        app = App(app_name, ['ElbScaler'])
        app.get_desired_instance_count = Mock(return_value=3)
        cf_info = {'name': app_name, 'instances': 4, 'guid': app_guid}
        app.refresh_cf_info(cf_info)

        autoscaler = Autoscaler()
        autoscaler.cooldown_seconds_after_scale_up = 300
        autoscaler.cooldown_seconds_after_scale_down = 60
        autoscaler.last_scale_up[app_name] = 1000
        autoscaler.last_scale_down[app_name] = 800
        autoscaler._now = Mock(return_value=1200)
        autoscaler.scale(app)
        mock_get_statsd_client.return_value.gauge.assert_called_once_with("{}.instance-count".format(app_name), 4)
        mock_cf.return_value.assert_not_called()

    def test_scale_paas_app_fewer_instances_recent_scale_down(self, mock_get_statsd_client, mock_cf):
        app_guid = '11111-11111-11111111-1111'
        app_name = 'app-name-1'
        app = App(app_name, ['ElbScaler'])
        app.get_desired_instance_count = Mock(return_value=3)
        cf_info = {'name': app_name, 'instances': 4, 'guid': app_guid}
        app.refresh_cf_info(cf_info)

        autoscaler = Autoscaler()
        autoscaler.cooldown_seconds_after_scale_up = 300
        autoscaler.cooldown_seconds_after_scale_down = 60
        autoscaler.last_scale_up[app_name] = 1000
        autoscaler.last_scale_down[app_name] = 1400
        autoscaler._now = Mock(return_value=1430)
        autoscaler.scale(app)
        mock_get_statsd_client.return_value.gauge.assert_called_once_with("{}.instance-count".format(app_name), 4)
        mock_cf.return_value.assert_not_called()

    def test_scale_paas_app_fewer_instances_missing_recent_scale_information(self, mock_get_statsd_client, mock_cf):
        app_guid = '11111-11111-11111111-1111'
        app_name = 'app-name-1'
        app = App(app_name, ['ElbScaler'])
        app.get_desired_instance_count = Mock(return_value=3)
        cf_info = {'name': app_name, 'instances': 4, 'guid': app_guid}
        app.refresh_cf_info(cf_info)

        autoscaler = Autoscaler()
        autoscaler.cooldown_seconds_after_scale_up = 300
        autoscaler.cooldown_seconds_after_scale_down = 60
        autoscaler._now = Mock(return_value=1000)
        autoscaler.scale(app)
        mock_get_statsd_client.return_value.gauge.assert_called_once_with("{}.instance-count".format(app_name), 4)
        mock_cf.return_value.assert_not_called()

    def test_run_task(self, mock_get_statsd_client, mock_cf):
        app_guid = '11111-11111-11111111-1111'
        app_name = 'app-name-1'
        app = App(app_name, ['ElbScaler'])
        app.get_desired_instance_count = Mock(return_value=5)

        mock_cf.return_value.get_paas_apps.return_value = {
            app_name: {'name': app_name, 'instances': 4, 'guid': app_guid},
        }

        autoscaler = Autoscaler()
        autoscaler._schedule = Mock()
        autoscaler.autoscaler_apps = [app]

        autoscaler.run_task()
        mock_get_statsd_client.return_value.gauge.assert_called_once_with("{}.instance-count".format(app_name), 5)
        mock_cf.return_value.apps._update.assert_called_once_with(app_guid, {'instances': 5})


@patch('app.autoscaler.Cf')
@patch('app.autoscaler.get_statsd_client')
@patch.object(ScheduleScaler, '_now', return_value=datetime.datetime(2018, 3, 15, 4, 20, 00))
@patch.object(ElbScaler, 'gauge')
@patch.object(ElbScaler, '_get_boto3_client')
@patch.object(ElbScaler, '_get_request_counts')
class TestAutoscalerAlmostEndToEnd:
    def test_scale_up(self,
                      mock_get_request_counts,
                      mock_get_boto3_client,
                      mock_gauge,
                      mock_schedule_scaler_now,
                      mock_get_statsd_client,
                      mock_cf):
        app_name = 'test-api-app'
        app_config = {
            'name': app_name,
            'scalers': ['ElbScaler', 'ScheduleScaler'],
            'elb_name': 'my-elb',
            'min_instances': 5,
            'max_instances': 10,
            'threshold': 300,
            'schedule': '''
---
workdays:
  - 08:00-19:00
weekends:
  - 09:00-17:00
scale_factor: 0.8
'''
        }

        mock_cf.return_value.get_paas_apps.return_value = {
            app_name: {'name': app_name, 'instances': 5, 'guid': app_name + '-guid'},
        }

        # to trigger a scale up we need at least one value greater than min_instances * threshold
        mock_get_request_counts.return_value = [1300, 1500, 1600, 1700, 1700]
        app_config['schedule'] = yaml.safe_load(app_config['schedule'])
        app = App(**app_config)

        autoscaler = Autoscaler()
        autoscaler.cooldown_seconds_after_scale_up = 300
        autoscaler.cooldown_seconds_after_scale_down = 60
        autoscaler._now = Mock(datetime.datetime(2018, 3, 17, 10, 20, 00).timestamp())
        autoscaler._schedule = Mock()

        autoscaler.autoscaler_apps = [app]
        autoscaler.run_task()

        mock_get_statsd_client.return_value.gauge.assert_called_once_with("{}.instance-count".format(app_name), 6)
        mock_cf.return_value.apps._update.assert_called_once_with(app_name + '-guid', {'instances': 6})

        # emulate that we are running in schedule now, which means max_instances * scale_factor
        mock_schedule_scaler_now.return_value = datetime.datetime(2018, 3, 15, 14, 20, 00)
        mock_get_statsd_client.return_value.reset_mock()
        mock_cf.return_value.apps._update.reset_mock()

        autoscaler.run_task()

        mock_get_statsd_client.return_value.gauge.assert_called_once_with("{}.instance-count".format(app_name), 8)
        mock_cf.return_value.apps._update.assert_called_once_with(app_name + '-guid', {'instances': 8})
