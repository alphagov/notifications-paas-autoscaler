import datetime
import logging
from unittest.mock import patch, Mock

from cloudfoundry_client.errors import InvalidStatusCode
from freezegun import freeze_time
import fakeredis
import yaml

from app.autoscaler import Autoscaler
from app.base_scalers import AwsBaseScaler
from app.elb_scaler import ElbScaler
from app.app import App

SCALEUP_COOLDOWN_SECONDS = 300
SCALEDOWN_COOLDOWN_SECONDS = 60


@freeze_time("2018-05-31 06:00:00")
@patch.object(Autoscaler, '_load_autoscaler_apps')
@patch('app.autoscaler.Redis', fakeredis.FakeRedis)
@patch('app.autoscaler.PaasClient')
@patch('app.autoscaler.get_statsd_client')
class TestScale:
    def _now(self):
        return datetime.datetime.utcnow().timestamp()

    def _get_mock_app(self, name, paas_client_attributes):
        app = Mock()
        app.name = name
        app.cf_attributes = paas_client_attributes

        return app

    def test_scale_paas_app_same_instance_count(self, mock_get_statsd_client, mock_paas_client, *args):
        app_name = 'app-name-1'
        app_guid = '11111-11111-11111111-1111'
        cf_info = {'name': app_name, 'instances': 4, 'guid': app_guid}
        app = self._get_mock_app(app_name, cf_info)
        app.get_desired_instance_count = Mock(return_value=4)

        autoscaler = Autoscaler()
        autoscaler.scale(app)
        mock_get_statsd_client.return_value.gauge.assert_called_once_with("{}.instance-count".format(app_name), 4)
        mock_paas_client.return_value.assert_not_called()

    def test_scale_paas_app_more_instances(self, mock_get_statsd_client, mock_paas_client, *args):
        app_guid = '11111-11111-11111111-1111'
        app_name = 'app-name-1'
        cf_info = {'name': app_name, 'instances': 4, 'guid': app_guid}
        app = self._get_mock_app(app_name, cf_info)
        app.get_desired_instance_count = Mock(return_value=6)

        autoscaler = Autoscaler()
        autoscaler.scale(app)
        assert float(autoscaler.redis_client.hget('last_scale_up', app_name)) == self._now()
        mock_get_statsd_client.return_value.gauge.assert_called_once_with("{}.instance-count".format(app_name), 6)
        mock_paas_client.return_value.update.assert_called_once_with(app_guid, 6)

    def test_scale_paas_app_much_fewer_instances(self, mock_get_statsd_client, mock_paas_client, *args):
        """ We don't scale down more than 1 instance at a time """
        app_guid = '11111-11111-11111111-1111'
        app_name = 'app-name-1'
        cf_info = {'name': app_name, 'instances': 4, 'guid': app_guid}
        app = self._get_mock_app(app_name, cf_info)
        app.get_desired_instance_count = Mock(return_value=1)

        autoscaler = Autoscaler()
        autoscaler.cooldown_seconds_after_scale_up = SCALEUP_COOLDOWN_SECONDS
        autoscaler.cooldown_seconds_after_scale_down = SCALEDOWN_COOLDOWN_SECONDS

        # we scaled down 600 seconds ago, scaled up 325 seconds ago
        autoscaler._set_last_scale('last_scale_down', app_name, (self._now() - SCALEDOWN_COOLDOWN_SECONDS * 10))
        autoscaler._set_last_scale('last_scale_up', app_name, (self._now() - (SCALEUP_COOLDOWN_SECONDS + 25)))
        autoscaler.scale(app)
        assert float(autoscaler.redis_client.hget('last_scale_down', app_name)) == self._now()
        mock_get_statsd_client.return_value.gauge.assert_called_once_with("{}.instance-count".format(app_name), 3)
        mock_paas_client.return_value.update.assert_called_once_with(app_guid, 3)

    def test_scale_paas_app_fewer_instances_recent_scale_up(self, mock_get_statsd_client, mock_paas_client, *args):
        """ We don't scale down after a recent scale up event """
        app_guid = '11111-11111-11111111-1111'
        app_name = 'app-name-1'
        cf_info = {'name': app_name, 'instances': 4, 'guid': app_guid}
        app = self._get_mock_app(app_name, cf_info)
        app.get_desired_instance_count = Mock(return_value=3)

        autoscaler = Autoscaler()
        autoscaler.cooldown_seconds_after_scale_up = SCALEUP_COOLDOWN_SECONDS
        autoscaler.cooldown_seconds_after_scale_down = SCALEDOWN_COOLDOWN_SECONDS

        # we scaled down 600 seconds ago, scaled up 100 seconds ago
        autoscaler._set_last_scale('last_scale_down', app_name, (self._now() - SCALEDOWN_COOLDOWN_SECONDS * 10))
        autoscaler._set_last_scale('last_scale_up', app_name, (self._now() - 100))
        autoscaler.scale(app)
        mock_get_statsd_client.return_value.gauge.assert_called_once_with("{}.instance-count".format(app_name), 4)
        mock_paas_client.return_value.update.assert_not_called()

    def test_scale_paas_app_fewer_instances_recent_scale_down(self, mock_get_statsd_client, mock_paas_client, *args):
        app_guid = '11111-11111-11111111-1111'
        app_name = 'app-name-1'
        cf_info = {'name': app_name, 'instances': 4, 'guid': app_guid}
        app = self._get_mock_app(app_name, cf_info)
        app.get_desired_instance_count = Mock(return_value=3)

        autoscaler = Autoscaler()
        autoscaler.cooldown_seconds_after_scale_up = SCALEUP_COOLDOWN_SECONDS
        autoscaler.cooldown_seconds_after_scale_down = SCALEDOWN_COOLDOWN_SECONDS

        # we scaled up 600 seconds ago, scaled down 30 seconds ago
        autoscaler._set_last_scale('last_scale_down', app_name, (self._now() - 30))
        autoscaler._set_last_scale('last_scale_up', app_name, (self._now() - 600))

        autoscaler.scale(app)
        mock_get_statsd_client.return_value.gauge.assert_called_once_with("{}.instance-count".format(app_name), 4)
        mock_paas_client.return_value.assert_not_called()

    def test_scale_paas_app_fewer_instances_missing_recent_scale_information(self, mock_get_statsd_client,
                                                                             mock_paas_client, *args):
        app_guid = '11111-11111-11111111-1111'
        app_name = 'app-name-1'
        cf_info = {'name': app_name, 'instances': 4, 'guid': app_guid}
        app = self._get_mock_app(app_name, cf_info)
        app.get_desired_instance_count = Mock(return_value=3)

        autoscaler = Autoscaler()
        autoscaler.cooldown_seconds_after_scale_up = SCALEUP_COOLDOWN_SECONDS
        autoscaler.cooldown_seconds_after_scale_down = SCALEDOWN_COOLDOWN_SECONDS
        autoscaler.scale(app)
        mock_get_statsd_client.return_value.gauge.assert_called_once_with("{}.instance-count".format(app_name), 4)
        mock_paas_client.return_value.assert_not_called()

    def test_scale_paas_app_handles_deployments(self, mock_get_statsd_client, mock_paas_client, _, caplog):
        caplog.set_level(logging.INFO)
        app_name = 'app-name-1'
        app_guid = '11111-11111-11111111-1111'
        cf_info = {'name': app_name, 'instances': 4, 'guid': app_guid}
        app = self._get_mock_app(app_name, cf_info)
        app.get_desired_instance_count = Mock(return_value=6)

        mock_paas_client.return_value.update.side_effect = InvalidStatusCode(
            status_code=422,
            body={
                "description": "Cannot scale this process while a deployment is in flight.",
                "error_code": "CF-ScaleDisabledDuringDeployment",
                "code": 390016
            }
        )

        autoscaler = Autoscaler()
        autoscaler.scale(app)
        mock_paas_client.return_value.update.assert_called_once_with(app_guid, 6)
        assert caplog.record_tuples == [
            ('root', logging.INFO, 'Scaling app-name-1 from 4 to 6'),
            ('root', logging.INFO, 'Cannot scale during deployment app-name-1')
        ]

    def test_scale_paas_app_handles_unexpected_errors(self, mock_get_statsd_client, mock_paas_client, _, caplog):
        caplog.set_level(logging.INFO)
        app_name = 'app-name-1'
        app_guid = '11111-11111-11111111-1111'
        cf_info = {'name': app_name, 'instances': 4, 'guid': app_guid}
        app = self._get_mock_app(app_name, cf_info)
        app.get_desired_instance_count = Mock(return_value=6)

        mock_paas_client.return_value.update.side_effect = InvalidStatusCode(
            status_code=400,
            body={'description': 'something bad'}
        )

        autoscaler = Autoscaler()
        autoscaler.scale(app)
        mock_paas_client.return_value.update.assert_called_once_with(app_guid, 6)
        assert caplog.record_tuples == [
            ('root', logging.INFO, 'Scaling app-name-1 from 4 to 6'),
            ('root', logging.ERROR, 'Failed to scale app-name-1: 400 : {"description": "something bad"}')
        ]


