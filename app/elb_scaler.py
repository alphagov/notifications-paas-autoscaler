import logging
import math
from datetime import timedelta

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
        logging.debug('Processing {}'.format(self.app_name))
        request_counts = self._get_request_counts()
        if len(request_counts) == 0:
            request_counts = [0]
        logging.debug('Request counts: {}'.format(request_counts))

        # Keep the highest request count over the specified time range
        highest_request_count = max(request_counts)
        logging.debug('Highest request count: {}'.format(highest_request_count))

        self.gauge("{}.request-count".format(self.app_name), highest_request_count)
        desired_instance_count = int(math.ceil(highest_request_count / float(self.threshold)))
        return desired_instance_count

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
