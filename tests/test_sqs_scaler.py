from datetime import datetime

from freezegun import freeze_time
from unittest.mock import patch, Mock, call

from app.sqs_scaler import SqsScaler

app_name = 'test-app'
min_instances = 1
max_instances = 2


@patch('app.base_scalers.boto3')
class TestSqsScaler:
    input_attrs = {
        'threshold': 250,
        'queues': []
    }

    def test_init_assigns_relevant_values(self, mock_boto3):
        self.input_attrs['queues'] = ['queue1', 'queue2']
        sqs_scaler = SqsScaler(app_name, min_instances, max_instances, **self.input_attrs)

        assert sqs_scaler.app_name == app_name
        assert sqs_scaler.min_instances == min_instances
        assert sqs_scaler.max_instances == max_instances
        assert sqs_scaler.queue_length_threshold == self.input_attrs['threshold']
        assert sqs_scaler.throughput_threshold == 1000
        assert sqs_scaler.queues == self.input_attrs['queues']

    def test_init_assigns_relevant_values_non_list_queue(self, mock_boto3):
        self.input_attrs['queues'] = 'queue1'
        sqs_scaler = SqsScaler(app_name, min_instances, max_instances, **self.input_attrs)

        assert sqs_scaler.queues == ['queue1']

    def test_init_sets_throughput_threshold_from_tasks_per_worker_per_minute_if_provided(self, mock_boto3):
        sqs_scaler = SqsScaler(app_name, min_instances, max_instances, **{
            'threshold': 100,
            'tasks_per_worker_per_minute': 5,
            'queues': []
        })
        assert sqs_scaler.queue_length_threshold == 100
        assert sqs_scaler.throughput_threshold == 5

    def test_init_sets_queue_threshold_from_allowed_queue_backlog_per_worker_if_threshold_not_set(self, mock_boto3):
        sqs_scaler = SqsScaler(app_name, min_instances, max_instances, **{
            'allowed_queue_backlog_per_worker': 5,
            'queues': []
        })
        assert sqs_scaler.queue_length_threshold == 5
        assert sqs_scaler.throughput_threshold == 1000

    def test_client_initialization(self, mock_boto3):
        self.input_attrs['queues'] = ['queue1', 'queue2']
        mock_client = mock_boto3.client
        sqs_scaler = SqsScaler(app_name, min_instances, max_instances, **self.input_attrs)
        sqs_scaler.statsd_client = Mock()

        assert sqs_scaler.sqs_client is None
        assert sqs_scaler.cloudwatch_client is None
        sqs_scaler.get_desired_instance_count()
        assert sqs_scaler.sqs_client == mock_client.return_value
        assert sqs_scaler.cloudwatch_client == mock_client.return_value
        calls = [
            call('sqs', region_name='eu-west-1'),
            call('cloudwatch', region_name='eu-west-1'),
        ]
        for x in calls:
            assert x in mock_client.call_args_list

    def test_get_desired_instance_count_based_on_current_queue_length(self, mock_boto3):
        self.input_attrs['queues'] = ['queue1', 'queue2']

        sqs_client = mock_boto3.client.return_value
        sqs_client.get_queue_attributes.side_effect = [
            {'Attributes': {'ApproximateNumberOfMessages': '400'}},
            {'Attributes': {'ApproximateNumberOfMessages': '350'}},
        ]

        sqs_scaler = SqsScaler(app_name, min_instances, max_instances, **self.input_attrs)
        sqs_scaler.statsd_client = Mock()
        assert sqs_scaler._get_desired_instance_count_based_on_current_queue_length() == 3
        calls = [
            call("testqueue1.queue-length", 400),
            call("testqueue2.queue-length", 350),
        ]
        sqs_scaler.statsd_client.gauge.assert_has_calls(calls)

    def test_get_desired_instance_count_sums_based_on_queue_length_and_throughput(self, mock_boto3, mocker):
        self.input_attrs['queues'] = ['queue1', 'queue2']
        sqs_scaler = SqsScaler(app_name, min_instances, max_instances, **self.input_attrs)

        throughput_mock = mocker.patch.object(
            sqs_scaler, "_get_desired_instance_count_based_on_throughput_of_tasks_put_onto_queues"
        )
        queue_length_mock = mocker.patch.object(sqs_scaler, "_get_desired_instance_count_based_on_current_queue_length")
        throughput_mock.return_value = 2
        queue_length_mock.return_value = 3

        assert sqs_scaler._get_desired_instance_count() == 5

        throughput_mock.assert_called_once()
        queue_length_mock.assert_called_once()

    def test_get_desired_instance_count_based_on_queue_throughput(self, mock_boto3, mocker):
        self.input_attrs['queues'] = ['queue1', 'queue2']

        sqs_scaler = SqsScaler(app_name, min_instances, max_instances, **self.input_attrs)

        _get_throughput_mock = mocker.patch.object(
            sqs_scaler, '_get_throughput_of_tasks_put_onto_queue', side_effect=[2000, 800]
        )

        # threshold is 1000
        assert sqs_scaler._get_desired_instance_count_based_on_throughput_of_tasks_put_onto_queues() == 3

        assert _get_throughput_mock.call_args_list == [
            call('queue1'),
            call('queue2'),
        ]

    def test_get_throughput_uses_max_value(self, mock_boto3, mocker):
        sqs_scaler = SqsScaler(app_name, min_instances, max_instances, **self.input_attrs)

        _get_sqs_throughput_mock = mocker.patch.object(
            sqs_scaler, '_get_sqs_throughput_of_tasks_put_onto_queue', return_value=[100, 200, 50]
        )
        statsd_mock = mocker.patch.object(sqs_scaler, 'statsd_client')

        assert sqs_scaler._get_throughput_of_tasks_put_onto_queue('my-queue') == 200
        # queue prefix "test" pulled from SQS_QUEUE_PREFIX env var
        statsd_mock.gauge.assert_called_once_with('testmy-queue.queue-throughput', 50)
        _get_sqs_throughput_mock.assert_called_once_with('testmy-queue')

    def test_get_throughput_returns_0_if_no_data(self, mock_boto3, mocker):
        sqs_scaler = SqsScaler(app_name, min_instances, max_instances, **self.input_attrs)

        mocker.patch.object(
            sqs_scaler, '_get_sqs_throughput_of_tasks_put_onto_queue', return_value=[]
        )
        statsd_mock = mocker.patch.object(sqs_scaler, 'statsd_client')

        assert sqs_scaler._get_throughput_of_tasks_put_onto_queue('my-queue') == 0
        statsd_mock.gauge.assert_called_once_with('testmy-queue.queue-throughput', 0)

    @freeze_time("2018-03-15 15:10:00")
    def test_get_sqs_throughput(self, mock_boto3):
        self.input_attrs['queues'] = ['queue1', 'queue2']

        cloudwatch_client = mock_boto3.client.return_value
        cloudwatch_client.get_metric_statistics.return_value = {
            'Datapoints': [
                {'Sum': 1500, 'Timestamp': 111111110},
                {'Sum': 1600, 'Timestamp': 111111111},
                {'Sum': 5500, 'Timestamp': 111111112},
                {'Sum': 5300, 'Timestamp': 111111113},
                {'Sum': 2100, 'Timestamp': 111111114},
            ]}

        sqs_scaler = SqsScaler(app_name, min_instances, max_instances, **self.input_attrs)

        assert sqs_scaler._get_sqs_throughput_of_tasks_put_onto_queue('my-queue') == [1500, 1600, 5500, 5300, 2100]

        cloudwatch_client.get_metric_statistics.assert_called_once_with(
            Namespace='AWS/SQS',
            MetricName='NumberOfMessagesSent',
            Dimensions=[
                {
                    'Name': 'QueueName',
                    'Value': 'my-queue'
                },
            ],
            StartTime=datetime(2018, 3, 15, 15, 5, 0),
            EndTime=datetime(2018, 3, 15, 15, 10, 0),
            Period=60,
            Statistics=['Sum'],
            Unit='Count'
        )
