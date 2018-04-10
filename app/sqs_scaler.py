import math
import os

from app.base_scalers import AwsBaseScaler


class SqsScaler(AwsBaseScaler):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.queues = kwargs['queues'] if isinstance(kwargs['queues'], list) else [kwargs['queues']]
        self.sqs_queue_prefix = os.environ.get('SQS_QUEUE_PREFIX', '')
        self.sqs_client = None

    def _init_sqs_client(self):
        if self.sqs_client is None:
            self.sqs_client = super()._get_boto3_client('sqs', region_name=self.aws_region)

    def get_desired_instance_count(self):
        print('Processing {}'.format(self.app_name))
        total_message_count = self._get_total_message_count(self.queues)
        print('Total message count: {}'.format(total_message_count))
        desired_instance_count = int(math.ceil(total_message_count / float(self.threshold)))

        return self.normalize_desired_instance_count(desired_instance_count)

    def _get_sqs_queue_name(self, name):
        return "{}{}".format(self.sqs_queue_prefix, name)

    def _get_sqs_queue_url(self, name):
        return "https://sqs.{}.amazonaws.com/{}/{}".format(
            self.aws_region, self.aws_account_id, name)

    def _get_sqs_message_count(self, name):
        self._init_sqs_client()
        response = self.sqs_client.get_queue_attributes(
            QueueUrl=self._get_sqs_queue_url(name),
            AttributeNames=['ApproximateNumberOfMessages'])
        result = int(response['Attributes']['ApproximateNumberOfMessages'])
        print('Messages in {}: {}'.format(name, result))
        return result

    def _get_message_count(self, queue):
        queue_name = self._get_sqs_queue_name(queue)
        message_count = self._get_sqs_message_count(queue_name)
        self.incr("{}.queue-length".format(queue_name), message_count)
        return message_count

    def _get_total_message_count(self, queues):
        return sum(self._get_message_count(queue) for queue in queues)
