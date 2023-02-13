import logging
import math
from datetime import timedelta

from app.base_scalers import AwsBaseScaler
from app.config import config

# calculated by looking at log output of a single instance of delivery-worker-save-api-notifications on production
# during high load
THROUGHPUT_OF_TASKS_PER_WORKER_PER_MINUTE = 1000


class SqsScaler(AwsBaseScaler):
    def __init__(self, app_name, min_instances, max_instances, **kwargs):
        super().__init__(app_name, min_instances, max_instances, kwargs.get("aws_region"))
        self.queue_length_threshold = kwargs.get("threshold") or kwargs["allowed_queue_backlog_per_worker"]
        self.throughput_threshold = kwargs.get("tasks_per_worker_per_minute", THROUGHPUT_OF_TASKS_PER_WORKER_PER_MINUTE)
        self.queues = kwargs["queues"] if isinstance(kwargs["queues"], list) else [kwargs["queues"]]
        self.sqs_queue_prefix = config["SCALERS"]["SQS_QUEUE_PREFIX"]
        self.request_count_time_range = kwargs.get("request_count_time_range", {"minutes": 5})
        self.sqs_client = None
        self.cloudwatch_client = None

    def _init_sqs_client(self):
        if self.sqs_client is None:
            self.sqs_client = super()._get_boto3_client("sqs", region_name=self.aws_region)

    def _init_cloudwatch_client(self):
        if self.cloudwatch_client is None:
            self.cloudwatch_client = super()._get_boto3_client("cloudwatch", region_name=self.aws_region)

    def _get_desired_instance_count(self):
        logging.debug("Processing {}".format(self.app_name))
        instance_count_throughput = self._get_desired_instance_count_based_on_throughput_of_tasks_put_onto_queues()
        instance_count_queue_length = self._get_desired_instance_count_based_on_current_queue_length()

        # We don't actually use these metrics for determining how many instances should be counted
        # We are only having those code here as it's the easiest and quickest way to publish very similar metrics to
        # those we use for number of items in the queue and number of items being put onto the queue
        self._publish_metrics_for_throughput_of_tasks_pulled_from_queues()

        # How many instances we run should be enough to handle the current level of throughput, however
        # if the throughput remains the same and we already have items building up in our queue, then we
        # wish to scale even higher to bring the queue down
        return instance_count_throughput + instance_count_queue_length

    def _get_desired_instance_count_based_on_current_queue_length(self):
        total_message_count = self._get_total_message_count(self.queues)
        logging.debug("Total message count: {}".format(total_message_count))
        desired_instance_count = int(math.ceil(total_message_count / float(self.queue_length_threshold)))
        return desired_instance_count

    def _get_desired_instance_count_based_on_throughput_of_tasks_put_onto_queues(self):
        total_throughput = self._get_total_throughput_of_tasks_put_onto_queues(self.queues)
        logging.debug("Total throughput: {}".format(total_throughput))
        desired_instance_count = int(math.ceil(total_throughput / float(self.throughput_threshold)))
        return desired_instance_count

    def _get_sqs_queue_name(self, name):
        return "{}{}".format(self.sqs_queue_prefix, name)

    def _get_sqs_queue_url(self, name):
        return "https://sqs.{}.amazonaws.com/{}/{}".format(self.aws_region, self.aws_account_id, name)

    def _get_sqs_message_count(self, name):
        # Number of visible messages waiting in the queue to be picked up
        self._init_sqs_client()
        response = self.sqs_client.get_queue_attributes(
            QueueUrl=self._get_sqs_queue_url(name), AttributeNames=["ApproximateNumberOfMessages"]
        )
        result = int(response["Attributes"]["ApproximateNumberOfMessages"])
        logging.debug("Messages in {}: {}".format(name, result))
        return result

    def _get_message_count(self, queue):
        queue_name = self._get_sqs_queue_name(queue)
        message_count = self._get_sqs_message_count(queue_name)
        self.gauge("{}.queue-length".format(queue_name), message_count)
        return message_count

    def _get_total_message_count(self, queues):
        return sum(self._get_message_count(queue) for queue in queues)

    def _get_sqs_throughput_of_tasks_put_onto_queue(self, name):
        self._init_cloudwatch_client()
        start_time = self._now() - timedelta(**self.request_count_time_range)
        end_time = self._now()
        result = self.cloudwatch_client.get_metric_statistics(
            Namespace="AWS/SQS",
            MetricName="NumberOfMessagesSent",
            Dimensions=[
                {"Name": "QueueName", "Value": name},
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=60,
            Statistics=["Sum"],
            Unit="Count",
        )
        datapoints = result["Datapoints"]
        datapoints = sorted(datapoints, key=lambda x: x["Timestamp"])
        return [row["Sum"] for row in datapoints]

    def _get_throughput_of_tasks_put_onto_queue(self, queue):
        queue_name = self._get_sqs_queue_name(queue)
        past_5_mins_of_throughput = self._get_sqs_throughput_of_tasks_put_onto_queue(queue_name)

        if len(past_5_mins_of_throughput) == 0:
            past_5_mins_of_throughput = [0]
        logging.debug("Throughput of tasks put onto queue: {}".format(past_5_mins_of_throughput))

        # Keep the highest throughput over the specified time range
        highest_throughput = max(past_5_mins_of_throughput)
        logging.debug("Highest throughput of tasks put onto queue: {}".format(highest_throughput))

        self.gauge("{}.queue-throughput".format(queue_name), past_5_mins_of_throughput[-1])
        return highest_throughput

    def _get_total_throughput_of_tasks_put_onto_queues(self, queues):
        return sum(self._get_throughput_of_tasks_put_onto_queue(queue) for queue in queues)

    def _get_sqs_throughput_of_tasks_pulled_from_queue(self, name):
        self._init_cloudwatch_client()
        start_time = self._now() - timedelta(**self.request_count_time_range)
        end_time = self._now()
        result = self.cloudwatch_client.get_metric_statistics(
            Namespace="AWS/SQS",
            MetricName="NumberOfMessagesReceived",
            Dimensions=[
                {"Name": "QueueName", "Value": name},
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=60,
            Statistics=["Sum"],
            Unit="Count",
        )
        datapoints = result["Datapoints"]
        datapoints = sorted(datapoints, key=lambda x: x["Timestamp"])
        return [row["Sum"] for row in datapoints]

    def _get_throughput_of_tasks_pulled_from_queue(self, queue):
        queue_name = self._get_sqs_queue_name(queue)
        past_5_mins_of_throughput = self._get_sqs_throughput_of_tasks_pulled_from_queue(queue_name)

        if len(past_5_mins_of_throughput) == 0:
            past_5_mins_of_throughput = [0]
        logging.debug("Throughput of tasks pulled from queue: {}".format(past_5_mins_of_throughput))

        # Keep the highest throughput over the specified time range
        highest_throughput = max(past_5_mins_of_throughput)
        logging.debug("Highest throughput of tasks pulled from queue: {}".format(highest_throughput))

        self.gauge("{}.throughput-tasks-pulled-from-queue".format(queue_name), past_5_mins_of_throughput[-1])
        return highest_throughput

    def _publish_metrics_for_throughput_of_tasks_pulled_from_queues(self):
        for queue in self.queues:
            self._get_throughput_of_tasks_pulled_from_queue(queue)
