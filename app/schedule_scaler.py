import datetime
import math
import os

from app.base_scalers import BaseScaler


class ScheduleScaler(BaseScaler):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.schedule = kwargs['schedule']
        self.scale_factor = self.schedule.get('scale_factor') or os.environ.get('SCHEDULE_SCALE_FACTOR', 0.1)

    def estimate_instance_count(self):
        if not self._should_scale_on_schedule():
            return self.min_instances

        return int(math.ceil(self.max_instances * self.scale_factor))

    def _should_scale_on_schedule(self):
        now = self._now()
        week_part = "workdays" if now.weekday() in range(5) else "weekends"  # Monday = 0, sunday = 6

        if week_part not in self.schedule:
            return False

        for time_range_string in self.schedule[week_part]:
            # convert the time range string to time objects
            start, end = [datetime.datetime.strptime(i, '%H:%M').time() for i in time_range_string.split('-')]

            if datetime.datetime.combine(now, start) <= now <= datetime.datetime.combine(now, end):
                return True

        return False
