#!/usr/bin/env python3
"""
Import massivo di show visti su Trakt da CSV o JSON.
"""
import argparse
import csv
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from difflib import SequenceMatcher

try:
    import config
except ImportError:
    print("\n⚠ File config.py non trovato!")
    print("Configura prima CLIENT_ID e CLIENT_SECRET.\n")
    sys.exit(1)

from trakt_auth import TraktAuth
from trakt_shows import TraktShows


TITLE_KEYS = ('title', 'name', 'show', 'series', 'series_title')
YEAR_KEYS = ('year', 'release_year')
WATCHED_AT_KEYS = (
    'watched_at',
    'watched_on',
    'viewed_at',
    'viewed_on',
    'first_aired',
    'released',
    'released_at',
    'release_date',
    'aired_at'
)


def normalize_title(value):
    """Normalizza un titolo per il matching."""
    if not value:
        return ''

    value = unicodedata.normalize('NFKD', str(value))
    value = value.encode('ascii', 'ignore').decode('ascii')
    value = value.lower()
    value = re.sub(r'[^a-z0-9]+', ' ', value)
    value = re.sub(r'\s+', ' ', value).strip()
    return value


def pick_value(record, keys):
    """Restituisce il primo valore non vuoto per una lista di chiavi."""
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        value = str(value).strip()
        if value:
            return value
    return None


def parse_year(value):
    """Converte l'anno in intero, se disponibile."""
    if value is None:
        return None

    match = re.search(r'(19|20)\d{2}', str(value))
    if not match:
        return None
    return int(match.group(0))


def parse_watched_at(value):
    """Converte varie date in ISO8601 UTC accettabile per Trakt."""
    if not value:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    candidates = [
        '%Y-%m-%d',
        '%d/%m/%Y',
        '%Y/%m/%d',
        '%d-%m-%Y',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%d/%m/%Y %H:%M:%S',
        '%d/%m/%Y %H:%M',
    ]

    iso_candidate = raw.replace('Z', '+00:00')
    try:
        dt = datetime.fromisoformat(iso_candidate)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    except ValueError:
        pass

    for fmt in candidates:
        try:
            dt = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
            return dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        except ValueError:
            continue

    return None


def load_csv(path, delimiter=','):
    """Carica record da CSV."""
    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        return list(reader)


def load_json(path):
    """Carica record da JSON."""
    with path.open('r', encoding='utf-8') as handle:
        data = json.load(handle)

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ('shows', 'items', 'data'):
            value = data.get(key)
            if isinstance(value, list):
                return value
    raise ValueError('Formato JSON non supportato. Atteso array di oggetti.')


def load_txt(path):
    """Carica record da file di testo, un titolo per riga."""
    records = []

    with path.open('r', encoding='utf-8-sig') as handle:
        for line in handle:
            title = line.strip()
            if not title:
                continue
            records.append({'title': title})

    return records


def load_records(path, fmt='auto', delimiter=','):
    """Carica il file sorgente nel formato richiesto."""
    detected = fmt
    if fmt == 'auto':
        suffix = path.suffix.lower()
        if suffix == '.csv':
            detected = 'csv'
        elif suffix == '.json':
            detected = 'json'
        elif suffix == '.txt':
            detected = 'txt'
        else:
            raise ValueError('Impossibile rilevare il formato. Usa --format csv, json o txt.')

    if detected == 'csv':
        return load_csv(path, delimiter=delimiter)
    if detected == 'json':
        return load_json(path)
    if detected == 'txt':
        return load_txt(path)
    raise ValueError(f'Formato non supportato: {detected}')


def build_source_item(record, index):
    """Normalizza un record sorgente."""
    title = pick_value(record, TITLE_KEYS)
    year = parse_year(pick_value(record, YEAR_KEYS))
    watched_at = parse_watched_at(pick_value(record, WATCHED_AT_KEYS))

    return {
        'index': index,
        'raw': record,
        'title': title,
        'year': year,
        'watched_at': watched_at
    }


def score_candidate(source, candidate_show):
    """Calcola un punteggio di matching fra record sorgente e show Trakt."""
    source_title = normalize_title(source['title'])
    candidate_title = normalize_title(candidate_show.get('title'))
    ratio = SequenceMatcher(None, source_title, candidate_title).ratio()

    source_year = source.get('year')
    candidate_year = candidate_show.get('year')

    if source_year and candidate_year:
        if source_year == candidate_year:
            ratio += 0.08
        elif abs(source_year - candidate_year) == 1:
            ratio += 0.02
        else:
            ratio -= 0.15

    return max(0.0, min(ratio, 1.0))


