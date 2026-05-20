# PyTrakt - Gestione Show Trakt.tv

Script Python per interagire con l'API di Trakt.tv e visualizzare informazioni sui tuoi show preferiti.

## Caratteristiche

- ✅ Autenticazione OAuth2 con Trakt.tv
- 📺 Visualizzazione show preferiti
- 📋 Gestione watchlist
- 🎬 Tracciamento show guardati
- 🔍 Ricerca show
- 🔥 Show popolari e di tendenza
- 💾 Salvataggio automatico del token di autenticazione
- 📥 Import massivo di show visti da CSV/JSON con matching automatico

## Installazione

1. **Clona o scarica il progetto**

2. **Installa le dipendenze**
   ```bash
   pip install -r requirements.txt
   ```

3. **Crea un'app su Trakt.tv**
   - Vai su https://trakt.tv/oauth/applications/new
   - Compila i campi:
     - Name: scegli un nome per la tua app
     - Redirect uri: `urn:ietf:wg:oauth:2.0:oob`
     - Permissions: seleziona quelle necessarie
   - Salva e copia il **Client ID** e **Client Secret**

4. **Configura le credenziali**
   ```bash
   # Copia il file di esempio
   cp config_example.py config.py
   
   # Modifica config.py e inserisci le tue credenziali
   ```

## Avvio rapido

### Windows

1. **Apri PowerShell nella cartella del progetto**
2. **Crea e attiva virtualenv**
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   copy config_example.py config.py
   ```
3. **Configura `config.py`** con credenziali Trakt e Telegram
4. **Prima autenticazione Trakt**
   ```powershell
   python monitor.py
   ```
5. **Esecuzione**
   - menu principale: `python main.py`
   - monitor notifiche: `python monitor.py`

6. **Task Scheduler**
   - utilizza `Task Scheduler` se vuoi avviare l'app automaticamente

### Raspberry / Linux

1. **Prepara ambiente**
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   cp config_example.py config.py
   ```
2. **Configura `config.py`**
3. **Prima autenticazione Trakt**
   ```bash
   .venv/bin/python monitor.py
   ```
4. **Esecuzione manuale**
   - menu principale: `.venv/bin/python main.py`
   - monitor notifiche: `.venv/bin/python monitor.py`

## Telegram Bot (setup rapido)

1. Su Telegram cerca `@BotFather`
2. Esegui `/newbot` e completa nome + username del bot
3. Copia il token fornito da BotFather (`TELEGRAM_BOT_TOKEN`)
4. Scrivi almeno un messaggio al tuo bot (es. `/start`)
5. Recupera il tuo `chat_id`:
   - metodo rapido: apri `https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getUpdates`
   - cerca il campo `chat.id` nel JSON
6. Inserisci in `config.py`:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
7. Test invio:
   ```bash
   python monitor.py --test-telegram
   ```

## Deploy su Raspberry / Linux (systemd)

Percorso consigliato:
- progetto: `/opt/tvtracker`
- venv: `/opt/tvtracker/.venv`

1. **Clona repo e prepara ambiente**
   ```bash
   sudo mkdir -p /opt/tvtracker
   sudo chown -R pi:pi /opt/tvtracker
   git clone <URL_REPO> /opt/tvtracker
   cd /opt/tvtracker
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   cp config_example.py config.py
   ```

2. **Configura `config.py`**
   - inserisci `CLIENT_ID`, `CLIENT_SECRET`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
   - imposta `POLLING_INTERVAL_MINUTES` a un valore `> 0` (es. `15`)

3. **Prima autenticazione Trakt**
   ```bash
   .venv/bin/python monitor.py
   ```
   Segui la procedura OAuth a terminale. Verrà creato `trakt_token.json`.

