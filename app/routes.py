from flask import Blueprint, render_template, request, jsonify
from markupsafe import Markup
import os
import sqlite3
import traceback
import logging
import json
from datetime import datetime

from app.utils import (
    get_show_metadata,
    get_season_metadata,
    get_top_characters,
    get_show_backdrop,
    get_season_details,
    get_cast,
    search_tmdb,
    save_show_metadata,
    save_season_metadata,
    save_top_characters,
    get_latest_show_title_from_db,
    get_cached_summary, 
    summarize_character
)
from app.prompt_builder import build_character_prompt
from app.utils import find_actor_by_name

main = Blueprint('main', __name__)
logging.basicConfig(level=logging.INFO)

@main.route('/compare', methods=['POST'])
def compare():
    title1 = request.form.get('title1')
    title2 = request.form.get('title2')

    if not title1 or not title2:
        logging.warning("Both titles must be provided.")
        return "Both titles must be provided", 400

    res1_tv = search_tmdb(title1, 'tv').get('results', [])
    res1_mv = search_tmdb(title1, 'movie').get('results', [])
    result1 = (res1_tv + res1_mv)[0] if (res1_tv + res1_mv) else None

    res2_tv = search_tmdb(title2, 'tv').get('results', [])
    res2_mv = search_tmdb(title2, 'movie').get('results', [])
    result2 = (res2_tv + res2_mv)[0] if (res2_tv + res2_mv) else None

    if not result1 or not result2:
        logging.warning(f"Could not find one or both titles: {title1}, {title2}")
        return f"Could not find one or both titles: {title1}, {title2}", 404

    id1 = result1['id']
    id2 = result2['id']
    type1 = 'tv' if result1 in res1_tv else 'movie'
    type2 = 'tv' if result2 in res2_tv else 'movie'

    cast1 = get_cast(id1, type1)
    cast2 = get_cast(id2, type2)

    for actor in cast1:
        actor['show_id'] = id1
    for actor in cast2:
        actor['show_id'] = id2

    names1 = {actor['name'] for actor in cast1}
    names2 = {actor['name'] for actor in cast2}
    shared = sorted(names1 & names2)

    from app.db import log_overlap_query
    log_overlap_query(title1, title2, len(shared))

    from collections import defaultdict
    episode_map = defaultdict(int)

    for actor in cast1 + cast2:
        if actor['name'] in shared:
            ep = int(actor.get('episode_count', 0)) or 0
            episode_map[actor['name']] = max(episode_map[actor['name']], ep)

    shared_sorted = sorted(episode_map.items(), key=lambda x: x[1], reverse=True)
    top_names = {name for name, _ in shared_sorted[:20]}
    filtered_cast = [a for a in cast1 + cast2 if a['name'] in top_names]

    actor_details = get_actor_details(
        filtered_cast,
        (title1, id1, type1),
        (title2, id2, type2),
        top_names
    )

    return render_template(
        'overlap_results.html',
        title1=title1,
        title2=title2,
        shared=[name for name, _ in shared_sorted],
        actor_details=actor_details,
        count=len(shared)
    )

@main.route('/autocomplete/shows')
def autocomplete_shows():
    query = request.args.get('q', '').lower()
    suggestions = []
    try:
        db = sqlite3.connect("data/shownotes.db")
        cursor = db.execute("SELECT DISTINCT title FROM shows")
        rows = cursor.fetchall()
        for row in rows:
            title = row[0]
            if query in title.lower():
                suggestions.append({"name": title})
        db.close()
    except Exception as e:
        logging.error(f"Error fetching shows for autocomplete: {e}")
    return jsonify(suggestions[:10])

