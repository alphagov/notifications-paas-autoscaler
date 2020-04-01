from datetime import timedelta
import logging
import math

from app.base_scalers import AwsBaseScaler


class ElbScaler(AwsBaseScaler):
    def __init__(self, app_name, min_instances, max_instances, **kwargs):
        super().__init__(app_name, min_instances, max_instances, kwargs.get('aws_region'))
        self.elb_name = kwargs['elb_name']
        self.threshold = kwargs['threshold']
        self.request_count_time_range = kwargs.get('request_count_time_range', {'minutes': 5})
        self.cloudwatch_client = None

    def _init_cloudwatch_client(self):
        if self.cloudwatch_client is None:
            self.cloudwatch_client = super()._get_boto3_client('cloudwatch', region_name=self.aws_region)

    def _get_desired_instance_count(self):
        # we need to get the value even if surge queue has items, so that we update statsd metrics.
        desired_instance_count = self._get_desired_instance_count_from_request_count()

        if self._surge_queue_has_items():
            desired_instance_count = self.max_instances

        return desired_instance_count

    def _get_desired_instance_count_from_request_count(self):
        logging.debug('Processing {}'.format(self.app_name))
        request_counts = self._get_request_counts()
        if len(request_counts) == 0:
            request_counts = [0]
        logging.debug('Request counts: {}'.format(request_counts))

        # Keep the highest request count over the specified time range
        highest_request_count = max(request_counts)
        logging.debug('Highest request count: {}'.format(highest_request_count))

        self.gauge("{}.request-count".format(self.app_name), highest_request_count)
        return int(math.ceil(highest_request_count / float(self.threshold)))

    def _surge_queue_has_items(self):
        surge_queue_length = self._get_surge_queue_length()
        self.gauge("{}.surge-queue".format(self.app_name), surge_queue_length)
        logging.debug('Surge queue length: {}'.format(surge_queue_length))
        return surge_queue_length != 0

    def _get_request_counts(self):
        self._init_cloudwatch_client()
        start_time = self._now() - timedelta(**self.request_count_time_range)
        end_time = self._now()
        result = self.cloudwatch_client.get_metric_statistics(
            Namespace='AWS/ELB',
            MetricName='RequestCount',
            Dimensions=[
                {
                    'Name': 'LoadBalancerName',
                    'Value': self.elb_name
                },
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=60,
            Statistics=['Sum'],
            Unit='Count'
        )
        datapoints = result['Datapoints']
        datapoints = sorted(datapoints, key=lambda x: x['Timestamp'])
        return [row['Sum'] for row in datapoints]

    def _get_surge_queue_length(self):
        """
        The Surge Queue is a queue in AWS ELB - if none of our apps accept an incoming connection, it'll queue up to
        1024 connections that our nginx (really our api) instances aren't able to accept. We shouldn't ever have
        anything in this queue - so if it's nonzero we should scale up.

        In the short term this metric is stored per second, but we should get the max val from the last 5 minutes anyway
        to be safe.
        """
        self._init_cloudwatch_client()
        start_time = self._now() - timedelta(**self.request_count_time_range)
        end_time = self._now()

        results = self.cloudwatch_client.get_metric_statistics(
            Namespace='AWS/ELB',
            MetricName='SurgeQueueLength',
            Dimensions=[
                {
                    'Name': 'LoadBalancerName',
                    'Value': 'notify-paas-proxy'
                },
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=60,
            Statistics=['Maximum'],
        )
        datapoints = results['Datapoints']
        if datapoints:
            return max(row['Maximum'] for row in datapoints)
        else:
            return 0
