from unittest.mock import patch
from datetime import datetime, timedelta
import json
import os

import psycopg2
import pytest
from freezegun import freeze_time

from app.base_scalers import BaseScaler, AwsBaseScaler, DbQueryScaler

app_name = 'test-app'
min_instances = 1
max_instances = 2


class TestBaseScaler:
    def test_init_assigns_basic_values(self):
        base_scaler = BaseScaler(app_name, min_instances, max_instances)

        assert base_scaler.app_name == app_name
        assert base_scaler.min_instances == min_instances
        assert base_scaler.max_instances == max_instances

    @pytest.mark.parametrize('min_instances,max_instances,desired_instances,expected_instances', [
        (3, 5, 4, 4),
        (3, 5, 7, 5),
        (3, 5, 2, 3),
        (3, 5, -1, 3),
    ], ids=[
        "Desired within limits",
        "Desired above upper limit",
        "Desired below lower limit",
        "Desired negative",
    ])
    def test_get_desired_instance_count_is_normalized(
            self, min_instances, max_instances, desired_instances, expected_instances):

        base_scaler = BaseScaler(app_name, min_instances, max_instances)
        with patch.object(base_scaler, '_get_desired_instance_count', side_effect=[desired_instances]):
            assert base_scaler.get_desired_instance_count() == expected_instances


@patch('app.base_scalers.boto3')
class TestAwsBaseScaler:
    def test_init_assigns_basic_values(self, mock_boto3):
        input_attrs = {'aws_region': 'eu-west-1'}
        aws_base_scaler = AwsBaseScaler(app_name, min_instances, max_instances, **input_attrs)

        assert aws_base_scaler.app_name == app_name
        assert aws_base_scaler.min_instances == min_instances
        assert aws_base_scaler.max_instances == max_instances

    def test_aws_credentials_from_attributes(self, mock_boto3):
        input_attrs = {'aws_region': 'eu-west-1'}
        aws_base_scaler = AwsBaseScaler(app_name, min_instances, max_instances, **input_attrs)

        assert aws_base_scaler.aws_region == input_attrs['aws_region']

    def test_aws_credentials_from_env_var(self, mock_boto3):
        with patch.dict(os.environ, {'AWS_REGION': 'us-west-1'}):
            aws_base_scaler = AwsBaseScaler(app_name, min_instances, max_instances)
            assert aws_base_scaler.aws_region == 'us-west-1'

    def test_aws_credentials_default_value(self, mock_boto3):
        aws_base_scaler = AwsBaseScaler(app_name, min_instances, max_instances)
        assert aws_base_scaler.aws_region == 'eu-west-1'

    def test_aws_account_id_from_boto_client(self, mock_boto3):
        mock_client = mock_boto3.client
        mock_client.return_value.get_caller_identity.return_value = {'Account': 123456}

        aws_base_scaler = AwsBaseScaler(app_name, min_instances, max_instances)
        assert aws_base_scaler.aws_region == 'eu-west-1'
        assert aws_base_scaler.aws_account_id == 123456
        mock_client.assert_called_with('sts', region_name='eu-west-1')


@pytest.fixture
def mock_db_connection():
    with patch('app.base_scalers.psycopg2.connect') as mock_db_connection:
        yield mock_db_connection


@freeze_time('2018-01-01 12:00')
class TestDbQueryScaler:
    def setup_method(self, method):
        vcap_string = json.dumps({'postgres': [{'credentials': {'uri': 'test-db-uri'}}]})
        with patch.dict(os.environ, {'VCAP_SERVICES': vcap_string}):
            self.db_query_scaler = DbQueryScaler(app_name, min_instances, max_instances)
            self.db_query_scaler.query = 'foo'

    def test_db_uri_is_loaded(self):
        assert self.db_query_scaler.db_uri == 'test-db-uri'

    def test_sets_last_failure_and_returns_0_if_exception(self, mock_db_connection):
        assert self.db_query_scaler.last_db_error == datetime.min

        mock_db_connection.side_effect = psycopg2.OperationalError
        res = self.db_query_scaler.run_query()

        assert res == 0
        assert self.db_query_scaler.last_db_error == datetime.utcnow()

    def test_skips_execution_if_recently_failed(self, mock_db_connection):
        self.db_query_scaler.last_db_error = datetime.utcnow() - timedelta(seconds=59)

        res = self.db_query_scaler.run_query()

        assert mock_db_connection.called is False
        assert res == 0

    def test_runs_query_if_failure_is_old(self, mock_db_connection):
        self.db_query_scaler.last_db_error = datetime.utcnow() - timedelta(seconds=61)

        self.db_query_scaler.run_query()

        assert mock_db_connection.called is True