@main.route('/autocomplete/characters')
def autocomplete_characters():
    query = request.args.get('q', '').lower()
    show = request.args.get('show', '')
    suggestions = []
    try:
        db = sqlite3.connect("data/shownotes.db")
        cursor = db.execute("""
            SELECT character_name, actor_name
            FROM top_characters
            WHERE show_title = ?
        """, (show,))
        rows = cursor.fetchall()
        seen = set()
        for character, actor in rows:
            if (query in character.lower() or query in actor.lower()) and character.lower() not in seen:
                suggestions.append({"name": f"{character} ({actor})"})
                seen.add(character.lower())
        db.close()
    except Exception as e:
        logging.error(f"Error fetching characters for autocomplete: {e}")
    return jsonify(suggestions[:10])

@main.route('/character-summary', methods=['GET', 'POST'])
def character_summary():
    raw_summary = summary = image_url = reference_links = None
    character = show = ""
    season = episode = 1
    source = None
    other_characters = []

    if request.method == 'POST':
        show = request.form.get("show")
        character = request.form.get("character", "").split('(')[0].strip()
        season = request.form.get("season", type=int) or 1
        episode = request.form.get("episode", type=int) or 1

        summary, raw_summary = get_cached_summary(character, show, season, episode)
        source = "cache" if summary else "generated"

        if not summary:
            options = {
                "include_relationships": True,
                "include_motivations": True,
                "include_themes": True,
                "include_quote": True,
                "tone": "tv_expert"
            }
            summary, raw_summary = summarize_character(character, show, season, episode, options)
            save_character_summary_to_db(character, show, season, episode, raw_summary, summary)
            if summary:
                from datetime import datetime
                # Example mock token usage values for demonstration
                prompt_tokens = 500
                completion_tokens = 800
                total_tokens = prompt_tokens + completion_tokens
                # Approximate GPT-4 Turbo cost calculation
                cost = (prompt_tokens / 1000 * 0.01) + (completion_tokens / 1000 * 0.03)
                try:
                    db = sqlite3.connect("data/shownotes.db")
                    db.execute("""
                        INSERT INTO api_usage (character, show, prompt_tokens, completion_tokens, total_tokens, cost, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (character, show, prompt_tokens, completion_tokens, total_tokens, cost, datetime.utcnow().isoformat()))
                    db.commit()
                    db.close()
                except Exception as log_error:
                    logging.warning(f"Failed to log API usage: {log_error}")

        actor = find_actor_by_name(show, character)
        if actor and actor.get("profile_path"):
            image_url = f"https://image.tmdb.org/t/p/w185{actor['profile_path']}"

        other_characters = get_all_characters_for_show(show)

    return render_template("character_summary.html",
                           character=character,
                           show=show,
                           season=season,
                           episode=episode,
                           summary=summary,
                           image_url=image_url,
                           raw_summary=raw_summary,
                           source=source,
                           other_characters=other_characters,
                           reference_links=reference_links)

@main.route('/chat-as-character', methods=["GET", "POST"])
def chat_as_character_view():
    try:
        reply = message = None
        character = request.form.get('character') if request.method == 'POST' else 'Walter White'
        show = request.form.get('show') if request.method == 'POST' else 'Breaking Bad'

        if request.method == 'POST':
            message = request.form.get('message')
            reply = chat_as_character(character, show, message)

        actor = find_actor_by_name(show, character)
        image_url = f"https://image.tmdb.org/t/p/w185/{actor['profile_path']}" if actor and actor.get('profile_path') else None

        return render_template("chat_as_character.html",
                               reply=reply,
                               user_message=message,
                               show=show,
                               character=character,
                               image_url=image_url,
                               character_name=character)
    except Exception as e:
        logging.error("Server error in chat_as_character_view: %s", e)
        traceback.print_exc()
        return "Internal server error", 500

@main.route("/plex-webhook", methods=["POST"])
def plex_webhook():
    if request.method != "POST":
        return "Method Not Allowed", 405
    try:
        logging.info("Payload received:")
        try:
            logging.info(json.dumps(payload, indent=2))
        except Exception as logging_error:
            logging.warning(f"Failed to log payload: {logging_error}")
        if request.is_json:
            payload = request.get_json()
        else:
            payload = request.form.to_dict()
            try:
                import urllib.parse
                payload = json.loads(urllib.parse.unquote_plus(payload.get('payload', '{}')))
            except Exception as decode_err:
                logging.warning(f"Failed to decode form payload: {decode_err}")
                return "Invalid payload format", 400

        if not payload or "Metadata" not in payload:
            logging.warning("Invalid or missing Metadata in payload.")
            return "Invalid payload", 400

        show_title = payload["Metadata"].get("grandparentTitle") or payload["Metadata"].get("title")
        season = payload["Metadata"].get("parentIndex", 0)
        episode = payload["Metadata"].get("index", 0)

        if not show_title:
            logging.warning("Missing show title in metadata.")
            return jsonify({"status": "error", "message": "Missing show title"}), 400

        username = payload.get("Account", {}).get("title", "Unknown")
        logging.info(f"✔️ Webhook: {username} is watching {show_title} S{season}E{episode}")

        try:
            db = sqlite3.connect("data/shownotes.db")
            db.execute("""
                CREATE TABLE IF NOT EXISTS current_watch (
                    id INTEGER PRIMARY KEY,
                    show_title TEXT NOT NULL,
                    season INTEGER,
                    episode INTEGER,
                    username TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS webhook_log (
                    id INTEGER PRIMARY KEY,
                    show_title TEXT,
                    season INTEGER,
                    episode INTEGER,
                    username TEXT,
                    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            db.execute("""
                INSERT INTO webhook_log (show_title, season, episode, username)
                VALUES (?, ?, ?, ?)
            """, (show_title, int(season), int(episode), username))

            cursor = db.execute("""
                SELECT COUNT(*) FROM current_watch 
                WHERE show_title = ? AND season = ? AND episode = ? AND username = ?
                  AND updated_at >= datetime('now', '-1 minute')
            """, (show_title, int(season), int(episode), username))

            if cursor.fetchone()[0] == 0:
                db.execute("""
                    INSERT INTO current_watch (show_title, season, episode, username)
                    VALUES (?, ?, ?, ?)
                """, (show_title, int(season), int(episode), username))
                logging.info(f"Database updated with: {show_title} S{season}E{episode}")
            else:
                logging.info(f"Duplicate webhook skipped for: {show_title} S{season}E{episode}")

            db.commit()
            db.close()
        except Exception as db_error:
            logging.error(f"Failed to update current_watch: {db_error}")
            return jsonify({"status": "error", "message": "Database update failed"}), 500

        # Auto-refresh metadata
        try:
            logging.info(f"Starting metadata population for: {show_title}")
            populate_metadata(show_title)
            logging.info(f"Metadata populated for: {show_title}")
        except Exception as meta_error:
            logging.error(f"Error populating metadata for {show_title}: {meta_error}")
            return jsonify({"status": "error", "message": f"Metadata update failed for {show_title}"}), 500

        return jsonify({
            "status": "success",
            "message": f"Recorded watch event for {show_title} S{season}E{episode} by {username}"
        }), 200
    except Exception as e:
        logging.error(f"Error processing Plex webhook: {e}")
        return jsonify({"status": "error", "message": "Unexpected error processing webhook"}), 500

@main.route("/")
def index():
    latest_show = None
    current_season = None
    current_episode = None
    recent_shows = []

    try:
        db = sqlite3.connect("data/shownotes.db")
        cursor = db.execute("SELECT show_title, season, episode FROM current_watch ORDER BY updated_at DESC LIMIT 1")
        row = cursor.fetchone()

        if row:
            latest_show, current_season, current_episode = row
        else:
            cursor = db.execute("""
                SELECT DISTINCT show_title
                FROM character_summaries
                ORDER BY timestamp DESC
                LIMIT 5
            """)
            recent_shows = [r[0] for r in cursor.fetchall()]
        db.close()
    except Exception as e:
        logging.error(f"Error reading from database: {e}")

    show_metadata = get_show_metadata(latest_show) if latest_show else None
    seasons = get_season_metadata(latest_show) if latest_show else []
    top_characters = get_top_characters(latest_show) if latest_show else []
    backdrop_url = get_show_backdrop(latest_show) if latest_show else None
    season_banner_path = None
    if latest_show and current_season:
        try:
            db = sqlite3.connect("data/shownotes.db")
            cursor = db.execute("SELECT poster_url FROM seasons WHERE title = ? AND season_number = ?", (latest_show, current_season))
            row = cursor.fetchone()
            db.close()
            if row:
                season_banner_path = row[0]
        except Exception as e:
            logging.warning(f"Failed to fetch season banner for {latest_show} S{current_season}: {e}")

    actor_images = {}
    for character, actor, _ in top_characters[:10]:
        person = find_actor_by_name(latest_show, character)
        if person and person.get("profile_path"):
            image_url = f"https://image.tmdb.org/t/p/w185{person['profile_path']}"
            actor_images[character] = image_url

    return render_template(
        "index.html",
        latest_show=latest_show,
        show_metadata=show_metadata,
        seasons=seasons,
        top_characters=top_characters,
        actor_images=actor_images,
        backdrop_url=backdrop_url,
        season_banner_path=season_banner_path,
        current_season=current_season,
        current_episode=current_episode,
        recent_shows=recent_shows
    )


@main.route('/admin/summaries/')
def admin_summaries():
    db_path = os.path.join("data", "shownotes.db")
    summaries = []

    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT character_name, show_title, season_limit, episode_limit, timestamp
            FROM character_summaries
            ORDER BY timestamp DESC
            LIMIT 50
        """)
        summaries = cursor.fetchall()
        conn.close()

    return render_template("admin_summaries.html", summaries=summaries)

@main.route('/admin/api-usage')
def admin_api_usage():
    usage_records = []
    try:
        db = sqlite3.connect("data/shownotes.db")
        cursor = db.execute("""
            SELECT character, show, prompt_tokens, completion_tokens, total_tokens, cost, timestamp
            FROM api_usage
            ORDER BY timestamp DESC
            LIMIT 100
        """)
        usage_records = cursor.fetchall()
        db.close()
    except Exception as e:
        logging.error(f"Error fetching API usage data: {e}")

    return render_template("api_usage.html", usage_records=usage_records)

@main.route('/populate-metadata/<show_title>')
def populate_metadata(show_title):
    try:
        logging.info(f"Attempting to fetch metadata for show: {show_title}")
        results = search_tmdb(show_title, 'tv').get('results', [])
        logging.info(f"TMDB search found {len(results)} result(s) for {show_title}")
        if not results:
            logging.warning(f"No results found for {show_title}.")
            return f"No results found for {show_title}", 404

        show = results[0]
        description = show.get('overview', 'No description available.')
        poster_url = f"https://image.tmdb.org/t/p/w500{show.get('poster_path')}" if show.get('poster_path') else None
        logging.info(f"Poster URL for {show_title}: {poster_url}")
        logging.info(f"Selected show: {show}")
        logging.info(f"Show ID: {show.get('id')}, Description: {description}")

        save_show_metadata(show.get('id'), show_title, description, poster_url)
        logging.info("Saved show metadata.")

        season_description = "Placeholder description"  # Replace with real data later
        season_poster_url = None  # Replace with real data later
        seasons = get_season_details(show.get('id'))
        logging.info(f"Found {len(seasons)} season(s) for {show_title}")
        for season_data in seasons:
            try:
                season_number = season_data[0]
                logging.info(f"Processing season {season_number} for {show_title}")
                season_description = season_data[1] if len(season_data) > 1 else "No description available."
                season_poster_url = season_data[2] if len(season_data) > 2 else None
                save_season_metadata(show_title, season_number, season_description, season_poster_url)
            except Exception as season_error:
                logging.warning(f"Failed to process season data {season_data}: {season_error}")
        logging.info("Saved season metadata.")

        character_list = get_cast(show.get('id'), 'tv')
        save_top_characters(show_title, character_list)
        logging.info("Saved top characters.")

        return f"Metadata saved for {show_title}", 200
    except Exception as e:
        logging.error("Error saving metadata: %s", e)
        traceback.print_exc()
        return f"Failed to save metadata for {show_title}", 500

@main.route('/show/<show_title>')
def show_detail(show_title):
    try:
        show_metadata = get_show_metadata(show_title)
        seasons = get_season_metadata(show_title)
        # Count episodes per season accurately
        season_counts = {}
        for row in get_season_metadata(show_title):
            if len(row) >= 4:
                season_num = row[0]
                season_counts[season_num] = season_counts.get(season_num, 0) + 1
        top_characters = get_top_characters(show_title)
        # Build actor image dictionary
        actor_images = {}
        for character, actor, _ in top_characters:
            person = find_actor_by_name(show_title, character)
            if person and person.get("profile_path"):
                image_url = f"https://image.tmdb.org/t/p/w300{person['profile_path']}"
                # logging.info(f"Image URL for {character}: {image_url}")
                actor_images[character] = image_url
        backdrop_url = get_show_backdrop(show_title)

        # Build a dictionary mapping season numbers to a list of (episode_number, title)
        season_episodes = {}
        for row in get_season_metadata(show_title):
            if len(row) >= 5:
                season_num, _, _, ep_num, ep_title = row
                season_episodes.setdefault(season_num, []).append((ep_num, ep_title))

        logging.info(f"Top characters for {show_title}: {top_characters}")
        return render_template(
            "show.html",
            latest_show=show_title,
            show_metadata=show_metadata,
            seasons=seasons,
            top_characters=top_characters,
            backdrop_url=backdrop_url,
            season_episodes=season_episodes,
            season_counts=season_counts,
            actor_images=actor_images
        )
    except Exception as e:
        logging.error(f"Failed to load show page for {show_title}: {e}")
        return f"Unable to load details for {show_title}", 500

@main.route('/debug-db')
def debug_db():
    rows = []
    try:
        db = sqlite3.connect("data/shownotes.db")
        cursor = db.execute("""
            SELECT show_title, season, episode, username, updated_at
            FROM current_watch
            ORDER BY updated_at DESC
            LIMIT 10
        """)
        rows = cursor.fetchall()
        db.close()
    except Exception as e:
        logging.error(f"Error fetching debug DB data: {e}")

    return render_template("debug-db.html", rows=rows)

@main.route('/admin/init-db')
def init_db():
    try:
        db = sqlite3.connect("data/shownotes.db")
        db.execute("""
            CREATE TABLE IF NOT EXISTS api_usage (
                id INTEGER PRIMARY KEY,
                character TEXT,
                show TEXT,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                cost REAL,
                timestamp TEXT
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS shows (
                id INTEGER PRIMARY KEY,
                tmdb_id INTEGER,
                title TEXT,
                description TEXT,
                poster_url TEXT
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS seasons (
                id INTEGER PRIMARY KEY,
                title TEXT,
                season_number INTEGER,
                description TEXT,
                poster_url TEXT
            )
        """)
        db.commit()
        db.close()
        return "api_usage, shows, and seasons tables initialized.", 200
    except Exception as e:
        logging.error(f"Failed to initialize database tables: {e}")
        return "Database initialization failed.", 500

@main.route("/admin/refresh-show")
def refresh_show_metadata():
    latest_show = get_latest_show_title_from_db()
    if not latest_show:
        return "No recent show found.", 400

    try:
        populate_metadata(latest_show)
        return f"Metadata refreshed for: {latest_show}", 200
    except Exception as e:
        return f"Error: {e}", 500

@main.route('/admin/recreate-current-watch')
def recreate_current_watch():
    try:
        db = sqlite3.connect("data/shownotes.db")
        db.execute("DROP TABLE IF EXISTS current_watch")
        db.execute("""
            CREATE TABLE current_watch (
                id INTEGER PRIMARY KEY,
                show_title TEXT NOT NULL,
                season INTEGER,
                episode INTEGER,
                username TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.commit()
        db.close()
        return "current_watch table recreated.", 200
    except Exception as e:
        return f"Error recreating table: {e}", 500

@main.route("/admin/test-webhook")
def test_webhook():
    import requests
    import json
    test_payload = {
        "Metadata": {
            "grandparentTitle": "For All Mankind",
            "parentIndex": 3,
            "index": 7
        },
        "Account": {
            "title": "testuser"
        }
    }
    try:
        headers = {"Content-Type": "application/json"}
        resp = requests.post("http://127.0.0.1:5002/plex-webhook", headers=headers, json=test_payload)
        status_code = resp.status_code
        response_text = resp.text
        formatted_payload = json.dumps(test_payload, indent=2)
        return f"""
              <h2>Webhook Test Sent</h2>
              <p><strong>Status Code:</strong> {status_code}</p>
              <h3>Sent Payload:</h3>
              <pre>{formatted_payload}</pre>
              <h3>Webhook Response:</h3>
              <pre>{response_text}</pre>
          """, 200
    except Exception as e:
        return f"<h2>Webhook Test Failed</h2><pre>{e}</pre>", 500

@main.route('/admin/test-character-summary')
def test_character_summary():
    from app.utils import summarize_character

    character = "Ellie Williams"
    show = "The Last of Us"
    season = 1
    episode = 3
    options = {
        "include_relationships": True,
        "include_motivations": True,
        "include_themes": True,
        "include_quote": True,
        "tone": "tv_expert"
    }

    parsed, raw = summarize_character(character, show, season, episode, options)
    return f"<h2>Summary for {character} from {show} (S{season}E{episode})</h2><pre>{raw}</pre>"

@main.route('/admin/autocomplete-log')
def admin_autocomplete_log():
    logs = []
    try:
        db = sqlite3.connect("data/shownotes.db")
        cursor = db.execute("""
            SELECT term, type, timestamp
            FROM autocomplete_logs
            ORDER BY timestamp DESC
            LIMIT 100
        """)
        logs = cursor.fetchall()
        db.close()
    except Exception as e:
        logging.error(f"Error fetching autocomplete log data: {e}")
    return render_template("admin_autocomplete_log.html", logs=logs)

@main.route('/admin/webhook-log')
def admin_webhook_log():
    logs = []
    try:
        db = sqlite3.connect("data/shownotes.db")
        cursor = db.execute("""
            SELECT show_title, season, episode, username, received_at
            FROM webhook_log
            ORDER BY received_at DESC
            LIMIT 100
        """)
        logs = cursor.fetchall()
        db.close()
    except Exception as e:
        logging.error(f"Error fetching webhook log data: {e}")
    return render_template("admin_webhook_log.html", logs=logs)

@main.route('/log-autocomplete-selection', methods=['POST'])
def log_autocomplete_selection():
    data = request.get_json()
    term = data.get('term')
    field_type = data.get('type')  # 'show' or 'character'
    timestamp = datetime.utcnow().isoformat()

    try:
        db = sqlite3.connect("data/shownotes.db")
        db.execute("""
            CREATE TABLE IF NOT EXISTS autocomplete_logs (
                id INTEGER PRIMARY KEY,
                term TEXT,
                type TEXT,
                timestamp TEXT
            )
        """)
        db.execute("""
            INSERT INTO autocomplete_logs (term, type, timestamp)
            VALUES (?, ?, ?)
        """, (term, field_type, timestamp))
        db.commit()
        db.close()
        return '', 204
    except Exception as e:
        logging.error(f"Failed to log autocomplete selection: {e}")
        return 'Error', 500
@main.route('/calendar/full')
def calendar_full_data():
    try:
        data = fetch_sonarr_calendar(days=7)
        events = []

        for show in data:
            events.append({
                "title": f"{show['series']['title']} - S{show['seasonNumber']}E{show['episodeNumber']}",
                "start": show['airDateUtc'],
                "end": show['airDateUtc'],  # optional; could estimate with runtime if needed
                "description": show.get('overview', '')
            })

        return jsonify(events)

    except Exception as e:
        logging.exception("Error generating FullCalendar event data")
        return jsonify({"error": str(e)}), 500