def choose_best_match(source, search_results):
    """Seleziona il miglior match e decide se è abbastanza affidabile."""
    scored = []

    for result in search_results or []:
        show = result.get('show', {})
        score = score_candidate(source, show)
        scored.append({
            'score': score,
            'show': show
        })

    scored.sort(key=lambda item: item['score'], reverse=True)

    if not scored:
        return None, 'unmatched', []

    best = scored[0]
    alternatives = scored[:5]
    second_score = scored[1]['score'] if len(scored) > 1 else 0.0
    gap = best['score'] - second_score

    exact_title = normalize_title(source['title']) == normalize_title(best['show'].get('title'))
    exact_year = (
        source.get('year') is not None and
        source.get('year') == best['show'].get('year')
    )

    if exact_title and (source.get('year') is None or exact_year):
        return best, 'matched', alternatives

    if best['score'] >= 0.93:
        return best, 'matched', alternatives

    if best['score'] >= 0.88 and gap >= 0.06 and exact_year:
        return best, 'matched', alternatives

    if best['score'] >= 0.84 and gap >= 0.10 and source.get('year') is None:
        return best, 'matched', alternatives

    return best, 'ambiguous', alternatives


def build_history_item(match):
    """Crea il payload show per /sync/history."""
    show = match['show']
    item = {
        'ids': {
            'trakt': show['ids']['trakt']
        }
    }

    if match['source'].get('watched_at'):
        item['watched_at'] = match['source']['watched_at']

    return item


def build_episode_history_items(shows_client, match, now_utc):
    """
    Espande uno show in episodi già andati in onda, usando first_aired come watched_at.
    """
    show = match['show']
    trakt_id = ((show.get('ids') or {}).get('trakt'))
    if not trakt_id:
        return [], 'missing_trakt_id'

    seasons = shows_client.get_show_seasons(trakt_id, extended='episodes,full')
    if not seasons:
        return [], 'seasons_fetch_failed'

    episodes_payload = []

    for season in seasons:
        if season.get('number', 0) == 0:
            continue

        for episode in season.get('episodes') or []:
            first_aired = episode.get('first_aired')
            if not first_aired:
                continue

            try:
                aired_dt = datetime.fromisoformat(first_aired.replace('Z', '+00:00'))
            except ValueError:
                continue

            if aired_dt > now_utc:
                continue

            episode_ids = episode.get('ids') or {}
            trakt_episode_id = episode_ids.get('trakt')
            if not trakt_episode_id:
                continue

            episodes_payload.append({
                'ids': {
                    'trakt': trakt_episode_id
                },
                'watched_at': aired_dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
            })

    if not episodes_payload:
        return [], 'no_aired_episodes'

    return episodes_payload, None


def chunked(items, size):
    """Divide una lista in chunk."""
    for start in range(0, len(items), size):
        yield items[start:start + size]


