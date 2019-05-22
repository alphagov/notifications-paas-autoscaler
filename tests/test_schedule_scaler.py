from unittest.mock import patch
import datetime

from freezegun import freeze_time
import pytest
import pytz

import app
from app.schedule_scaler import ScheduleScaler

LOCAL_TIMEZONE = pytz.timezone('Europe/London')

# March 2018
# 15/3 = Thursday, 17/3 = Saturday

WORKDAY_1259_GMT = datetime.datetime(2018, 3, 15, 12, 59, 00)
WORKDAY_1301_GMT = datetime.datetime(2018, 3, 15, 13, 1, 00)
WORKDAY_1459_GMT = datetime.datetime(2018, 3, 15, 14, 59, 00)
WORKDAY_1501_GMT = datetime.datetime(2018, 3, 15, 15, 1, 00)

WEEKEND_1259_GMT = datetime.datetime(2018, 3, 17, 12, 59, 00)
WEEKEND_1301_GMT = datetime.datetime(2018, 3, 17, 13, 1, 00)
WEEKEND_1459_GMT = datetime.datetime(2018, 3, 17, 14, 59, 00)
WEEKEND_1501_GMT = datetime.datetime(2018, 3, 17, 15, 1, 00)


# June 2018
# 15/6 = Friday, 17/6 = Sunday

WORKDAY_1259_BST = datetime.datetime(2018, 6, 15, 12, 59, 00)
WORKDAY_1301_BST = datetime.datetime(2018, 6, 15, 13, 1, 00)
WORKDAY_1459_BST = datetime.datetime(2018, 6, 15, 14, 59, 00)
WORKDAY_1501_BST = datetime.datetime(2018, 6, 15, 15, 1, 00)

WEEKEND_1259_BST = datetime.datetime(2018, 6, 17, 12, 59, 00)
WEEKEND_1301_BST = datetime.datetime(2018, 6, 17, 13, 1, 00)
WEEKEND_1459_BST = datetime.datetime(2018, 6, 17, 14, 59, 00)
WEEKEND_1501_BST = datetime.datetime(2018, 6, 17, 15, 1, 00)


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
        (WORKDAY_1259_GMT, 1),
        (WORKDAY_1301_GMT, 3),
        (WORKDAY_1459_GMT, 3),
        (WORKDAY_1501_GMT, 1),
        (WEEKEND_1259_GMT, 1),
        (WEEKEND_1301_GMT, 3),
        (WEEKEND_1459_GMT, 3),
        (WEEKEND_1501_GMT, 1),
    ], ids=[
        "GMT workday just before schedule start",
        "GMT workday just after schedule start",
        "GMT workday just before schedule end",
        "GMT workday just after schedule end",
        "GMT weekend just before schedule start",
        "GMT weekend just after schedule start",
        "GMT weekend just before schedule end",
        "GMT weekend just after schedule end",
    ])
    def test_get_desired_instance_count_schedule_in_gmt(self, now, expected):
        input_attrs = {
            'min_instances': 1,
            'max_instances': 5,
            'threshold': 1500,
            'schedule': {'workdays': ['13:00-15:00'], 'weekends': ['13:00-15:00'], 'scale_factor': 0.6}
        }
        now = pytz.timezone('Europe/London').localize(now).astimezone(pytz.utc).replace(tzinfo=None)
        with freeze_time(now):
            schedule_scaler = ScheduleScaler(**input_attrs)
            assert schedule_scaler.get_desired_instance_count() == expected

    @pytest.mark.parametrize('now,expected', [
        (WORKDAY_1259_BST, 1),
        (WORKDAY_1301_BST, 3),
        (WORKDAY_1459_BST, 3),
        (WORKDAY_1501_BST, 1),
        (WEEKEND_1259_BST, 1),
        (WEEKEND_1301_BST, 3),
        (WEEKEND_1459_BST, 3),
        (WEEKEND_1501_BST, 1),
    ], ids=[
        "BST workday just before schedule start",
        "BST workday just after schedule start",
        "BST workday just before schedule end",
        "BST workday just after schedule end",
        "BST weekend just before schedule start",
        "BST weekend just after schedule start",
        "BST weekend just before schedule end",
        "BST weekend just after schedule end",
    ])
    def test_get_desired_instance_count_schedule_in_bst(self, now, expected):
        input_attrs = {
            'min_instances': 1,
            'max_instances': 5,
            'threshold': 1500,
            'schedule': {'workdays': ['13:00-15:00'], 'weekends': ['13:00-15:00'], 'scale_factor': 0.6}
        }

        now = pytz.timezone('Europe/London').localize(now).astimezone(pytz.utc).replace(tzinfo=None)
        with freeze_time(now):
            schedule_scaler = ScheduleScaler(**input_attrs)
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
