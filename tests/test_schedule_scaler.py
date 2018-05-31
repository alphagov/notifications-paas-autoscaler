from unittest.mock import Mock, patch
import datetime

import pytest

import app
from app.schedule_scaler import ScheduleScaler

WORKDAY_1420 = datetime.datetime(2018, 3, 15, 14, 20, 00)
WORKDAY_1020 = datetime.datetime(2018, 3, 15, 10, 20, 00)
WEEKEND_1420 = datetime.datetime(2018, 3, 17, 14, 20, 00)
WEEKEND_1020 = datetime.datetime(2018, 3, 17, 10, 20, 00)


class TestScheduleScaler:
    def test_init_assigns_basic_values(self):
        input_attrs = {
            'min_instances': 1,
            'max_instances': 2,
            'threshold': 1500,
            'schedule': {'workdays': ['08:00-10:00'], 'scale_factor': 0.4}
        }
        schedule_scaler = ScheduleScaler(**input_attrs)

        assert schedule_scaler.min_instances == input_attrs['min_instances']
        assert schedule_scaler.max_instances == input_attrs['max_instances']
        assert schedule_scaler.threshold == input_attrs['threshold']
        assert schedule_scaler.scale_factor == 0.4

    @pytest.mark.parametrize('now,expected', [
        (WORKDAY_1420, 3),
        (WORKDAY_1020, 1),
        (WEEKEND_1420, 3),
        (WEEKEND_1020, 1),
    ], ids=[
        "Workday in schedule",
        "Workday off schedule",
        "Weekend in schedule",
        "Weekend off schedule",
    ])
    def test_get_desired_instance_count_schedule(self, now, expected):
        input_attrs = {
            'min_instances': 1,
            'max_instances': 5,
            'threshold': 1500,
            'schedule': {'workdays': ['13:00-15:00'], 'weekends': ['13:00-15:00'], 'scale_factor': 0.6}
        }
        schedule_scaler = ScheduleScaler(**input_attrs)
        schedule_scaler._now = Mock(return_value=now)
        assert schedule_scaler.get_desired_instance_count() == expected

    @pytest.mark.parametrize('enabled,expected', [
        (True, 3),
        (False, 1),
    ], ids=[
        "Scheduled scaler enabled",
        "Scheduled scaler disabled",
    ])
    def test_disabled_schedule(self, enabled, expected):
        input_attrs = {
            'min_instances': 1,
            'max_instances': 5,
            'threshold': 1500,
            'schedule': {'workdays': ['00:00-23:59'], 'weekends': ['00:00-23:59'], 'scale_factor': 0.6}
        }

        schedule_scaler = ScheduleScaler(**input_attrs)
        with patch.dict(app.config.config, {'SCALERS': {'SCHEDULE_SCALER_ENABLED': enabled}}):
            assert schedule_scaler.get_desired_instance_count() == expected