class TestAutoscalerAlmostEndToEnd:
    def test_scale_up(self, mocker):
        """Test consequent scalings on and off schedule"""
        app_name = 'test-api-app'
        app_config = {
            'name': app_name,
            'min_instances': 5,
            'max_instances': 10,
            'scalers': [{
                'type': 'ElbScaler',
                'elb_name': 'my-elb',
                'threshold': 300
            }, {
                'type': 'ScheduleScaler',
                'schedule': '''
---
workdays:
  - 08:00-19:00
weekends:
  - 09:00-17:00
scale_factor: 0.8
'''
            }]
        }

        mocker.patch.object(AwsBaseScaler, '_get_boto3_client')
        mocker.patch.object(ElbScaler, '_get_boto3_client')
        mocker.patch.object(ElbScaler, 'gauge')
        mocker.patch.object(ElbScaler, '_get_request_counts', return_value=[1300, 1500, 1600, 1700, 1700])
        mock_paas_client = mocker.patch('app.autoscaler.PaasClient')
        mocker.patch('app.autoscaler.Redis', fakeredis.FakeRedis)
        mock_get_statsd_client = mocker.patch('app.autoscaler.get_statsd_client')

        mock_paas_client.return_value.get_paas_apps.return_value = {
            app_name: {'name': app_name, 'instances': 5, 'guid': app_name + '-guid'},
        }

        with freeze_time("Thursday 31 May 2018 06:00:00") as frozen_time:
            # to trigger a scale up we need at least one value greater than min_instances * threshold
            app_config['scalers'][1]['schedule'] = yaml.safe_load(app_config['scalers'][1]['schedule'])
            app = App(**app_config)

            autoscaler = Autoscaler()
            autoscaler.cooldown_seconds_after_scale_up = 300
            autoscaler.cooldown_seconds_after_scale_down = 60
            autoscaler._schedule = Mock()

            autoscaler.autoscaler_apps = [app]
            autoscaler.run_task()

            mock_get_statsd_client.return_value.gauge.assert_called_once_with("{}.instance-count".format(app_name), 6)
            mock_paas_client.return_value.update.assert_called_once_with(app_name + '-guid', 6)

            # emulate that we are running in schedule now, which means max_instances * scale_factor
            frozen_time.move_to("Thursday 31 May 2018 13:15:00")
            mock_get_statsd_client.return_value.reset_mock()
            mock_paas_client.return_value.update.reset_mock()

            autoscaler.run_task()

            mock_get_statsd_client.return_value.gauge.assert_called_once_with("{}.instance-count".format(app_name), 8)
            mock_paas_client.return_value.update.assert_called_once_with(app_name + '-guid', 8)
