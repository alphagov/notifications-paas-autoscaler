from main import AutoScaler


class TestAutoscaler:
    def test_should_scale_on_schedule(self):
        autoscaler = AutoScaler([], [], [])
