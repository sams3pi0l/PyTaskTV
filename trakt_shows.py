"""
Modulo per interagire con gli show su Trakt.tv
"""
import requests
import time
from datetime import datetime


class TraktShows:
    """Gestisce le operazioni relative agli show su Trakt.tv"""
    
    API_URL = 'https://api.trakt.tv'
    REQUEST_TIMEOUT = 30
    
    def __init__(self, auth):
        self.auth = auth
    
    def _request(self, method, endpoint, params=None, json_data=None):
        """Effettua una richiesta API"""
        self.auth.ensure_valid_token()
        
        url = f"{self.API_URL}{endpoint}"
        headers = self.auth.get_headers()
        
        for attempt in range(3):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_data,
                    timeout=self.REQUEST_TIMEOUT
                )

                if response.status_code == 429 and attempt < 2:
                    retry_after = response.headers.get('Retry-After')
                    wait_seconds = int(retry_after) if retry_after and retry_after.isdigit() else 2
                    time.sleep(max(wait_seconds, 1))
                    continue

                if response.status_code == 204:
                    return None

                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                print(f"Errore nella richiesta API: {e}")
                return None

        return None

    def _make_request(self, endpoint, params=None):
        """Effettua una richiesta API GET"""
        return self._request('GET', endpoint, params=params)

    def _post_request(self, endpoint, json_data=None):
        """Effettua una richiesta API POST"""
        return self._request('POST', endpoint, json_data=json_data)
    
    def get_user_settings(self):
        """Ottiene le impostazioni dell'utente"""
        return self._make_request('/users/settings')
    
    def get_favorites(self, type='shows', extended='full'):
        """
        Ottiene gli show o film preferiti dell'utente
        
        Args:
            type: 'shows' o 'movies'
            extended: 'full' per informazioni complete, 'metadata' per metadati aggiuntivi
        """
        params = {'extended': extended}
        return self._make_request(f'/sync/favorites/{type}', params=params)
    
    def get_watchlist(self, type='shows', extended='full', sort_by='rank'):
        """
        Ottiene la watchlist dell'utente
        
        Args:
            type: 'shows', 'movies', 'seasons', 'episodes'
            extended: livello di dettaglio
            sort_by: criterio di ordinamento
        """
        params = {
            'extended': extended,
            'sort_by': sort_by
        }
        return self._make_request(f'/sync/watchlist/{type}', params=params)

    def get_combined_user_shows(self, extended='full'):
        """
        Restituisce una lista unica di show presi da favorites + watchlist.
        Deduplica usando l'ID Trakt dello show.
        """
        favorites = self.get_favorites(type='shows', extended=extended) or []
        watchlist = self.get_watchlist(type='shows', extended=extended) or []

        combined = []
        seen_trakt_ids = set()

        for item in favorites + watchlist:
            show = item.get('show', item)
            trakt_id = (show.get('ids') or {}).get('trakt')
            if not trakt_id or trakt_id in seen_trakt_ids:
                continue
            seen_trakt_ids.add(trakt_id)
            combined.append(item)

        return combined
    
    def get_show_details(self, show_id, extended='full'):
        """
        Ottiene i dettagli di uno show specifico
        
        Args:
            show_id: ID Trakt dello show o slug
            extended: livello di dettaglio
        """
        params = {'extended': extended}
        return self._make_request(f'/shows/{show_id}', params=params)

    def get_show_seasons(self, show_id, extended='full'):
        """
        Ottiene stagioni ed episodi di uno show.

        Args:
            show_id: ID Trakt dello show o slug
            extended: livello di dettaglio
        """
        params = {'extended': extended}
        return self._make_request(f'/shows/{show_id}/seasons', params=params)
    
    def get_show_progress(self, show_id):
        """
        Ottiene lo stato di avanzamento di uno show
        
        Args:
            show_id: ID Trakt dello show o slug
        """
        return self._make_request(f'/shows/{show_id}/progress/watched')

    def get_next_episode(self, show_id, extended='full'):
        """
        Ottiene il prossimo episodio di uno show.

        Args:
            show_id: ID Trakt dello show o slug
            extended: livello di dettaglio
        """
        self.auth.ensure_valid_token()
        url = f"{self.API_URL}/shows/{show_id}/next_episode"
        headers = self.auth.get_headers()
        params = {'extended': extended}

        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=self.REQUEST_TIMEOUT
            )
            if response.status_code in (204, 404):
                return None
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Errore nel recupero next_episode ({show_id}): {e}")
            return None
    
    def get_watched_shows(self, extended='full'):
        """Ottiene tutti gli show guardati dall'utente"""
        params = {'extended': extended}
        return self._make_request('/sync/watched/shows', params=params)
    
    def get_trending_shows(self, limit=10, extended='full'):
        """Ottiene gli show di tendenza"""
        params = {
            'extended': extended,
            'limit': limit
        }
        return self._make_request('/shows/trending', params=params)
    
    def get_popular_shows(self, limit=10, extended='full'):
        """Ottiene gli show più popolari"""
        params = {
            'extended': extended,
            'limit': limit
        }
        return self._make_request('/shows/popular', params=params)
    
    def search_show(self, query, extended='full', limit=None):
        """
        Cerca uno show per nome
        
        Args:
            query: termine di ricerca
            extended: livello di dettaglio
        """
        params = {
            'query': query,
            'fields': 'title',
            'extended': extended
        }
        results = self._make_request('/search/show', params=params)

        if limit and results:
            return results[:limit]
        return results

    def add_watched_history(self, shows_payload=None, episodes_payload=None):
        """
        Aggiunge show/episodi alla watched history dell'utente.

        Args:
            shows_payload: lista di show nel formato accettato da /sync/history
            episodes_payload: lista di episodi nel formato accettato da /sync/history
        """
        payload = {}

        if shows_payload:
            payload['shows'] = shows_payload
        if episodes_payload:
            payload['episodes'] = episodes_payload

        return self._post_request('/sync/history', json_data=payload)


