from unittest.mock import patch, Mock
import datetime

from freezegun import freeze_time

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
        elb_scaler.statsd_client = Mock()

        assert elb_scaler.cloudwatch_client is None
        elb_scaler.get_desired_instance_count()
        assert elb_scaler.cloudwatch_client == mock_client.return_value
        mock_client.assert_called_with('cloudwatch', region_name='eu-west-1')

    @freeze_time("2018-03-15 15:10:00")
    def test_get_desired_instance_count(self, mock_boto3):
        # set to 5 minutes, to have a smaller mocked response
        self.input_attrs['request_count_time_range'] = {'minutes': 5}
        cloudwatch_client = mock_boto3.client.return_value
        cloudwatch_client.get_metric_statistics.return_value = {
            'Datapoints': [
                {'Sum': 1500, 'Timestamp': 111111110},
                {'Sum': 1600, 'Timestamp': 111111111},
                {'Sum': 5500, 'Timestamp': 111111112},
                {'Sum': 5300, 'Timestamp': 111111113},
                {'Sum': 2100, 'Timestamp': 111111114},
            ]}

        elb_scaler = ElbScaler(**self.input_attrs)
        elb_scaler.statsd_client = Mock()

        assert elb_scaler.get_desired_instance_count() == 2
        cloudwatch_client.get_metric_statistics.assert_called_once_with(
            Namespace='AWS/ELB',
            MetricName='RequestCount',
            Dimensions=[
                {
                    'Name': 'LoadBalancerName',
                    'Value': self.input_attrs['elb_name']
                },
            ],
            StartTime=elb_scaler._now() - datetime.timedelta(**self.input_attrs['request_count_time_range']),
            EndTime=elb_scaler._now(),
            Period=60,
            Statistics=['Sum'],
            Unit='Count')
        elb_scaler.statsd_client.gauge.assert_called_once_with("{}.request-count".format(elb_scaler.app_name), 5500)