def write_report(path, report):
    """Scrive il report finale su disco."""
    with path.open('w', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description='Importa show visti su Trakt da CSV, TXT o JSON')
    parser.add_argument('input_file', help='Percorso file sorgente CSV, TXT o JSON')
    parser.add_argument('--format', choices=('auto', 'csv', 'json', 'txt'), default='auto')
    parser.add_argument('--delimiter', default=',', help='Separatore CSV, default ","')
    parser.add_argument('--report', help='Percorso file report JSON')
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Esegue davvero l’import su Trakt. Senza questo flag fa solo dry-run.'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=50,
        help='Numero di show per richiesta POST, default 50'
    )
    parser.add_argument(
        '--date-mode',
        choices=('release', 'now'),
        default='release',
        help='release = usa first_aired degli episodi, now = marca lo show senza date esplicite'
    )
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f'⚠ File non trovato: {input_path}')
        sys.exit(1)

    report_path = Path(args.report) if args.report else input_path.with_suffix('.trakt_import_report.json')

    auth = TraktAuth(
        client_id=config.CLIENT_ID,
        client_secret=config.CLIENT_SECRET,
        redirect_uri=config.REDIRECT_URI
    )

    if not auth.access_token:
        print("\nPrima autenticazione necessaria...")
        if not auth.authenticate():
            print("Autenticazione fallita. Uscita.")
            sys.exit(1)
    else:
        auth.ensure_valid_token()

    shows_client = TraktShows(auth)

    try:
        raw_records = load_records(input_path, fmt=args.format, delimiter=args.delimiter)
    except ValueError as exc:
        print(f'⚠ {exc}')
        sys.exit(1)

    source_items = [build_source_item(record, idx) for idx, record in enumerate(raw_records, 1)]

    matched = []
    ambiguous = []
    unmatched = []
    invalid = []
    skipped = []

    for source in source_items:
        if not source['title']:
            invalid.append({
                'index': source['index'],
                'reason': 'missing_title',
                'raw': source['raw']
            })
            continue

        results = shows_client.search_show(source['title'], extended='full', limit=10)
        best, status, alternatives = choose_best_match(source, results)

        if status == 'matched':
            matched.append({
                'source': source,
                'show': best['show'],
                'score': round(best['score'], 4)
            })
            continue

        if status == 'ambiguous':
            ambiguous.append({
                'source': source,
                'best_match': {
                    'title': best['show'].get('title'),
                    'year': best['show'].get('year'),
                    'ids': best['show'].get('ids'),
                    'score': round(best['score'], 4)
                },
                'alternatives': [
                    {
                        'title': item['show'].get('title'),
                        'year': item['show'].get('year'),
                        'ids': item['show'].get('ids'),
                        'score': round(item['score'], 4)
                    }
                    for item in alternatives
                ]
            })
            continue

        unmatched.append({
            'source': source
        })

    report = {
        'input_file': str(input_path),
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
        'summary': {
            'total_records': len(source_items),
            'matched': len(matched),
            'ambiguous': len(ambiguous),
            'unmatched': len(unmatched),
            'invalid': len(invalid),
            'skipped': 0,
            'applied': False
        },
        'date_mode': args.date_mode,
        'matched': [
            {
                'source_title': item['source']['title'],
                'source_year': item['source']['year'],
                'source_watched_at': item['source']['watched_at'],
                'trakt_title': item['show'].get('title'),
                'trakt_year': item['show'].get('year'),
                'trakt_ids': item['show'].get('ids'),
                'score': item['score']
            }
            for item in matched
        ],
        'ambiguous': ambiguous,
        'unmatched': unmatched,
        'invalid': invalid,
        'skipped': skipped
    }

    print(f"\nTotale record: {len(source_items)}")
    print(f"Match sicuri: {len(matched)}")
    print(f"Ambigui: {len(ambiguous)}")
    print(f"Non trovati: {len(unmatched)}")
    print(f"Non validi: {len(invalid)}")

    if not args.apply:
        write_report(report_path, report)
        print(f"\nDry-run completato. Report scritto in: {report_path}")
        print("Riesegui con --apply quando il report ti soddisfa.")
        return

    now_utc = datetime.now(timezone.utc)
    shows_payload = []
    episodes_payload = []

    if args.date_mode == 'now':
        shows_payload = [build_history_item(item) for item in matched]
    else:
        for item in matched:
            show_episodes, error_code = build_episode_history_items(shows_client, item, now_utc)
            if error_code:
                skipped.append({
                    'source_title': item['source']['title'],
                    'source_year': item['source']['year'],
                    'trakt_title': item['show'].get('title'),
                    'trakt_year': item['show'].get('year'),
                    'reason': error_code
                })
                continue
            episodes_payload.extend(show_episodes)

    report['skipped'] = skipped
    report['summary']['skipped'] = len(skipped)

    if not shows_payload and not episodes_payload:
        write_report(report_path, report)
        print("\nNessun elemento importabile trovato.")
        print(f"Report scritto in: {report_path}")
        return

    applied_count = 0

    if shows_payload:
        for batch in chunked(shows_payload, max(1, args.batch_size)):
            response = shows_client.add_watched_history(shows_payload=batch)
            if response is None:
                print("\n⚠ Import interrotto per errore API.")
                break

            added = ((response.get('added') or {}).get('shows')) or 0
            applied_count += added

    if episodes_payload:
        for batch in chunked(episodes_payload, max(1, args.batch_size)):
            response = shows_client.add_watched_history(episodes_payload=batch)
            if response is None:
                print("\n⚠ Import interrotto per errore API.")
                break

            added = ((response.get('added') or {}).get('episodes')) or 0
            applied_count += added

    report['summary']['applied'] = True
    report['summary']['applied_count'] = applied_count
    write_report(report_path, report)

    print(f"\nImport completato. Show aggiunti alla history: {applied_count}")
    print(f"Report scritto in: {report_path}")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrotto dall'utente.")
        sys.exit(130)
