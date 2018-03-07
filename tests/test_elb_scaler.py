from unittest.mock import patch, Mock, call
import os

from app.elb_scaler import ElbScaler


@patch('app.base_scalers.boto3')
class TestElbScaler:
    input_attrs = {
        'min_instances': 1,
        'max_instances': 2,
        'threshold': 1500,
        'elb_name': 'notify-paas-proxy',
        'request_count_time_range': {'minutes': 10},
    }

    def test_init_assigns_relevant_values(self, mock_boto3):
        elb_scaler = ElbScaler(**self.input_attrs)

        assert elb_scaler.min_instances == self.input_attrs['min_instances']
        assert elb_scaler.max_instances == self.input_attrs['max_instances']
        assert elb_scaler.threshold == self.input_attrs['threshold']
        assert elb_scaler.elb_name == self.input_attrs['elb_name']
        assert elb_scaler.request_count_time_range == self.input_attrs['request_count_time_range']

    def test_cloudwatch_client_initialization(self, mock_boto3):
        mock_client = mock_boto3.client
        elb_scaler = ElbScaler(**self.input_attrs)
        assert elb_scaler.cloudwatch_client == mock_client.return_value
        mock_client.assert_called_with('cloudwatch', region_name='eu-west-1')

    def test_estimate_instance_count(self, mock_boto3):
        pass
