"""
Modulo per gestire l'autenticazione OAuth con Trakt.tv
"""
import json
import requests
from pathlib import Path
from datetime import datetime, timedelta


class TraktAuth:
    """Gestisce l'autenticazione OAuth2 con Trakt.tv"""
    
    API_URL = 'https://api.trakt.tv'
    TOKEN_FILE = 'trakt_token.json'
    
    def __init__(self, client_id, client_secret, redirect_uri):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = None
        
        # Carica il token salvato se esiste
        self.load_token()
    
    def get_headers(self):
        """Restituisce gli header richiesti per le chiamate API"""
        headers = {
            'Content-Type': 'application/json',
            'trakt-api-version': '2',
            'trakt-api-key': self.client_id
        }
        
        if self.access_token:
            headers['Authorization'] = f'Bearer {self.access_token}'
        
        return headers
    
    def authenticate(self):
        """Avvia il flusso di autenticazione OAuth"""
        print("\n=== Autenticazione Trakt.tv ===\n")
        
        # Costruisci l'URL di autorizzazione
        auth_url = (
            f"https://trakt.tv/oauth/authorize?"
            f"response_type=code&"
            f"client_id={self.client_id}&"
            f"redirect_uri={self.redirect_uri}"
        )
        
        print(f"1. Visita questo URL nel tuo browser:")
        print(f"\n{auth_url}\n")
        print("2. Autorizza l'applicazione")
        print("3. Copia il codice che ricevi\n")
        
        code = input("Inserisci il codice di autorizzazione: ").strip()
        
        # Scambia il codice con un access token
        return self.get_token(code)
    
    def get_token(self, code):
        """Scambia il codice di autorizzazione con un access token"""
        url = f"{self.API_URL}/oauth/token"
        
        data = {
            'code': code,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': self.redirect_uri,
            'grant_type': 'authorization_code'
        }
        
        try:
            response = requests.post(url, json=data, headers={'Content-Type': 'application/json'})
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data['access_token']
            self.refresh_token = token_data['refresh_token']
            
            # Il token scade dopo 7 giorni (espresso in secondi)
            expires_in = token_data.get('expires_in', 7889238)  # default: 3 mesi
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in)
            
            self.save_token()
            print("\n[OK] Autenticazione completata con successo!\n")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"\n[ERRORE] Errore durante l'autenticazione: {e}\n")
            return False
    
    def refresh_access_token(self):
        """Aggiorna l'access token usando il refresh token"""
        if not self.refresh_token:
            print("Nessun refresh token disponibile. Ri-autentica l'app.")
            return self.authenticate()
        
        url = f"{self.API_URL}/oauth/token"
        
        data = {
            'refresh_token': self.refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': self.redirect_uri,
            'grant_type': 'refresh_token'
        }
        
        try:
            response = requests.post(url, json=data, headers={'Content-Type': 'application/json'})
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data['access_token']
            self.refresh_token = token_data['refresh_token']
            
            expires_in = token_data.get('expires_in', 7889238)
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in)
            
            self.save_token()
            print("[OK] Token aggiornato con successo!")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"[ERRORE] Errore durante l'aggiornamento del token: {e}")
            return self.authenticate()
    
    def is_token_valid(self):
        """Verifica se il token è ancora valido"""
        if not self.access_token or not self.token_expiry:
            return False
        
        # Controlla se il token scade nei prossimi 10 minuti
        return datetime.now() < (self.token_expiry - timedelta(minutes=10))
    
    def ensure_valid_token(self):
        """Assicura che ci sia un token valido, altrimenti lo aggiorna"""
        if not self.is_token_valid():
            if self.refresh_token:
                print("Token scaduto, aggiornamento in corso...")
                return self.refresh_access_token()
            else:
                print("Nessun token valido. Autenticazione necessaria.")
                return self.authenticate()
        return True
    
    def save_token(self):
        """Salva il token su file"""
        token_data = {
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'token_expiry': self.token_expiry.isoformat() if self.token_expiry else None
        }
        
        with open(self.TOKEN_FILE, 'w') as f:
            json.dump(token_data, f, indent=2)
    
    def load_token(self):
        """Carica il token dal file se esiste"""
        token_path = Path(self.TOKEN_FILE)
        
        if token_path.exists():
            try:
                with open(self.TOKEN_FILE, 'r') as f:
                    token_data = json.load(f)
                
                self.access_token = token_data.get('access_token')
                self.refresh_token = token_data.get('refresh_token')
                
                expiry_str = token_data.get('token_expiry')
                if expiry_str:
                    self.token_expiry = datetime.fromisoformat(expiry_str)
                
                print("[OK] Token caricato dal file")
            except Exception as e:
                print(f"[ATTENZIONE] Errore nel caricamento del token: {e}")
