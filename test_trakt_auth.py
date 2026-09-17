import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from trakt_auth import TraktAuth
from trakt_shows import TraktAuthError, TraktShows


def response(status=200, data=None, headers=None):
    result = Mock(status_code=status, headers=headers or {})
    result.json.return_value = data
    if status >= 400:
        result.raise_for_status.side_effect = requests.HTTPError(f'HTTP {status}')
    return result


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.token_path = Path(self.directory.name) / 'token.json'
        self.patch = patch.object(TraktAuth, 'TOKEN_FILE', self.token_path)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)
        self.auth = TraktAuth('client', 'secret', 'urn:ietf:wg:oauth:2.0:oob')
        self.tokens = {'access_token': 'new-access', 'refresh_token': 'new-refresh',
                       'created_at': 1700000000, 'expires_in': 604800}
        self.device = {'device_code': 'device', 'user_code': 'ABCD1234',
                       'verification_url': 'https://auth.trakt.tv/activate',
                       'interval': 5, 'expires_in': 60}
        self.now = 0

    def sleep(self, seconds):
        self.now += seconds

    def authenticate(self, replies):
        with patch('trakt_auth.requests.post', side_effect=replies) as post, \
             patch('trakt_auth.time.monotonic', side_effect=lambda: self.now), \
             patch('trakt_auth.time.sleep', side_effect=self.sleep) as sleep:
            result = self.auth.authenticate()
        return result, post, sleep

    def test_pending_then_success_saves_rotated_tokens(self):
        ok, post, sleep = self.authenticate([
            response(data=self.device), response(400), response(data=self.tokens)])
        self.assertTrue(ok)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(post.call_args.args[0], 'https://auth.trakt.tv/oauth/device/token')
        self.assertEqual(post.call_args.kwargs['json']['code'], 'device')
        self.assertEqual(post.call_args.kwargs['timeout'], 30)
        stored = json.loads(self.token_path.read_text())
        self.assertEqual(stored['refresh_token'], 'new-refresh')
        self.assertEqual(datetime.fromisoformat(stored['token_expiry']).timestamp(), 1700604800)
        self.assertEqual(TraktAuth('client', 'secret', 'redirect').access_token, 'new-access')

    def test_rate_limit_slows_polling(self):
        ok, _, sleep = self.authenticate([
            response(data=self.device), response(429, headers={'Retry-After': '12'}),
            response(data=self.tokens)])
        self.assertTrue(ok)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [5, 12])

    def test_terminal_errors_preserve_existing_file(self):
        self.token_path.write_text('existing session')
        for status in (404, 409, 410, 418, 500):
            with self.subTest(status=status):
                self.now = 0
                ok, _, _ = self.authenticate([response(data=self.device), response(status)])
                self.assertFalse(ok)
                self.assertEqual(self.token_path.read_text(), 'existing session')

    def test_expiry_stops_polling(self):
        self.device['expires_in'] = 10
        ok, post, _ = self.authenticate([response(data=self.device), response(400)])
        self.assertFalse(ok)
        self.assertEqual(post.call_count, 2)
        self.assertEqual(self.now, 10)

    def test_network_failure_preserves_session(self):
        self.token_path.write_text('existing session')
        ok, _, _ = self.authenticate([requests.Timeout('timeout')])
        self.assertFalse(ok)
        self.assertEqual(self.token_path.read_text(), 'existing session')

    def test_legacy_refresh_requires_authorization(self):
        self.auth.refresh_token = 'old-refresh'
        with patch('trakt_auth.requests.post', return_value=response(400, {'error': 'invalid_grant', 'error_description': 'session not found'})), \
             patch.object(self.auth, 'authenticate', return_value=True) as authenticate:
            self.assertTrue(self.auth.refresh_access_token())
            authenticate.assert_called_once()

    def test_transient_refresh_error_does_not_start_login(self):
        self.auth.refresh_token = 'old-refresh'
        for reply in (response(500), response(429), response(400, {'error': 'invalid_client'})):
            with patch('trakt_auth.requests.post', return_value=reply), \
                 patch.object(self.auth, 'authenticate') as authenticate:
                self.assertFalse(self.auth.refresh_access_token())
                authenticate.assert_not_called()
                self.assertEqual(self.auth.refresh_token, 'old-refresh')

    def test_refresh_saves_new_pair(self):
        self.auth.refresh_token = 'old-refresh'
        with patch('trakt_auth.requests.post', return_value=response(data=self.tokens)) as post:
            self.assertTrue(self.auth.refresh_access_token())
            self.assertEqual(post.call_args.args[0], 'https://auth.trakt.tv/oauth/token')
            self.assertEqual(post.call_args.kwargs['json']['refresh_token'], 'old-refresh')
        self.assertEqual(json.loads(self.token_path.read_text())['refresh_token'], 'new-refresh')

    def test_default_expiry_is_seven_days(self):
        del self.tokens['expires_in']
        self.auth._store_token(self.tokens)
        self.assertEqual(self.auth.token_expiry.timestamp(), 1700604800)

    def test_failed_atomic_replace_preserves_file(self):
        self.token_path.write_text('existing session')
        with patch.object(Path, 'replace', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                self.auth._store_token(self.tokens)
        self.assertEqual(self.token_path.read_text(), 'existing session')
        self.assertEqual(list(self.token_path.parent.iterdir()), [self.token_path])

    def test_corrupt_file_clears_partial_session(self):
        self.token_path.write_text(json.dumps({'access_token': 'old', 'token_expiry': 'invalid'}))
        self.auth.load_token()
        self.assertIsNone(self.auth.access_token)
        self.assertFalse(self.auth.is_token_valid())

    def test_failed_auth_blocks_api_request(self):
        with patch.object(self.auth, 'ensure_valid_token', return_value=False), \
             patch('trakt_shows.requests.request') as request:
            with self.assertRaises(TraktAuthError):
                TraktShows(self.auth).get_user_settings()
            request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
