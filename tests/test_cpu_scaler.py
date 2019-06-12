from unittest.mock import patch
import pytest

from app.cpu_scaler import CpuScaler

app_name = 'test-app'
min_instances = 1
max_instances = 4


@patch('app.base_scalers.PaasClient')
class TestCpuScaler:

    @pytest.mark.parametrize('input_attrs,expected_cpu', [
        ({}, 60),
        ({'threshold': 80}, 80),
    ], ids=[
        "Using default CPU threshold",
        "Using custom CPU threshold",
    ])
    def test_init_assigns_relevant_values(self, mock_paas_client, input_attrs, expected_cpu):
        cpu_scaler = CpuScaler(app_name, min_instances, max_instances, **input_attrs)

        assert cpu_scaler.app_name == app_name
        assert cpu_scaler.min_instances == min_instances
        assert cpu_scaler.max_instances == max_instances
        assert cpu_scaler.threshold == expected_cpu

    @pytest.mark.parametrize('cpus,expected', [
        ([50], 1),
        ([50, 50], 2),
        ([70], 2),
        ([70, 70], 3),
        ([30, 70], 2),
        ([100, 100], 4),
    ], ids=[
        "1 instance at 50% CPU",
        "2 instances at 50% CPU",
        "1 instances at 70% CPU",
        "2 instances at 70% CPU",
        "1 instance at 30% CPU, 1 instance at 70% CPU",
        "2 instances at 100% CPU",
    ])
    def test_get_desired_instance_count(self, mock_paas_client, cpus, expected):
        cpu_scaler = CpuScaler(app_name, min_instances, max_instances)

        mock_paas_client.return_value.get_app_stats.side_effect = [_get_app_stats(cpus)]

        assert cpu_scaler.get_desired_instance_count() == expected


# Create a dictionary that matches the schema of CF `stats` endpoint
def _get_app_stats(cpus):
    return {str(idx): {'stats': {'usage': {'cpu': cpu/100}}} for idx, cpu in enumerate(cpus)}
