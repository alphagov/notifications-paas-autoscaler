from datetime import datetime
import json
import os

import psycopg2
import boto3
from notifications_utils.clients.statsd.statsd_client import StatsdClient


class BaseScaler:
    def __init__(self, min_instances, max_instances, threshold, **kwargs):
        self.min_instances = min_instances
        self.max_instances = max_instances
        self.threshold = threshold
        self.app_name = kwargs.get('app_name', 'missing_name')
        self.statsd_client = None

    def normalize_desired_instance_count(self, desired_instances):
        desired_instances = max(desired_instances, self.min_instances)
        desired_instances = min(desired_instances, self.max_instances)

        return desired_instances

    def init_statsd_client(self):
        self.statsd_client = StatsdClient()
        self.statsd_client.init_app(self)

    def get_statsd_client(self):
        if self.statsd_client is None:
            self.init_statsd_client()
        return self.statsd_client

    def gauge(self, metric_name, metric_value):
        self.get_statsd_client()
        self.statsd_client.gauge(metric_name, metric_value)

    def incr(self, metric_name, metric_value):
        self.get_statsd_client()
        self.statsd_client.incr(metric_name, metric_value)

    def _now(self):
        # to make mocking in tests easier
        return datetime.now()

    def get_desired_instance_count(self):
        raise NotImplementedError


class AwsBaseScaler(BaseScaler):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.aws_region = kwargs.get('aws_region') or os.environ.get('AWS_REGION', 'eu-west-1')
        self.aws_account_id = self._get_boto3_client('sts', region_name=self.aws_region).get_caller_identity()['Account']  # noqa

    def _get_boto3_client(self, client, **kwargs):
        return boto3.client(client, **kwargs)


class DbQueryScaler(BaseScaler):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_db_uri()

    def _init_db_uri(self):
        try:
            self.db_uri = json.loads(
                os.environ['VCAP_SERVICES'])['postgres'][0]['credentials']['uri']
        except KeyError:
            # TODO: log error
            self.db_uri = None

    def run_query(self):
        if self.query is None:
            raise Exception("No query has been defined")

        if self.db_uri is None:
            raise Exception("db service not configured")

        with psycopg2.connect(self.db_uri) as conn:
            with conn.cursor() as cursor:
                cursor.execute(self.query)
                items_count = cursor.fetchone()[0]
                return items_count