def format_show_info(show_data, show_number=None):
    """Formatta le informazioni di uno show per la visualizzazione"""
    
    # Gestisci diversi formati di risposta
    if 'show' in show_data:
        show = show_data['show']
        notes = show_data.get('notes', '')
        rank = show_data.get('rank', 0)
    else:
        show = show_data
        notes = ''
        rank = 0
    
    lines = []
    
    # Header con numero
    if show_number:
        lines.append(f"\n{'='*70}")
        lines.append(f"  #{show_number} - {show.get('title', 'N/A')}")
        lines.append(f"{'='*70}")
    else:
        lines.append(f"\n{'='*70}")
        lines.append(f"  {show.get('title', 'N/A')}")
        lines.append(f"{'='*70}")
    
    # Anno
    year = show.get('year')
    if year:
        lines.append(f"Anno: {year}")
    
    # Status
    status = show.get('status')
    if status:
        status_emoji = {
            'returning series': '🔄',
            'continuing': '🔄',
            'ended': '✓',
            'canceled': '✗',
            'in production': '🎬'
        }
        emoji = status_emoji.get(status, '•')
        lines.append(f"Status: {emoji} {status.title()}")
    
    # Network
    network = show.get('network')
    if network:
        lines.append(f"Network: {network}")
    
    # Rating
    rating = show.get('rating')
    if rating:
        stars = '⭐' * int(rating)
        lines.append(f"Rating: {rating:.1f}/10 {stars}")
    
    # Votes
    votes = show.get('votes')
    if votes:
        lines.append(f"Voti: {votes:,}")
    
    # Generi
    genres = show.get('genres', [])
    if genres:
        lines.append(f"Generi: {', '.join(genres)}")
    
    # Overview
    overview = show.get('overview')
    if overview:
        lines.append(f"\nDescrizione:")
        # Limita la lunghezza della descrizione
        if len(overview) > 300:
            overview = overview[:297] + '...'
        lines.append(f"  {overview}")
    
    # Note dell'utente
    if notes:
        lines.append(f"\nNote personali:")
        lines.append(f"  {notes}")
    
    # IDs
    ids = show.get('ids', {})
    if ids:
        lines.append(f"\nIDs:")
        if ids.get('trakt'):
            lines.append(f"  Trakt: {ids['trakt']}")
        if ids.get('imdb'):
            lines.append(f"  IMDB: https://www.imdb.com/title/{ids['imdb']}")
        if ids.get('tmdb'):
            lines.append(f"  TMDB: https://www.themoviedb.org/tv/{ids['tmdb']}")
    
    # Link Trakt
    if ids.get('slug'):
        lines.append(f"  Trakt: https://trakt.tv/shows/{ids['slug']}")
    
    return '\n'.join(lines)


def display_shows_summary(shows_data):
    """Visualizza un riepilogo degli show"""
    print(f"\n{'='*70}")
    print(f"  RIEPILOGO SHOW")
    print(f"{'='*70}")
    
    for idx, show_data in enumerate(shows_data, 1):
        if 'show' in show_data:
            show = show_data['show']
        else:
            show = show_data
        
        title = show.get('title', 'N/A')
        year = show.get('year', '?')
        rating = show.get('rating', 0)
        stars = '⭐' * int(rating) if rating else ''
        
        print(f"{idx:3d}. {title} ({year}) - {rating:.1f}/10 {stars}")
    
    print(f"{'='*70}\n")
