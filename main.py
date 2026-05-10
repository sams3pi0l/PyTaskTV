#!/usr/bin/env python3
"""
Script principale per ottenere informazioni sugli show preferiti da Trakt.tv
"""
import sys
from pathlib import Path
from datetime import datetime

try:
    import config
except ImportError:
    print("\n⚠ File config.py non trovato!")
    print("1. Rinomina config_example.py in config.py")
    print("2. Crea un'app su https://trakt.tv/oauth/applications/new")
    print("3. Inserisci CLIENT_ID e CLIENT_SECRET nel file config.py\n")
    sys.exit(1)

from trakt_auth import TraktAuth
from trakt_shows import TraktShows, format_show_info, display_shows_summary


def main():
    """Funzione principale"""
    print("\n" + "="*70)
    print("  TRAKT.TV - GESTIONE SHOW PREFERITI")
    print("="*70)
    
    # Inizializza l'autenticazione
    auth = TraktAuth(
        client_id=config.CLIENT_ID,
        client_secret=config.CLIENT_SECRET,
        redirect_uri=config.REDIRECT_URI
    )
    
    # Verifica se dobbiamo autenticarci
    if not auth.access_token:
        print("\nPrima autenticazione necessaria...")
        if not auth.authenticate():
            print("Autenticazione fallita. Uscita.")
            sys.exit(1)
    else:
        # Assicurati che il token sia valido
        auth.ensure_valid_token()
    
    # Inizializza il gestore degli show
    shows = TraktShows(auth)
    
    # Ottieni le impostazioni utente per confermare l'autenticazione
    print("\nRecupero informazioni utente...")
    settings = shows.get_user_settings()
    
    if settings:
        user = settings.get('user', {})
        username = user.get('username', 'Unknown')
        print(f"✓ Autenticato come: {username}")
        
        # Verifica se l'utente è VIP
        if user.get('vip'):
            print("  [VIP] 👑")
    
    # Menu principale
    while True:
        print("\n" + "="*70)
        print("  MENU PRINCIPALE")
        print("="*70)
        print("1. Visualizza i miei show preferiti 📺")
        print("2. Visualizza la mia watchlist 📋")
        print("3. Visualizza gli show che ho già visto 🎬")
        print("4. Cerca uno show 🔍")
        print("5. Show più popolari 🔥")
        print("6. Show di tendenza 📈")
        print("7. Prossime uscite 📅")
        print("0. Esci")
        print("="*70)
        
        choice = input("\nScegli un'opzione: ").strip()
        
        if choice == '1':
            show_favorites(shows)
        elif choice == '2':
            show_watchlist(shows)
        elif choice == '3':
            show_watching(shows)
        elif choice == '4':
            search_shows(shows)
        elif choice == '5':
            show_popular(shows)
        elif choice == '6':
            show_trending(shows)
        elif choice == '7':
            show_upcoming_episodes(shows)
        elif choice == '0':
            print("\nArrivederci! 👋\n")
            break
        else:
            print("\n⚠ Opzione non valida. Riprova.")


def show_favorites(shows):
    """Visualizza gli show preferiti dell'utente"""
    print("\n📺 Recupero i tuoi show preferiti...")
    favorites = shows.get_favorites(type='shows')
    
    if not favorites:
        print("⚠ Nessuno show preferito trovato o errore nella richiesta.")
        return
    
    if len(favorites) == 0:
        print("Non hai ancora aggiunto show ai preferiti.")
        print("Visita https://trakt.tv per aggiungerne alcuni!")
        return
    
    print(f"\n✓ Trovati {len(favorites)} show preferiti")
    
    # Mostra riepilogo
    display_shows_summary(favorites)
    
    # Chiedi se vuole vedere i dettagli
    while True:
        choice = input("\nVuoi vedere i dettagli di uno show? (numero o 'n' per tornare): ").strip()
        
        if choice.lower() == 'n':
            break
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(favorites):
                print(format_show_info(favorites[idx], idx + 1))
            else:
                print("⚠ Numero non valido.")
        except ValueError:
            print("⚠ Inserisci un numero valido o 'n'.")


