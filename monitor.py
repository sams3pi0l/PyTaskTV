#!/usr/bin/env python3
"""
Monitor show Trakt e invia notifiche Telegram su cambi utili:
- status passa a returning series / in production
- next_air (next_episode.first_aired) passa da sconosciuto a data concreta
"""
import json
import os
import time
import argparse
import traceback
from datetime import datetime, timezone
from pathlib import Path

import requests

try:
    import config
except ImportError:
    print("File config.py non trovato.")
    raise SystemExit(1)

from trakt_auth import TraktAuth
from trakt_shows import TraktShows


TARGET_STATUSES = {"returning series", "in production"}
STATE_FILE = Path("status_cache.json")


def utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def load_state():
    if not STATE_FILE.exists():
        return {"shows": {}}
    try:
        with STATE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "shows" not in data:
            return {"shows": {}}
        if not isinstance(data["shows"], dict):
            data["shows"] = {}
        return data
    except Exception:
        return {"shows": {}}


def save_state(state):
    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=True)


def get_config_value(name, default=None):
    if hasattr(config, name):
        return getattr(config, name)
    return os.getenv(name, default)


def send_telegram_message(bot_token, chat_id, text):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    try:
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        body = response.json()
        return bool(body.get("ok"))
    except requests.RequestException as exc:
        print(f"Errore invio Telegram: {exc}")
        return False


def normalize_status(status):
    if not status:
        return None
    return str(status).strip().lower()


def show_key(show):
    trakt_id = (show.get("ids") or {}).get("trakt")
    if not trakt_id:
        return None
    return f"trakt:{trakt_id}"


def format_episode_code(season, episode):
    if season is None or episode is None:
        return None
    try:
        return f"S{int(season):02d}E{int(episode):02d}"
    except (TypeError, ValueError):
        return None


def get_next_episode_info(shows_client, show):
    show_id = (show.get("ids") or {}).get("trakt") or (show.get("ids") or {}).get("slug")
    if not show_id:
        return {"next_air": None, "next_episode_code": None}
    next_ep = shows_client.get_next_episode(show_id, extended="full")
    if not next_ep:
        return {"next_air": None, "next_episode_code": None}
    return {
        "next_air": next_ep.get("first_aired"),
        "next_episode_code": format_episode_code(
            next_ep.get("season"), next_ep.get("number")
        ),
    }


def build_message(show, prev_data, new_status, new_next_air, new_next_episode_code):
    title = show.get("title", "N/A")
    slug = (show.get("ids") or {}).get("slug")
    trakt_url = f"https://trakt.tv/shows/{slug}" if slug else ""

    lines = [f"Trakt update: {title}"]

    prev_status = prev_data.get("status") if prev_data else None
    prev_next_air = prev_data.get("next_air") if prev_data else None
    prev_next_episode_code = prev_data.get("next_episode_code") if prev_data else None

    if prev_status != new_status:
        lines.append(f"- status: {prev_status or 'N/A'} -> {new_status or 'N/A'}")
    if prev_next_air != new_next_air:
        lines.append(f"- next_air: {prev_next_air or 'TBA'} -> {new_next_air or 'TBA'}")
    if prev_next_episode_code != new_next_episode_code:
        lines.append(
            f"- next_episode: {prev_next_episode_code or 'TBA'} -> {new_next_episode_code or 'TBA'}"
        )

    if trakt_url:
        lines.append(trakt_url)

    return "\n".join(lines)


def should_notify(prev_data, new_status, new_next_air, new_next_episode_code):
    if prev_data is None:
        return False

    prev_status = prev_data.get("status")
    prev_next_air = prev_data.get("next_air")
    prev_next_episode_code = prev_data.get("next_episode_code")

    status_changed_to_target = (
        new_status in TARGET_STATUSES and new_status != prev_status
    )
    # Notifica se next_air diventa disponibile o cambia (anche da data a data)
    next_air_updated = prev_next_air != new_next_air and new_next_air is not None
    
    fingerprint_changed = (
        (prev_status != new_status)
        or (prev_next_air != new_next_air)
        or (prev_next_episode_code != new_next_episode_code)
    )

    return fingerprint_changed and (status_changed_to_target or next_air_updated)


def monitor_once(shows_client, bot_token, chat_id):
    state = load_state()
    state_shows = state.setdefault("shows", {})
    source_items = shows_client.get_combined_user_shows(extended="full")

    if not source_items:
        print("Nessuno show trovato in favorites/watchlist.")
        return 0

    sent = 0
    now_iso = utc_now_iso()

    for item in source_items:
        try:
            show = item.get("show", item)
            key = show_key(show)
            if not key:
                continue

            new_status = normalize_status(show.get("status"))
            next_ep_info = get_next_episode_info(shows_client, show)
            new_next_air = next_ep_info["next_air"]
            new_next_episode_code = next_ep_info["next_episode_code"]
            prev_data = state_shows.get(key)

            if should_notify(prev_data, new_status, new_next_air, new_next_episode_code):
                msg = build_message(
                    show, prev_data, new_status, new_next_air, new_next_episode_code
                )
                if send_telegram_message(bot_token, chat_id, msg):
                    sent += 1

            state_shows[key] = {
                "status": new_status,
                "next_air": new_next_air,
                "next_episode_code": new_next_episode_code,
                "updated_at": now_iso,
            }
        except Exception as exc:
            show_title = (item.get("show", item) or {}).get("title", "N/A")
            print(f"Errore show '{show_title}': {exc}")
            continue

    save_state(state)
    return sent


def main():
    parser = argparse.ArgumentParser(description="Trakt show monitor + Telegram notifier")
    parser.add_argument(
        "--test-telegram",
        action="store_true",
        help="Invia un messaggio test Telegram e termina.",
    )
    args = parser.parse_args()

    bot_token = get_config_value("TELEGRAM_BOT_TOKEN")
    chat_id = get_config_value("TELEGRAM_CHAT_ID")
    polling_interval_minutes = int(get_config_value("POLLING_INTERVAL_MINUTES", 0) or 0)

    if not bot_token or not chat_id:
        print("Config mancante: TELEGRAM_BOT_TOKEN e/o TELEGRAM_CHAT_ID.")
        raise SystemExit(1)

    if args.test_telegram:
        msg = f"Test Telegram OK - {utc_now_iso()}"
        ok = send_telegram_message(bot_token, chat_id, msg)
        print("Test Telegram inviato." if ok else "Invio test Telegram fallito.")
        raise SystemExit(0 if ok else 1)

    auth = TraktAuth(
        client_id=config.CLIENT_ID,
        client_secret=config.CLIENT_SECRET,
        redirect_uri=config.REDIRECT_URI,
    )

    if not auth.access_token and not auth.authenticate():
        print("Autenticazione Trakt fallita.")
        raise SystemExit(1)

    auth.ensure_valid_token()
    shows_client = TraktShows(auth)

    if polling_interval_minutes <= 0:
        sent = monitor_once(shows_client, bot_token, chat_id)
        print(f"Monitor completato. Notifiche inviate: {sent}")
        return

    print(f"Monitor avviato. Intervallo: {polling_interval_minutes} minuti.")
    while True:
        try:
            sent = monitor_once(shows_client, bot_token, chat_id)
            print(f"[{utc_now_iso()}] Notifiche inviate: {sent}")
        except Exception as exc:
            print(f"[{utc_now_iso()}] Errore nel ciclo monitor: {exc}")
            print(traceback.format_exc())
        time.sleep(polling_interval_minutes * 60)


if __name__ == "__main__":
    main()
