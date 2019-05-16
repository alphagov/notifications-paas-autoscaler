import datetime
import math

import pytz

from app.base_scalers import BaseScaler
from app.config import config


class ScheduleScaler(BaseScaler):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.schedule = kwargs['schedule']
        self.scale_factor = self.schedule.get('scale_factor') or config['SCALERS']['DEFAULT_SCHEDULE_SCALE_FACTOR']

    def get_desired_instance_count(self):
        if not self._should_scale_on_schedule():
            return self.min_instances

        return self.normalize_desired_instance_count(int(math.ceil(self.max_instances * self.scale_factor)))

    def _should_scale_on_schedule(self):
        if not config['SCALERS']['SCHEDULE_SCALER_ENABLED']:
            return False

        now = self._now()
        now = pytz.utc.localize(now).astimezone(pytz.timezone("Europe/London")).replace(tzinfo=None)
        week_part = "workdays" if now.weekday() in range(5) else "weekends"  # Monday = 0, sunday = 6

        if week_part not in self.schedule:
            return False

        for time_range_string in self.schedule[week_part]:
            # convert the time range string to time objects
            start, end = [datetime.datetime.strptime(i, '%H:%M').time()
                          for i in time_range_string.split('-')]

            if start <= now.time() <= end:
                return True

        return False