4. **Installa servizio systemd**
   Nel repository trovi gia il file `tvtracker.service` pronto come base.
   Va copiato in `/etc/systemd/system/` e adattato (utente e path) al tuo sistema.

   ```bash
   sudo cp tvtracker.service /etc/systemd/system/tvtracker.service
   sudo systemctl daemon-reload
   sudo systemctl enable tvtracker.service
   sudo systemctl start tvtracker.service
   ```

   Se devi adattare utente o path, modifica prima il servizio:
   ```bash
   sudo nano /etc/systemd/system/tvtracker.service
   ```
   Campi da verificare:
   - `User=pi` (nome utente)
   - `WorkingDirectory=/opt/tvtracker` (percorso)
   - `ExecStart=/opt/tvtracker/.venv/bin/python /opt/tvtracker/monitor.py` (comando di avvio)

   Dopo ogni modifica:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart tvtracker.service
   ```

5. **Verifica stato e log**
   ```bash
   systemctl status tvtracker.service
   journalctl -u tvtracker.service -f
   ```

## Utilizzo

Esegui lo script principale:

```bash
python main.py
```

### Monitor notifiche Telegram (status + next_air)

Per ricevere notifiche automatiche quando:
- uno show passa a `returning series` o `in production`
- `next_air` diventa una data concreta (da `TBA/None` a timestamp)

usa:

```bash
python monitor.py
```

Per verificare solo il bot Telegram (senza monitor Trakt):

```bash
python monitor.py --test-telegram
```

### Import massivo show già visti

Per importare molti show già visti senza farlo a mano su Trakt:

```bash
python import_watched.py miei_show.csv
```

Oppure da file testo con un titolo per riga:

```bash
python import_watched.py show.txt
```

Il comando sopra esegue un `dry-run`:
- cerca i titoli su Trakt
- accetta solo i match considerati sicuri
- per default espande ogni show negli episodi già andati in onda
- usa `first_aired` di ogni episodio come `watched_at`
- scrive un report JSON con match, ambigui e non trovati

Quando il report è corretto, esegui davvero l'import:

```bash
python import_watched.py miei_show.csv --apply
```

Se vuoi invece marcare lo show senza ricostruire le date episodio per episodio:

```bash
python import_watched.py miei_show.csv --apply --date-mode now
```

Formati supportati:
- `CSV`
- `TXT` (un titolo per riga)
- `JSON`

Campi riconosciuti automaticamente:
- titolo: `title`, `name`, `show`, `series`, `series_title`
- anno: `year`, `release_year`
- data vista/uscita: `watched_at`, `watched_on`, `viewed_at`, `first_aired`, `released`, `release_date`

Esempio CSV:

```csv
title,year,watched_at
Dark,2017,2017-12-01
Severance,2022,2022-02-18
```

Note:
- senza `--apply` non viene inviato nulla a Trakt
- i casi ambigui restano nel report per revisione manuale
- `--date-mode release` è il default ed è il più vicino alla procedura manuale "on release date"
- `--date-mode now` marca direttamente lo show e lascia a Trakt la data automatica

Configura in `config.py` (o come variabili ambiente):

```python
TELEGRAM_BOT_TOKEN = "123456:ABCDEF..."
TELEGRAM_CHAT_ID = "123456789"
POLLING_INTERVAL_MINUTES = 0  # 0 = esecuzione singola, >0 loop continuo

# Timezone usata per mostrare date/orari nelle notifiche Telegram
# https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
TIMEZONE = "Europe/Rome"
```

Lo script crea/aggiorna `status_cache.json` con fingerprint per show:
- `status`
- `next_air`
- `next_episode_code` (es. `S01E01`)
- `updated_at`

Nota: al primo run popola la cache e non invia notifiche retroattive.

Al primo avvio ti verrà chiesto di autenticarti:
1. Visita l'URL mostrato nel browser
2. Autorizza l'applicazione
3. Copia il codice ricevuto
4. Incollalo nel terminale

Il token verrà salvato automaticamente in `trakt_token.json` per gli usi successivi.

## Menu Opzioni

1. **Visualizza i miei show preferiti** - Mostra i tuoi top 50 show preferiti
2. **Visualizza la mia watchlist** - Show che stai seguendo
3. **Visualizza gli show che ho già visto** - Cronologia completa
4. **Cerca uno show** - Ricerca per nome
5. **Show più popolari** - I più votati su Trakt
6. **Show di tendenza** - I più visti nelle ultime 24 ore
7. **Prossime uscite** - Prossime uscite

## Struttura File

```
PyTrakt/
├── main.py               # Script principale
├── import_watched.py     # Import massivo show visti
├── trakt_auth.py         # Gestione autenticazione OAuth
├── trakt_shows.py        # Interazione con API show
├── config_example.py     # Template configurazione
├── config.py             # Configurazione (da creare)
├── trakt_token.json      # Token salvato (generato automaticamente)
├── requirements.txt      # Dipendenze Python
├── .gitignore            # File da ignorare in git
├── tvtracker.service     # Servizio systemd
├── status_cache.json     # Cache con fingerprint per show (generato automaticamente)
└── README.md             # Questo file
```

## API Endpoints Utilizzati

- `/users/settings` - Informazioni utente
- `/sync/favorites/shows` - Show preferiti
- `/sync/watchlist/shows` - Watchlist
- `/sync/watched/shows` - Show guardati
- `/shows/popular` - Show popolari
- `/shows/trending` - Show di tendenza
- `/search/text` - Ricerca show

## Note

- Il token di autenticazione ha una validità di 7 giorni
- Lo script aggiorna automaticamente il token quando necessario
- Le informazioni includono: titolo, anno, rating, generi, descrizione, link IMDB/TMDB
- Supporta gli show con stato VIP (richiede account Trakt VIP)

## Troubleshooting

**Errore 401 Unauthorized**
- Verifica che CLIENT_ID e CLIENT_SECRET siano corretti
- Ri-autentica l'applicazione eliminando `trakt_token.json`

**Errore 429 Rate Limit**
- Hai superato il limite di richieste (1000 ogni 5 minuti)
- Aspetta qualche minuto prima di riprovare

**Nessuno show trovato**
- Assicurati di aver aggiunto show ai preferiti su https://trakt.tv
- Verifica che l'account sia pubblico o che l'autenticazione sia corretta

## Risorse

- [Trakt API Documentation](https://trakt.docs.apiary.io/)
- [Creare un'app Trakt](https://trakt.tv/oauth/applications/new)
- [Trakt Website](https://trakt.tv)

## Licenza

Questo progetto è fornito "as is" per scopi educativi e personali.