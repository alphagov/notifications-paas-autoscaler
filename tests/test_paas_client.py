# flake8: noqa

from unittest.mock import patch, MagicMock, PropertyMock

from app.paas_client import PaasClient

ENV = {
    'CF_USERNAME': 'test_username',
    'CF_PASSWORD': 'test_password',
}

CONFIG = {
    'GENERAL': {
        'CF_API_URL': 'https://api.test.cf.com',
        'CF_ORG': 'notify',
        'CF_SPACE': 'test',
    }
}

class MockResponseObject():

    def __init__(self, **kwargs):
        self.lists = {
            'spaces': [],
            'apps': []
        }
        for k, v in kwargs.items():
            setattr(self, k, v)

    def set_items(self, item_type, values):
        for item in values:
            self.lists[item_type].append(item)

        return self

    def spaces(self):
        return self.lists['spaces']

    def apps(self):
        return self.lists['apps']

    def __getitem__(self, key):
        # to allow to retrieve attributes as a dict: obj['item']
        return getattr(self, key)


MockOrgs = [
    MockResponseObject(**{'entity': {'name': 'another-org'}}).set_items('spaces', [
        MockResponseObject(**{'entity': {'name': 'test'}}).set_items('apps', [
            MockResponseObject(**{'entity': {'name': 'app1', 'instances': 3}, 'metadata': {'guid': 'another-org-test-app1'}}),
            MockResponseObject(**{'entity': {'name': 'app2', 'instances': 4}, 'metadata': {'guid': 'another-org-test-app2'}}),
            MockResponseObject(**{'entity': {'name': 'app3', 'instances': 5}, 'metadata': {'guid': 'another-org-test-app3'}}),
        ]),
        MockResponseObject(**{'entity': {'name': 'another-space'}}).set_items('apps', [
            MockResponseObject(**{'entity': {'name': 'app4', 'instances': 5}, 'metadata': {'guid': 'another-org-another-space-app4'}}),
            MockResponseObject(**{'entity': {'name': 'app5', 'instances': 6}, 'metadata': {'guid': 'another-org-another-space-app5'}}),
            MockResponseObject(**{'entity': {'name': 'app6', 'instances': 7}, 'metadata': {'guid': 'another-org-another-space-app6'}}),
        ]),
    ]),
    MockResponseObject(**{'entity': {'name': 'notify'}}).set_items('spaces', [
        MockResponseObject(**{'entity': {'name': 'test'}}).set_items('apps', [
            MockResponseObject(**{'entity': {'name': 'app7', 'instances': 3}, 'metadata': {'guid': 'notify-test-app7'}}),
            MockResponseObject(**{'entity': {'name': 'app8', 'instances': 4}, 'metadata': {'guid': 'notify-test-app8'}}),
            MockResponseObject(**{'entity': {'name': 'app9', 'instances': 5}, 'metadata': {'guid': 'notify-test-app9'}}),
        ]),
        MockResponseObject(**{'entity': {'name': 'another-space'}}).set_items('apps', [
            MockResponseObject(**{'entity': {'name': 'app10', 'instances': 5}, 'metadata': {'guid': 'notify-another-space-app10'}}),
            MockResponseObject(**{'entity': {'name': 'app11', 'instances': 6}, 'metadata': {'guid': 'notify-another-space-app11'}}),
            MockResponseObject(**{'entity': {'name': 'app12', 'instances': 7}, 'metadata': {'guid': 'notify-another-space-app12'}}),
        ]),
    ]),
]

@patch.dict('app.config.config', CONFIG)
@patch.dict('os.environ', ENV)
@patch('app.paas_client.CloudFoundryClient')
class TestPaasClient:
    def test_paas_client_login_fails_waits_5_minutes(self, mock_paas_client_client, *args):
        mock_paas_client_client.return_value.init_with_user_credentials.side_effect = Exception("Login failed")
        with patch('app.paas_client.time') as mock_time:
            paas_client = PaasClient()
            paas_client.get_cloudfoundry_client()
            mock_time.sleep.assert_called_once_with(5 * 60)

    def test_get_paas_apps(self, mock_paas_client_client, *args):
        logged_in_mock_client = mock_paas_client_client.return_value
        logged_in_mock_client.organizations = MockOrgs
        paas_client = PaasClient()

        instances = paas_client.get_paas_apps()
        assert instances == {
            'app7': {'name': 'app7', 'instances': 3, 'guid': 'notify-test-app7'},
            'app8': {'name': 'app8', 'instances': 4, 'guid': 'notify-test-app8'},
            'app9': {'name': 'app9', 'instances': 5, 'guid': 'notify-test-app9'},
        }

    def test_logged_out_paas_client(self, mock_paas_client_client, *args):
        orgs_mock = PropertyMock(side_effect=[Exception("401  - no_token : no token provided"), MockOrgs])
        logged_in_mock_client = mock_paas_client_client.return_value
        type(logged_in_mock_client).organizations = orgs_mock
        paas_client = PaasClient()

        instances_first_run = paas_client.get_paas_apps()
        assert instances_first_run == {}
        assert paas_client.client is None

        # The paas client has been reset now
        instances_second_run = paas_client.get_paas_apps()
        assert paas_client.client is not None
        assert instances_second_run == {
            'app7': {'name': 'app7', 'instances': 3, 'guid': 'notify-test-app7'},
            'app8': {'name': 'app8', 'instances': 4, 'guid': 'notify-test-app8'},
            'app9': {'name': 'app9', 'instances': 5, 'guid': 'notify-test-app9'},
        }
