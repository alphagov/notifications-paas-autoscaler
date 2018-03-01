import os

import boto3


class BaseScaler:
    def __init__(self, min_instances, max_instances, threshold, **kwargs):
        self.min_instances = min_instances
        self.max_instances = max_instances
        self.threshold = threshold
        self.app_name = kwargs.get('app_name', 'missing_name')

    def normalize_desired_instance_count(self, desired_instances):
        desired_instances = max(desired_instances, self.min_instances)
        desired_instances = min(desired_instances, self.max_instances)

        return desired_instances

    def estimate_instance_count(self):
        raise NotImplementedError


class AwsBaseScaler(BaseScaler):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.aws_region = kwargs.get('aws_region') or os.environ.get('AWS_REGION', 'eu-west-1')
        self.aws_account_id = self._get_boto3_client('sts', region_name=self.aws_region).get_caller_identity()['Account']

    def _get_boto3_client(self, client, **kwargs):
        return boto3.client(client, **kwargs)
