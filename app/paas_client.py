import os
import time
import logging

from cloudfoundry_client.client import CloudFoundryClient

from app.config import config


class PaasClient:
    def __init__(self):
        self.client = None

        self.org = config['GENERAL']['CF_ORG']
        self.space = config['GENERAL']['CF_SPACE']
        self.api_url = config['GENERAL']['CF_API_URL']

        self.username = os.environ['CF_USERNAME']
        self.password = os.environ['CF_PASSWORD']

    def update(self, guid, instances):
        self.client.apps._update(guid, {'instances': instances})

    def get_cloudfoundry_client(self):
        if self.client is None:
            proxy = dict(http=os.environ.get('HTTP_PROXY', ''), https=os.environ.get('HTTPS_PROXY', ''))
            client = CloudFoundryClient(self.api_url, proxy=proxy)
            try:
                client.init_with_user_credentials(self.username, self.password)
                self.client = client
            except BaseException as e:
                msg = 'Failed to authenticate: {}, waiting 5 minutes and exiting'.format(str(e))
                logging.error(msg)
                # The sleep is added to avoid automatically banning the user for too many failed login attempts
                time.sleep(5 * 60)

        return self.client

    def get_paas_apps(self):
        instances = {}

        client = self.get_cloudfoundry_client()
        if client is not None:
            try:
                for organization in self.client.organizations:
                    if organization['entity']['name'] != self.org:
                        continue
                    for space in organization.spaces():
                        if space['entity']['name'] != self.space:
                            continue
                        for app in space.apps():
                            instances[app['entity']['name']] = {
                                'name': app['entity']['name'],
                                'guid': app['metadata']['guid'],
                                'instances': app['entity']['instances']
                            }
            except BaseException as e:
                msg = 'Failed to get stats for app {}: {}'.format(app['entity']['name'], str(e))
                logging.error(msg)
                self.reset_cloudfoundry_client()

        return instances

    def reset_cloudfoundry_client(self):
        self.cf_client = None
