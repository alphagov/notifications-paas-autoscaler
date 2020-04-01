from unittest.mock import patch, Mock
from datetime import datetime

import pytest
from freezegun import freeze_time

from app.elb_scaler import ElbScaler

app_name = 'test-app'
min_instances = 1
max_instances = 5


@patch('app.base_scalers.boto3')
class TestElbScaler:
    input_attrs = {
        'threshold': 1500,
        'elb_name': 'notify-paas-proxy',
        'request_count_time_range': {'minutes': 5},
    }

    def test_init_assigns_relevant_values(self, mock_boto3):
        elb_scaler = ElbScaler(app_name, min_instances, max_instances, **self.input_attrs)

        assert elb_scaler.app_name == app_name
        assert elb_scaler.min_instances == min_instances
        assert elb_scaler.max_instances == max_instances
        assert elb_scaler.threshold == self.input_attrs['threshold']
        assert elb_scaler.elb_name == self.input_attrs['elb_name']
        assert elb_scaler.request_count_time_range == self.input_attrs['request_count_time_range']

    def test_cloudwatch_client_initialization(self, mock_boto3):
        mock_client = mock_boto3.client
        elb_scaler = ElbScaler(app_name, min_instances, max_instances, **self.input_attrs)
        elb_scaler.statsd_client = Mock()

        assert elb_scaler.cloudwatch_client is None

        elb_scaler._get_desired_instance_count_from_request_count()

        assert elb_scaler.cloudwatch_client == mock_client.return_value
        mock_client.assert_called_with('cloudwatch', region_name='eu-west-1')

    @freeze_time("2018-03-15 15:10:00")
    def test_get_desired_instance_count_from_request_count(self, mock_boto3):
        cloudwatch_client = mock_boto3.client.return_value
        cloudwatch_client.get_metric_statistics.return_value = {
            'Datapoints': [
                {'Sum': 1500, 'Timestamp': 111111110},
                {'Sum': 1600, 'Timestamp': 111111111},
                {'Sum': 5500, 'Timestamp': 111111112},
                {'Sum': 5300, 'Timestamp': 111111113},
                {'Sum': 2100, 'Timestamp': 111111114},
            ]}

        elb_scaler = ElbScaler(app_name, min_instances, max_instances, **self.input_attrs)
        elb_scaler.statsd_client = Mock()

        assert elb_scaler._get_desired_instance_count_from_request_count() == 4
        cloudwatch_client.get_metric_statistics.assert_called_once_with(
            Namespace='AWS/ELB',
            MetricName='RequestCount',
            Dimensions=[
                {
                    'Name': 'LoadBalancerName',
                    'Value': self.input_attrs['elb_name']
                },
            ],
            StartTime=datetime(2018, 3, 15, 15, 5, 0),
            EndTime=datetime(2018, 3, 15, 15, 10, 0),
            Period=60,
            Statistics=['Sum'],
            Unit='Count')
        elb_scaler.statsd_client.gauge.assert_called_once_with("{}.request-count".format(elb_scaler.app_name), 5500)

    @freeze_time("2018-03-15 15:10:00")
    def test_get_surge_queue_length_returns_highest_value(self, mock_boto3):
        cloudwatch_client = mock_boto3.client.return_value
        cloudwatch_client.get_metric_statistics.return_value = {
            'Datapoints': [
                {'Maximum': 1, 'Timestamp': 111111110},
                {'Maximum': 15, 'Timestamp': 111111113},
                {'Maximum': 3, 'Timestamp': 111111114},
            ]}

        elb_scaler = ElbScaler(app_name, min_instances, max_instances, **self.input_attrs)
        elb_scaler.statsd_client = Mock()

        assert elb_scaler._get_surge_queue_length() == 15

        cloudwatch_client.get_metric_statistics.assert_called_once_with(
            Namespace='AWS/ELB',
            MetricName='SurgeQueueLength',
            Dimensions=[
                {
                    'Name': 'LoadBalancerName',
                    'Value': self.input_attrs['elb_name']
                },
            ],
            StartTime=datetime(2018, 3, 15, 15, 5, 0),
            EndTime=datetime(2018, 3, 15, 15, 10, 0),
            Period=60,
            Statistics=['Maximum'],
        )

    @freeze_time("2018-03-15 15:10:00")
    def test_get_surge_queue_length_returns_0_when_queue_is_empty(self, mock_boto3):
        cloudwatch_client = mock_boto3.client.return_value
        cloudwatch_client.get_metric_statistics.return_value = {'Datapoints': []}

        elb_scaler = ElbScaler(app_name, min_instances, max_instances, **self.input_attrs)
        elb_scaler.statsd_client = Mock()

        assert elb_scaler._get_surge_queue_length() == 0

    @pytest.mark.parametrize('num_items, expected_return', [(15, True), (0, False)])
    def test_surge_queue_has_items(self, mock_boto3, mocker, num_items, expected_return):
        elb_scaler = ElbScaler(app_name, min_instances, max_instances, **self.input_attrs)

        mocker.patch.object(elb_scaler, '_get_surge_queue_length', return_value=num_items)
        statsd = mocker.patch.object(elb_scaler, 'statsd_client')

        assert elb_scaler._surge_queue_has_items() is expected_return

        statsd.gauge.assert_called_once_with("test-app.surge-queue", num_items)

    @pytest.mark.parametrize('desired_count_from_requests, surge_queue_has_items, expected_count', [
        (1, True, 5),  # surge queue overrides and sets to max_instances
        (3, False, 3),  # otherwise we take the desired count from requests
    ])
    def test_get_desired_instance_count(
        self,
        mock_boto3,
        mocker,
        desired_count_from_requests,
        surge_queue_has_items,
        expected_count
    ):
        elb_scaler = ElbScaler(app_name, min_instances, max_instances, **self.input_attrs)
        mocker.patch.object(elb_scaler, 'statsd_client')
        mock_surge_queue = mocker.patch.object(elb_scaler, '_surge_queue_has_items', return_value=surge_queue_has_items)
        mock_desired_from_requests = mocker.patch.object(
            ElbScaler,
            '_get_desired_instance_count_from_request_count',
            return_value=desired_count_from_requests
        )

        assert elb_scaler._get_desired_instance_count() == expected_count

        mock_surge_queue.assert_called_once_with()
        mock_desired_from_requests.assert_called_once_with()
