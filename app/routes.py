from flask import Blueprint, render_template, request, jsonify
from markupsafe import Markup
import os
import sqlite3
import traceback
import logging
import json

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
    get_latest_show_title_from_db
)
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
    query = request.args.get('q', '')
    results_tv = search_tmdb(query, 'tv').get('results', [])
    results_movie = search_tmdb(query, 'movie').get('results', [])
    titles = {result.get('name') or result.get('title') for result in results_tv + results_movie}
    return jsonify(list(titles)[:10])

@main.route('/autocomplete/characters')
def autocomplete_characters():
    query = request.args.get('q', '')
    context = request.args.get('context', '')
    res_tv = search_tmdb(context, 'tv').get('results', [])
    res_mv = search_tmdb(context, 'movie').get('results', [])
    result = (res_tv + res_mv)[0] if (res_tv + res_mv) else None

    if not result:
        logging.warning("No result found for context.")
        return jsonify([])

    media_type = 'tv' if result in res_tv else 'movie'
    cast = get_cast(result['id'], media_type)

    suggestions = []
    seen = set()
    query_lc = query.lower()

    for actor in cast:
        char_name = actor.get('character', '')
        actor_name = actor.get('name', '')

        if query_lc in char_name.lower() and char_name.lower() not in seen:
            suggestions.append(f"{char_name} ({actor_name})")
            seen.add(char_name.lower())
        elif query_lc in actor_name.lower() and actor_name.lower() not in seen:
            suggestions.append(f"{char_name} ({actor_name})" if char_name else actor_name)
            seen.add(actor_name.lower())

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
            summary, raw_summary = summarize_character(character, show, season, episode)
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
    try:
        if request.is_json:
            payload = request.get_json()
        else:
            payload = request.form.to_dict()
            try:
                import urllib.parse
                payload = json.loads(urllib.parse.unquote_plus(payload.get('payload', '{}')))
            except Exception as decode_err:
                logging.warning(f"Failed to decode form payload: {decode_err}")

        if not payload or "Metadata" not in payload:
            return "Invalid payload", 400

        show_title = payload["Metadata"].get("grandparentTitle") or payload["Metadata"].get("title")
        season = payload["Metadata"].get("parentIndex")
        episode = payload["Metadata"].get("index")

        if show_title:
            # Store current watch in database
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
            db.execute("DELETE FROM current_watch")
            username = payload.get("Account", {}).get("title", "Unknown")
            db.execute("INSERT INTO current_watch (show_title, season, episode, username) VALUES (?, ?, ?, ?)",
                       (show_title, season, episode, username))
            db.commit()
            db.close()

            logging.info(f"Plex Webhook: Updated DB with {show_title} S{season}E{episode}")

            # Auto-refresh metadata
            populate_metadata(show_title)
        return "", 204
    except Exception as e:
        logging.error(f"Error processing Plex webhook: {e}")
        return "Error", 500

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

    return render_template(
        "index.html",
        latest_show=latest_show,
        show_metadata=show_metadata,
        seasons=seasons,
        top_characters=top_characters,
        backdrop_url=backdrop_url,
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
        logging.info(f"TMDB search results: {results}")
        if not results:
            logging.warning(f"No results found for {show_title}.")
            return f"No results found for {show_title}", 404

        show = results[0]
        description = show.get('overview', 'No description available.')
        poster_url = f"https://image.tmdb.org/t/p/w500{show.get('poster_path')}" if show.get('poster_path') else None
        logging.info(f"Selected show: {show}")
        logging.info(f"Show ID: {show.get('id')}, Description: {description}")

        save_show_metadata(show.get('id'), show_title, description, poster_url)
        logging.info("Saved show metadata.")

        season_description = "Placeholder description"  # Replace with real data later
        season_poster_url = None  # Replace with real data later
        seasons = get_season_details(show.get('id'))
        for season_number, season_description, season_poster_url in seasons:
            save_season_metadata(show_title, season_number, season_description, season_poster_url)
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
                actor_images[character] = f"https://image.tmdb.org/t/p/w300{person['profile_path']}"
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

    return render_template("debug_db.html", rows=rows)

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
        db.commit()
        db.close()
        return "api_usage table initialized.", 200
    except Exception as e:
        logging.error(f"Failed to initialize API usage table: {e}")
        return "Database initialization failed.", 500
