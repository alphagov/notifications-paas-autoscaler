from unittest.mock import patch, Mock

from app.autoscaler import Autoscaler


@patch.object(Autoscaler, 'cf_client')
@patch.object(Autoscaler, 'statsd_client')
class TestAutoscaler:
    def test_scale_paas_app_same_instance_count(self, mock_statsd_client, mock_cf_client):
        app_guid = '11111-11111-11111111-1111'
        app_name = 'app-name-1'
        autoscaler = Autoscaler()
        autoscaler.scale_paas_apps(app_name, {'guid': app_guid}, 4, 4)
        mock_cf_client.assert_not_called()

    def test_scale_paas_app_more_instances(self, mock_statsd_client, mock_cf_client):
        app_guid = '11111-11111-11111111-1111'
        app_name = 'app-name-1'
        autoscaler = Autoscaler()
        autoscaler.scale_paas_apps(app_name, {'guid': app_guid}, 4, 6)
        mock_cf_client.apps._update.assert_called_once_with(app_guid, {'instances': 6})

    def test_scale_paas_app_much_fewer_instances(self, mock_statsd_client, mock_cf_client):
        app_guid = '11111-11111-11111111-1111'
        app_name = 'app-name-1'
        autoscaler = Autoscaler()
        autoscaler.cooldown_seconds_after_scale_up = 300
        autoscaler.cooldown_seconds_after_scale_down = 60
        autoscaler.last_scale_up[app_name] = 1000
        autoscaler.last_scale_down[app_name] = 800
        autoscaler._now = Mock(return_value=1500)
        autoscaler.scale_paas_apps(app_name, {'guid': app_guid}, 4, 1)
        mock_cf_client.apps._update.assert_called_once_with(app_guid, {'instances': 3})

    def test_scale_paas_app_fewer_instances_recent_scale_up(self, mock_statsd_client, mock_cf_client):
        app_guid = '11111-11111-11111111-1111'
        app_name = 'app-name-1'
        autoscaler = Autoscaler()
        autoscaler.cooldown_seconds_after_scale_up = 300
        autoscaler.cooldown_seconds_after_scale_down = 60
        autoscaler.last_scale_up[app_name] = 1000
        autoscaler.last_scale_down[app_name] = 800
        autoscaler._now = Mock(return_value=1200)
        autoscaler.scale_paas_apps(app_name, {'guid': app_guid}, 4, 3)
        mock_cf_client.assert_not_called()

    def test_scale_paas_app_fewer_instances_recent_scale_down(self, mock_statsd_client, mock_cf_client):
        app_guid = '11111-11111-11111111-1111'
        app_name = 'app-name-1'
        autoscaler = Autoscaler()
        autoscaler.cooldown_seconds_after_scale_up = 300
        autoscaler.cooldown_seconds_after_scale_down = 60
        autoscaler.last_scale_up[app_name] = 1000
        autoscaler.last_scale_down[app_name] = 1400
        autoscaler._now = Mock(return_value=1430)
        autoscaler.scale_paas_apps(app_name, {'guid': app_guid}, 4, 3)
        mock_cf_client.assert_not_called()

    def test_scale_paas_app_fewer_instances_recent_scale_information(self, mock_statsd_client, mock_cf_client):
        app_guid = '11111-11111-11111111-1111'
        app_name = 'app-name-1'
        autoscaler = Autoscaler()
        autoscaler.cooldown_seconds_after_scale_up = 300
        autoscaler.cooldown_seconds_after_scale_down = 60
        autoscaler._now = Mock(return_value=1000)
        autoscaler.scale_paas_apps(app_name, {'guid': app_guid}, 4, 3)
        mock_cf_client.assert_not_called()
