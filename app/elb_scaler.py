import datetime
import math

from app.base_scalers import AwsBaseScaler


class ElbScaler(AwsBaseScaler):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.elb_name = kwargs['elb_name']
        self.request_count_time_range = kwargs.get('request_count_time_range', {'minutes': 5})
        self._init_cloudwatch_client()

    def _init_cloudwatch_client(self):
        self.cloudwatch_client = super()._get_boto3_client('cloudwatch', region_name=self.aws_region)

    def estimate_instance_count(self):
        print('Processing {}'.format(self.app_name))
        request_counts = self._get_request_counts()
        if len(request_counts) == 0:
            request_counts = [0]
        print('Request counts: {}'.format(request_counts))

        # Keep the highest request count over the specified time range
        highest_request_count = max(request_counts)
        print('Highest request count: {}'.format(highest_request_count))

        self.statsd_client.gauge("{}.request-count".format(self.app_name), highest_request_count)
        desired_instance_count = int(math.ceil(highest_request_count / float(self.threshold)))
        return self.normalize_desired_instance_count(desired_instance_count)

    def _now(self):
        # to make mocking in tests easier
        return datetime.datetime.now()

    def _get_request_counts(self):
        start_time = self._now() - datetime.timedelta(**self.request_count_time_range)
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
