# Trakt API Configuration
# Rinomina questo file in config.py e inserisci le tue credenziali

# Crea un'app su https://trakt.tv/oauth/applications/new
CLIENT_ID = 'your_trakt_client_id'
CLIENT_SECRET = 'your_trakt_client_secret'

# L'URL di redirect deve essere lo stesso che hai impostato nell'app Trakt
REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'

# Il tuo username Trakt (opzionale, viene rilevato automaticamente)
USERNAME = 'your_trakt_username'

# Telegram monitor (monitor.py)
TELEGRAM_BOT_TOKEN = '123456789:replace_with_real_bot_token'
TELEGRAM_CHAT_ID = '123456789'

# 0 = esecuzione singola (consigliato con Task Scheduler su Windows)
# >0 = loop continuo ogni N minuti (consigliato con systemd su Raspberry)
POLLING_INTERVAL_MINUTES = 60

# Timezone usata per mostrare date/orari nelle notifiche Telegram
# https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
TIMEZONE = "Europe/Rome"