def show_watchlist(shows):
    """Visualizza la watchlist dell'utente"""
    print("\n📋 Recupero la tua watchlist...")
    watchlist = shows.get_watchlist(type='shows')
    
    if not watchlist:
        print("⚠ Nessuno show nella watchlist o errore nella richiesta.")
        return
    
    if len(watchlist) == 0:
        print("La tua watchlist è vuota.")
        return
    
    print(f"\n✓ Trovati {len(watchlist)} show nella watchlist")
    
    # Mostra riepilogo
    display_shows_summary(watchlist)
    
    # Chiedi se vuole vedere i dettagli
    while True:
        choice = input("\nVuoi vedere i dettagli di uno show? (numero o 'n' per tornare): ").strip()
        
        if choice.lower() == 'n':
            break
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(watchlist):
                print(format_show_info(watchlist[idx], idx + 1))
            else:
                print("⚠ Numero non valido.")
        except ValueError:
            print("⚠ Inserisci un numero valido o 'n'.")


def show_watching(shows):
    """Visualizza gli show che l'utente sta guardando"""
    print("\n🎬 Recupero gli show che stai guardando...")
    watched = shows.get_watched_shows()
    
    if not watched:
        print("⚠ Nessuno show trovato o errore nella richiesta.")
        return
    
    if len(watched) == 0:
        print("Non hai ancora guardato nessuno show.")
        return
    
    print(f"\n✓ Trovati {len(watched)} show guardati")
    
    # Mostra riepilogo
    display_shows_summary(watched)


def search_shows(shows):
    """Cerca uno show"""
    query = input("\n🔍 Inserisci il nome dello show da cercare: ").strip()
    
    if not query:
        print("⚠ Query di ricerca vuota.")
        return
    
    print(f"\nRicerca di '{query}'...")
    results = shows.search_show(query)
    
    if not results:
        print("⚠ Nessun risultato trovato o errore nella richiesta.")
        return
    
    if len(results) == 0:
        print(f"Nessuno show trovato per '{query}'.")
        return
    
    print(f"\n✓ Trovati {len(results)} risultati")
    
    # Mostra i primi 10 risultati
    display_results = results[:10]
    
    for idx, result in enumerate(display_results, 1):
        show = result.get('show', {})
        title = show.get('title', 'N/A')
        year = show.get('year', '?')
        rating = show.get('rating', 0)
        
        print(f"{idx:3d}. {title} ({year}) - Rating: {rating:.1f}/10")
    
    # Chiedi se vuole vedere i dettagli
    while True:
        choice = input("\nVuoi vedere i dettagli di uno show? (numero o 'n' per tornare): ").strip()
        
        if choice.lower() == 'n':
            break
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(display_results):
                print(format_show_info(display_results[idx], idx + 1))
            else:
                print("⚠ Numero non valido.")
        except ValueError:
            print("⚠ Inserisci un numero valido o 'n'.")


def show_popular(shows):
    """Visualizza gli show più popolari"""
    print("\n🔥 Recupero gli show più popolari...")
    
    limit_input = input("Quanti show vuoi visualizzare? (default: 10): ").strip()
    limit = int(limit_input) if limit_input.isdigit() else 10
    
    popular = shows.get_popular_shows(limit=limit)
    
    if not popular:
        print("⚠ Errore nella richiesta.")
        return
    
    print(f"\n✓ Trovati {len(popular)} show popolari")
    
    # Mostra riepilogo
    display_shows_summary(popular)
    
    # Chiedi se vuole vedere i dettagli
    while True:
        choice = input("\nVuoi vedere i dettagli di uno show? (numero o 'n' per tornare): ").strip()
        
        if choice.lower() == 'n':
            break
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(popular):
                print(format_show_info(popular[idx], idx + 1))
            else:
                print("⚠ Numero non valido.")
        except ValueError:
            print("⚠ Inserisci un numero valido o 'n'.")


