from unittest.mock import patch
import json
import os

import pytest

from app.base_scalers import BaseScaler, AwsBaseScaler, DbQueryScaler

INPUT_ATTRS = {
    'min_instances': 1,
    'max_instances': 2,
    'threshold': 1500,
}


class TestBaseScaler:
    def test_init_assigns_basic_values(self):
        input_attrs = dict(INPUT_ATTRS, **{'extra_field_1': 'some_value'})
        base_scaler = BaseScaler(**input_attrs)

        assert base_scaler.min_instances == input_attrs['min_instances']
        assert base_scaler.max_instances == input_attrs['max_instances']
        assert base_scaler.threshold == input_attrs['threshold']

    @pytest.mark.parametrize('min_instances,max_instances,desired_instances,expected_instances', [
        (3, 5, 4, 4),
        (3, 5, 7, 5),
        (3, 5, 2, 3),
        (3, 5, -1, 3),
    ])
    def test_normalize_desired_instance_count(
            self, min_instances, max_instances, desired_instances, expected_instances):

        input_attrs = {
            'min_instances': min_instances,
            'max_instances': max_instances,
            'threshold': 1500,
            'extra_field_1': 'some_value'
        }
        base_scaler = BaseScaler(**input_attrs)

        assert base_scaler.normalize_desired_instance_count(desired_instances) == expected_instances


@patch('app.base_scalers.boto3')
class TestAwsBaseScaler:
    def test_init_assigns_basic_values(self, mock_boto3):
        input_attrs = dict(INPUT_ATTRS, **{'aws_region': 'eu-west-1'})
        aws_base_scaler = AwsBaseScaler(**input_attrs)

        assert aws_base_scaler.min_instances == input_attrs['min_instances']
        assert aws_base_scaler.max_instances == input_attrs['max_instances']
        assert aws_base_scaler.threshold == input_attrs['threshold']

    def test_aws_credentials_from_attributes(self, mock_boto3):
        input_attrs = dict(INPUT_ATTRS, **{'aws_region': 'eu-west-1'})
        aws_base_scaler = AwsBaseScaler(**input_attrs)

        assert aws_base_scaler.aws_region == input_attrs['aws_region']

    def test_aws_credentials_from_env_var(self, mock_boto3):
        with patch.dict(os.environ, {'AWS_REGION': 'us-west-1'}):
            aws_base_scaler = AwsBaseScaler(**INPUT_ATTRS)
            assert aws_base_scaler.aws_region == 'us-west-1'

    def test_aws_credentials_default_value(self, mock_boto3):
        aws_base_scaler = AwsBaseScaler(**INPUT_ATTRS)
        assert aws_base_scaler.aws_region == 'eu-west-1'

    def test_aws_account_id_from_boto_client(self, mock_boto3):
        mock_client = mock_boto3.client
        mock_client.return_value.get_caller_identity.return_value = {'Account': 123456}

        aws_base_scaler = AwsBaseScaler(**INPUT_ATTRS)
        assert aws_base_scaler.aws_region == 'eu-west-1'
        assert aws_base_scaler.aws_account_id == 123456
        mock_client.assert_called_with('sts', region_name='eu-west-1')


class TestDbQueryScaler:
    def test_db_uri_is_loaded(self):
        vcap_string = json.dumps({'postgres': [{'credentials': {'uri': 'test-db-uri'}}]})
        with patch.dict(os.environ, {'VCAP_SERVICES': vcap_string}):
            db_query_scaler = DbQueryScaler(**INPUT_ATTRS)
            assert db_query_scaler.db_uri == 'test-db-uri'
