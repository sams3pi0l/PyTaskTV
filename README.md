# PyTaskTV - Gestione Show Trakt.tv

Script Python per interagire con l'API di Trakt.tv e visualizzare informazioni sui tuoi show preferiti.

## Caratteristiche

- ✅ Autenticazione OAuth2 tramite device code, anche da server senza browser
- 📺 Visualizzazione show preferiti
- 📋 Gestione watchlist
- 🎬 Tracciamento show guardati
- 🔍 Ricerca show
- 🔥 Show popolari e di tendenza
- 💾 Salvataggio e rinnovo automatico dei token di autenticazione
- 📥 Import massivo di show visti da CSV/TXT/JSON con matching automatico

## Installazione

1. **Clona o scarica il progetto**

2. **Installa le dipendenze**
   ```bash
   pip install -r requirements.txt
   ```

3. **Crea un'app su Trakt.tv**
   - Vai su https://app.trakt.tv/settings/apps
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
   python trakt_auth.py
   ```
5. **Esecuzione**
   - menu principale: `python main.py`
   - monitor notifiche: `python monitor.py`

6. **Task Scheduler**
   - utilizza `Task Scheduler` se vuoi avviare l'app automaticamente

### Linux

1. **Prepara ambiente**
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   cp config_example.py config.py
   ```
2. **Configura `config.py`**
3. **Prima autenticazione Trakt**
   ```bash
   .venv/bin/python trakt_auth.py
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

## Autenticazione Trakt

Esegui `python trakt_auth.py` (su Linux: `.venv/bin/python trakt_auth.py`) per collegare l'account o ripetere l'autenticazione, anche se esiste già un token salvato. Il comando esegue solo il login, senza avviare il monitor o inviare notifiche Telegram.

1. Apri l'URL visualizzato nel terminale.
2. Accedi a Trakt e inserisci **sul sito** il codice mostrato dal programma.
3. Autorizza l'applicazione.
4. Lascia aperto il terminale: il programma riceve automaticamente la conferma e salva i token.

Se lavori via SSH su una VPS, puoi aprire l'URL dal browser del tuo PC o telefono: non serve un browser sul server. Se il codice scade o l'autorizzazione viene negata, esegui nuovamente il comando.

Il file `trakt_token.json` viene letto e scritto nella cartella del progetto, indipendentemente dalla directory di avvio. Non occorre eliminarlo prima di ripetere il login: viene sostituito dopo aver ricevuto i nuovi token. Il rinnovo automatico salva sia il nuovo access token sia il nuovo refresh token.

OAuth usa `https://auth.trakt.tv`; le richieste agli show usano `https://api.trakt.tv`. Il flusso device non richiede di copiare un codice dal browser al terminale né di configurare un server di callback. Mantieni `REDIRECT_URI` coerente con le impostazioni della tua app Trakt: viene ancora usato nello scambio e nel rinnovo dei token.

## Deploy su Linux (systemd)

I comandi seguenti usano `/opt/tvtracker` come cartella del progetto e il suo ambiente virtuale `.venv`. Eseguili con l'utente che eseguirà il servizio, usando `sudo` solo dove indicato.

1. **Clona il repository e prepara l'ambiente**

   ```bash
   sudo mkdir -p /opt/tvtracker
   sudo chown "$(id -un):$(id -gn)" /opt/tvtracker
   git clone https://github.com/sams3pi0l/PyTaskTV.git /opt/tvtracker
   cd /opt/tvtracker
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   cp config_example.py config.py
   ```

2. **Configura `config.py`**

   - Inserisci `CLIENT_ID`, `CLIENT_SECRET`, `REDIRECT_URI`, `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`.
   - Imposta `POLLING_INTERVAL_MINUTES` a un valore maggiore di zero (es. `15`) per il monitor continuo.
   - Imposta `TIMEZONE`, ad esempio `Europe/Rome`.

