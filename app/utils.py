import os

from notifications_utils.clients.statsd.statsd_client import StatsdClient

from app.config import config


class _StatsdWrapper():
    def __init__(self):
        self.config = {}
        self.config.update({
            'STATSD_ENABLED': config['GENERAL']['STATSD_ENABLED'],
            'NOTIFY_ENVIRONMENT': config['GENERAL']['CF_SPACE'],
            'NOTIFY_APP_NAME': 'autoscaler',
            'STATSD_HOST': os.environ['STATSD_HOST'],
            'STATSD_PORT': 8125,
        })
        self.statsd_client = StatsdClient()
        self.statsd_client.init_app(self)


_statsd_wrapper = _StatsdWrapper()


def get_statsd_client():
    return _statsd_wrapper.statsd_client