def show_trending(shows):
    """Visualizza gli show di tendenza"""
    print("\n📈 Recupero gli show di tendenza...")
    
    limit_input = input("Quanti show vuoi visualizzare? (default: 10): ").strip()
    limit = int(limit_input) if limit_input.isdigit() else 10
    
    trending = shows.get_trending_shows(limit=limit)
    
    if not trending:
        print("⚠ Errore nella richiesta.")
        return
    
    print(f"\n✓ Trovati {len(trending)} show di tendenza")
    
    # Mostra riepilogo
    display_shows_summary(trending)
    
    # Chiedi se vuole vedere i dettagli
    while True:
        choice = input("\nVuoi vedere i dettagli di uno show? (numero o 'n' per tornare): ").strip()
        
        if choice.lower() == 'n':
            break
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(trending):
                print(format_show_info(trending[idx], idx + 1))
            else:
                print("⚠ Numero non valido.")
        except ValueError:
            print("⚠ Inserisci un numero valido o 'n'.")


def show_upcoming_episodes(shows):
    """Visualizza le prossime uscite degli show nella watchlist/preferiti"""
    print("\n📅 Recupero le prossime uscite...")
    
    # Ottieni tutti gli show combinati (favorites + watchlist)
    all_shows = shows.get_combined_user_shows(extended='full')
    
    if not all_shows:
        print("⚠ Nessuno show trovato o errore nella richiesta.")
        return
    
    # Lista per raccogliere gli show con prossime uscite
    upcoming = []
    
    for item in all_shows:
        show = item.get('show', item)
        show_id = (show.get('ids') or {}).get('trakt') or (show.get('ids') or {}).get('slug')
        
        if not show_id:
            continue
        
        # Ottieni il prossimo episodio
        next_ep = shows.get_next_episode(show_id, extended='full')
        
        if next_ep and next_ep.get('first_aired'):
            upcoming.append({
                'show': show,
                'next_episode': next_ep,
                'first_aired': next_ep.get('first_aired')
            })
    
    if not upcoming:
        print("\n📭 Nessuno show ha date di uscita programmate al momento.")
        return
    
    # Ordina per data di uscita
    upcoming.sort(key=lambda x: x['first_aired'])
    
    print(f"\n✓ Trovati {len(upcoming)} show con uscite programmate\n")
    print("="*70)
    
    for idx, item in enumerate(upcoming, 1):
        show = item['show']
        next_ep = item['next_episode']
        
        title = show.get('title', 'N/A')
        status = show.get('status', 'N/A')
        
        # Informazioni episodio
        season = next_ep.get('season')
        episode = next_ep.get('number')
        ep_title = next_ep.get('title', 'TBA')
        first_aired = next_ep.get('first_aired')
        
        # Formatta la data
        try:
            aired_dt = datetime.fromisoformat(first_aired.replace('Z', '+00:00'))
            aired_str = aired_dt.strftime('%d/%m/%Y %H:%M')
            
            # Calcola giorni mancanti
            now = datetime.now(aired_dt.tzinfo)
            delta = aired_dt - now
            days_left = delta.days
            
            if days_left < 0:
                time_info = "(già trasmesso)"
            elif days_left == 0:
                time_info = "(OGGI!)" 
            elif days_left == 1:
                time_info = "(domani)"
            else:
                time_info = f"(tra {days_left} giorni)"
        except:
            aired_str = first_aired
            time_info = ""
        
        # Codice episodio
        ep_code = f"S{season:02d}E{episode:02d}" if season and episode else "N/A"
        
        print(f"{idx:3d}. {title}")
        print(f"     {ep_code} - {ep_title}")
        print(f"     📅 {aired_str} {time_info}")
        print(f"     Status: {status}")
        print()
    
    print("="*70)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrotto dall'utente. Arrivederci! 👋\n")
        sys.exit(0)
