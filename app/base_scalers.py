import json
import logging
import os
from datetime import datetime, timedelta

import boto3
import psycopg2

from app.paas_client import PaasClient
from app.utils import get_statsd_client


class BaseScaler:
    def __init__(self, app_name, min_instances, max_instances):
        self.app_name = app_name
        self.min_instances = min_instances
        self.max_instances = max_instances
        self.statsd_client = get_statsd_client()

    def get_desired_instance_count(self):
        desired_instances = self._get_desired_instance_count()
        desired_instances = max(desired_instances, self.min_instances)
        desired_instances = min(desired_instances, self.max_instances)

        return desired_instances

    def gauge(self, metric_name, metric_value):
        self.statsd_client.gauge(metric_name, metric_value)

    def _now(self):
        # to make mocking in tests easier
        return datetime.utcnow()

    def _get_desired_instance_count(self):
        raise NotImplementedError


class AwsBaseScaler(BaseScaler):
    def __init__(self, app_name, min_instances, max_instances, aws_region=None):
        super().__init__(app_name, min_instances, max_instances)

        self.aws_region = aws_region or os.environ.get("AWS_REGION", "eu-west-1")
        self.aws_account_id = self._get_boto3_client("sts", region_name=self.aws_region).get_caller_identity()[
            "Account"
        ]  # noqa

    def _get_boto3_client(self, client, **kwargs):
        return boto3.client(client, **kwargs)


class PaasBaseScaler(BaseScaler):
    def __init__(self, app_name, min_instances, max_instances):
        super().__init__(app_name, min_instances, max_instances)
        self.paas_client = PaasClient()


class DbQueryScaler(BaseScaler):
    DB_CONNECTION_TIMEOUT = timedelta(seconds=60)

    def __init__(self, app_name, min_instances, max_instances):
        super().__init__(app_name, min_instances, max_instances)
        self._init_db_uri()
        self.last_db_error = datetime.min

    def _init_db_uri(self):
        if "SQLALCHEMY_DATABASE_URI" in os.environ:
            self.db_uri = os.environ["SQLALCHEMY_DATABASE_URI"].replace("postgresql://", "postgres://")
            return
        try:
            self.db_uri = json.loads(os.environ["VCAP_SERVICES"])["postgres"][0]["credentials"]["uri"]
        except KeyError as e:
            msg = str(e)
            logging.error(msg)
            self.db_uri = None

    def run_query(self):
        if datetime.utcnow() - self.last_db_error < self.DB_CONNECTION_TIMEOUT:
            return 0

        if self.query is None:
            msg = "No query has been defined"
            logging.critical(msg)
            raise Exception(msg)

        if self.db_uri is None:
            msg = "Database service not configured"
            logging.critical(msg)
            raise Exception(msg)

        try:
            with psycopg2.connect(self.db_uri) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(self.query)
                    items_count = cursor.fetchone()[0]
                    return items_count
        except psycopg2.OperationalError:
            # if there is exceptional load we might have run out of connections. try again in sixty seconds.
            logging.warning("Could not connect to database", exc_info=True)
            self.last_db_error = datetime.utcnow()

            # return 0 so that autoscaler can continue to look at other metrics.
            return 0
