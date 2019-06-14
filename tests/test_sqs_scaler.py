from unittest.mock import patch, Mock, call

from app.sqs_scaler import SqsScaler

app_name = 'test-app'
min_instances = 1
max_instances = 2


@patch('app.base_scalers.boto3')
class TestSqsScaler:
    input_attrs = {
        'threshold': 250,
    }

    def test_init_assigns_relevant_values(self, mock_boto3):
        self.input_attrs['queues'] = ['queue1', 'queue2']
        sqs_scaler = SqsScaler(app_name, min_instances, max_instances, **self.input_attrs)

        assert sqs_scaler.app_name == app_name
        assert sqs_scaler.min_instances == min_instances
        assert sqs_scaler.max_instances == max_instances
        assert sqs_scaler.threshold == self.input_attrs['threshold']
        assert sqs_scaler.queues == self.input_attrs['queues']

    def test_init_assigns_relevant_values_non_list_queue(self, mock_boto3):
        self.input_attrs['queues'] = 'queue1'
        sqs_scaler = SqsScaler(app_name, min_instances, max_instances, **self.input_attrs)

        assert sqs_scaler.queues == ['queue1']

    def test_sqs_client_initialization(self, mock_boto3):
        self.input_attrs['queues'] = ['queue1', 'queue2']
        mock_client = mock_boto3.client
        sqs_scaler = SqsScaler(app_name, min_instances, max_instances, **self.input_attrs)
        sqs_scaler.statsd_client = Mock()

        assert sqs_scaler.sqs_client is None
        sqs_scaler.get_desired_instance_count()
        assert sqs_scaler.sqs_client == mock_client.return_value
        mock_client.assert_called_with('sqs', region_name='eu-west-1')

    def test_get_desired_instance_count(self, mock_boto3):
        self.input_attrs['queues'] = ['queue1', 'queue2']

        sqs_client = mock_boto3.client.return_value
        sqs_client.get_queue_attributes.side_effect = [
            {'Attributes': {'ApproximateNumberOfMessages': '400'}},
            {'Attributes': {'ApproximateNumberOfMessages': '350'}},
        ]

        sqs_scaler = SqsScaler(app_name, min_instances, max_instances, **self.input_attrs)
        sqs_scaler.statsd_client = Mock()
        assert sqs_scaler.get_desired_instance_count() == 2
        calls = [
            call("testqueue1.queue-length", 400),
            call("testqueue2.queue-length", 350),
        ]
        sqs_scaler.statsd_client.incr.assert_has_calls(calls)