3. **Completa l'autenticazione prima di avviare il servizio**

   ```bash
   .venv/bin/python trakt_auth.py
   ```

   Segui la procedura descritta in [Autenticazione Trakt](#autenticazione-trakt). Verrà salvato `trakt_token.json`.

4. **Personalizza e installa il servizio systemd**

   Il file `tvtracker.service_sample` è un modello: **deve essere modificato in base al tuo utente, ai tuoi percorsi e alle tue impostazioni prima di avviare il servizio**. Copialo con il nome `tvtracker.service`:

   ```bash
   sudo cp tvtracker.service_sample /etc/systemd/system/tvtracker.service
   sudo nano /etc/systemd/system/tvtracker.service
   ```

   Verifica questi campi:

   - `User=ubuntu`: sostituisci `ubuntu` con l'utente che ha configurato il progetto e completato il login.
   - `WorkingDirectory=/opt/tvtracker`: cartella del progetto, usata anche per la cache del monitor.
   - `ExecStart=/opt/tvtracker/.venv/bin/python /opt/tvtracker/monitor.py`: percorsi assoluti dell'interprete e dello script.
   - `ReadWritePaths=/opt/tvtracker`: cartella in cui il servizio deve poter aggiornare token e cache; l'utente deve avere i permessi di scrittura.
   - `ProtectHome=true`: impedisce l'accesso alle cartelle home; con questa impostazione mantieni progetto e ambiente virtuale fuori da `/home` e `/root`, come nell'esempio.

   Dopo aver salvato le impostazioni:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now tvtracker.service
   ```

   Dopo modifiche successive al file del servizio, esegui `sudo systemctl daemon-reload` e `sudo systemctl restart tvtracker.service`.

5. **Verifica stato e log**

   ```bash
   systemctl status tvtracker.service
   sudo journalctl -u tvtracker.service -f
   ```

### Aggiornamento e nuova autenticazione sulla VPS

Ferma il servizio prima di aggiornare il codice o rigenerare i token. Dalla cartella del progetto, come utente del servizio:

```bash
sudo systemctl stop tvtracker.service
cd /opt/tvtracker
git pull --ff-only
.venv/bin/pip install -r requirements.txt
```

`git pull` scarica solo le modifiche già pubblicate nel repository remoto. Se stai distribuendo modifiche locali, copia sulla VPS i file aggiornati al posto del comando `git pull`, preservando `config.py`, `trakt_token.json` e `status_cache.json`.

Se serve una nuova autorizzazione, esegui:

```bash
.venv/bin/python trakt_auth.py
```

Dopo l'aggiornamento e l'eventuale login riuscito:

```bash
sudo systemctl start tvtracker.service
sudo journalctl -u tvtracker.service -n 50 --no-pager
```

Un aggiornamento del solo codice Python non richiede `daemon-reload`. Se aggiorni anche il modello systemd, riporta le modifiche nel servizio installato mantenendo le tue impostazioni, poi esegui `daemon-reload` prima di avviarlo.

### Server principale, fallback e test

Mantieni un solo monitor attivo per evitare notifiche duplicate. Puoi usare la VPS come server principale, un secondo server Linux come fallback e Windows per i test.

Per tenere fermo il fallback anche dopo un riavvio:

```bash
sudo systemctl disable --now tvtracker.service
```

Quando serve il fallback, assicurati che il monitor principale sia fermo, aggiorna il codice sul server di riserva e, se necessario, esegui `.venv/bin/python trakt_auth.py`. Avvia quindi il servizio con `sudo systemctl start tvtracker.service`; con `start` rimane disabilitato l'avvio automatico al boot.

Ogni installazione deve avere una propria autorizzazione: non copiare `trakt_token.json` tra macchine. I refresh token sono monouso e una sessione condivisa può causare conflitti al rinnovo. Evita anche di eseguire contemporaneamente il servizio e una copia manuale del programma nella stessa installazione.

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
PyTaskTV/
├── main.py               # Script principale
├── monitor.py            # Monitor e notifiche Telegram
├── import_watched.py     # Import massivo show visti
├── trakt_auth.py         # Gestione autenticazione OAuth
├── trakt_shows.py        # Interazione con API show
├── config_example.py     # Template configurazione
├── config.py             # Configurazione (da creare)
├── trakt_token.json      # Token salvato (generato automaticamente)
├── requirements.txt      # Dipendenze Python
├── .gitignore            # File da ignorare in git
├── tvtracker.service_sample # Modello systemd da personalizzare
├── test_trakt_auth.py     # Test locali dell'autenticazione (opzionali)
├── status_cache.json     # Cache con fingerprint per show (generato automaticamente)
└── README.md             # Questo file
```

## Test dell'autenticazione

`test_trakt_auth.py` contiene test con risposte Trakt simulate: non usa le credenziali reali e non modifica la sessione salvata. Per eseguirli dall'ambiente virtuale:

```bash
python -m unittest test_trakt_auth -v
```

Su Linux usa `.venv/bin/python -m unittest test_trakt_auth -v`. Il file serve per verificare modifiche al codice; non è necessario per eseguire l'applicazione e non occorre copiarlo sui server.

## API Endpoints Utilizzati

- `/oauth/device/code` - Generazione del codice di attivazione
- `/oauth/device/token` - Conferma dell'autorizzazione
- `/oauth/token` - Scambio e rinnovo dei token
- `/users/settings` - Informazioni utente
- `/sync/favorites/shows` - Show preferiti
- `/sync/watchlist/shows` - Watchlist
- `/sync/watched/shows` - Show guardati
- `/shows/popular` - Show popolari
- `/shows/trending` - Show di tendenza
- `/search/text` - Ricerca show

## Note

- La scadenza del token viene calcolata dai dati restituiti da Trakt; in assenza di `expires_in` il programma usa 7 giorni
- Lo script rinnova il token quando scade o mancano meno di 10 minuti alla scadenza
- Se l'autenticazione fallisce, le richieste API dipendenti vengono bloccate
- Le informazioni includono: titolo, anno, rating, generi, descrizione, link IMDB/TMDB
- Supporta gli show con stato VIP (richiede account Trakt VIP)

## Troubleshooting

**Errore 401 Unauthorized**

- Verifica che CLIENT_ID e CLIENT_SECRET siano corretti
- Ferma il monitor e ri-autentica con `python trakt_auth.py` (su Linux: `.venv/bin/python trakt_auth.py`); non serve eliminare il token
- I vecchi refresh token precedenti alla migrazione Trakt possono restituire `invalid_grant`: serve una nuova autorizzazione
- OAuth usa `https://auth.trakt.tv`; le altre API usano `https://api.trakt.tv`
- `trakt_token.json` viene letto e scritto nella cartella del progetto, anche avviando da un'altra cartella
- Esegui una sola istanza alla volta: i refresh token sono monouso; non condividere una copia della sessione tra macchine

**Il browser non mostra il codice dopo il login**

- Il nuovo flusso device mostra il codice nel terminale e lo richiede sul sito
- Avvia `python trakt_auth.py` per collegare nuovamente l'account senza avviare il monitor Telegram
- Il file esistente viene sostituito solo dopo aver ricevuto i nuovi token

**Errore 429 Rate Limit**

- Trakt ha applicato un limite alle richieste; durante il login il programma rallenta il polling
- Aspetta qualche minuto prima di riprovare

**Nessuno show trovato**

- Assicurati di aver aggiunto show ai preferiti su https://trakt.tv
- Verifica che l'account sia pubblico o che l'autenticazione sia corretta

## Risorse

- [Trakt API Documentation](https://docs.trakt.tv/)
- [Autenticazione e migrazione dei refresh token](https://docs.trakt.tv/docs/authentication-oauth)
- [Creare un'app Trakt](https://app.trakt.tv/settings/apps)
- [Trakt Website](https://trakt.tv)

## Licenza

Questo progetto è fornito "as is" per scopi educativi e personali.
