"""Autenticazione Trakt OAuth tramite device code e rinnovo dei token."""
import json
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests


class TraktAuth:
    API_URL = 'https://api.trakt.tv'
    AUTH_URL = 'https://auth.trakt.tv'
    TOKEN_FILE = Path(__file__).resolve().with_name('trakt_token.json')
    REQUEST_TIMEOUT = 30

    def __init__(self, client_id, client_secret, redirect_uri):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token = self.refresh_token = self.token_expiry = None
        self.load_token()

    def get_headers(self):
        headers = {'Content-Type': 'application/json', 'trakt-api-version': '2',
                   'trakt-api-key': self.client_id}
        if self.access_token:
            headers['Authorization'] = f'Bearer {self.access_token}'
        return headers

    def _auth_post(self, endpoint, data):
        return requests.post(
            f'{self.AUTH_URL}{endpoint}', json=data,
            headers={'Content-Type': 'application/json', 'trakt-api-version': '2',
                     'trakt-api-key': self.client_id}, timeout=self.REQUEST_TIMEOUT)

    def authenticate(self):
        """Mostra il codice da inserire sul sito e attende l'autorizzazione."""
        print('\n=== Autenticazione Trakt.tv ===\n')
        try:
            response = self._auth_post('/oauth/device/code', {'client_id': self.client_id})
            response.raise_for_status()
            device = response.json()
            interval = max(float(device['interval']), 1)
            deadline = time.monotonic() + float(device['expires_in'])
            data = {'code': device['device_code'], 'client_id': self.client_id,
                    'client_secret': self.client_secret}
            print(f"1. Visita: {device['verification_url']}")
            print(f"2. Accedi e inserisci questo codice sul sito: {device['user_code']}")
            print("3. Autorizza l'applicazione. Attendo la conferma automaticamente...\n")
            while time.monotonic() < deadline:
                time.sleep(min(interval, max(0, deadline - time.monotonic())))
                if time.monotonic() >= deadline:
                    break
                response = self._auth_post('/oauth/device/token', data)
                if response.status_code == 200:
                    self._store_token(response.json())
                    print('\n[OK] Autenticazione completata con successo!\n')
                    return True
                if response.status_code == 400:
                    continue  # Autorizzazione ancora in attesa.
                if response.status_code == 429:
                    retry_after = response.headers.get('Retry-After', '')
                    interval = max(interval + 5, float(retry_after) if retry_after.isdigit() else 0)
                    continue
                errors = {404: 'Codice non valido.', 409: 'Codice gia utilizzato.',
                          410: 'Codice scaduto.', 418: 'Autorizzazione negata.'}
                if response.status_code in errors:
                    print(f'[ERRORE] {errors[response.status_code]} Ripeti l\'autenticazione.')
                    return False
                response.raise_for_status()
                raise ValueError('Risposta inattesa dal servizio di autenticazione')
            print('[ERRORE] Codice scaduto. Ripeti l\'autenticazione.')
        except (requests.exceptions.RequestException, ValueError, KeyError, TypeError, OSError) as e:
            print(f'[ERRORE] Autenticazione non completata: {e}')
        return False

    def _store_token(self, token_data):
        access_token = token_data['access_token']
        refresh_token = token_data['refresh_token']
        if not access_token or not refresh_token:
            raise ValueError('Token mancanti nella risposta Trakt')
        created_at = float(token_data.get('created_at', time.time()))
        expires_in = float(token_data.get('expires_in', 7 * 24 * 60 * 60))
        expiry = datetime.fromtimestamp(created_at + expires_in)
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_expiry = expiry
        self.save_token()

    def get_token(self, code):
        """Supporto allo scambio di un authorization code gia ottenuto."""
        data = {'code': code, 'client_id': self.client_id,
                'client_secret': self.client_secret, 'redirect_uri': self.redirect_uri,
                'grant_type': 'authorization_code'}
        try:
            response = self._auth_post('/oauth/token', data)
            response.raise_for_status()
            self._store_token(response.json())
            print('[OK] Autenticazione completata con successo!')
            return True
        except (requests.exceptions.RequestException, ValueError, KeyError, TypeError, OSError) as e:
            print(f'[ERRORE] Autenticazione non completata: {e}')
            return False

    def refresh_access_token(self):
        if not self.refresh_token:
            return self.authenticate()
        data = {'refresh_token': self.refresh_token, 'client_id': self.client_id,
                'client_secret': self.client_secret, 'redirect_uri': self.redirect_uri,
                'grant_type': 'refresh_token'}
        try:
            response = self._auth_post('/oauth/token', data)
            if response.status_code == 400:
                error = response.json()
                if error.get('error') == 'invalid_grant':
                    print('[ATTENZIONE] Sessione Trakt scaduta, revocata o precedente alla '
                          'migrazione. Occorre autorizzare nuovamente l\'app.')
                    return self.authenticate()
            response.raise_for_status()
            self._store_token(response.json())
            print('[OK] Token aggiornato con successo!')
            return True
        except (requests.exceptions.RequestException, ValueError, KeyError, TypeError, OSError) as e:
            print(f'[ERRORE] Errore durante l\'aggiornamento del token: {e}')
            return False

    def is_token_valid(self):
        if not self.access_token or not self.token_expiry:
            return False
        return datetime.now(self.token_expiry.tzinfo) < self.token_expiry - timedelta(minutes=10)

    def ensure_valid_token(self):
        if self.is_token_valid():
            return True
        if self.refresh_token:
            print('Token scaduto, aggiornamento in corso...')
            return self.refresh_access_token()
        print('Nessun token valido. Autenticazione necessaria.')
        return self.authenticate()

    def save_token(self):
        """Sostituzione atomica: conserva il vecchio file se la scrittura fallisce."""
        token_data = {'access_token': self.access_token, 'refresh_token': self.refresh_token,
                      'token_expiry': self.token_expiry.isoformat() if self.token_expiry else None}
        token_path = Path(self.TOKEN_FILE)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                             dir=token_path.parent, delete=False) as f:
                temporary_path = Path(f.name)
                json.dump(token_data, f, indent=2)
            temporary_path.replace(token_path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def load_token(self):
        token_path = Path(self.TOKEN_FILE)
        if token_path.exists():
            try:
                token_data = json.loads(token_path.read_text(encoding='utf-8'))
                self.access_token = token_data.get('access_token')
                self.refresh_token = token_data.get('refresh_token')
                expiry = token_data.get('token_expiry')
                if expiry:
                    self.token_expiry = datetime.fromisoformat(expiry)
                print('[OK] Token caricato dal file')
            except (OSError, ValueError, TypeError, AttributeError) as e:
                self.access_token = self.refresh_token = self.token_expiry = None
                print(f'[ATTENZIONE] Errore nel caricamento del token: {e}')


if __name__ == '__main__':
    import config
    try:
        auth = TraktAuth(config.CLIENT_ID, config.CLIENT_SECRET, config.REDIRECT_URI)
        raise SystemExit(0 if auth.authenticate() else 1)
    except KeyboardInterrupt:
        print('\nAutenticazione annullata.')
        raise SystemExit(1)
