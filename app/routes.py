from flask import Blueprint, render_template, request, jsonify

from markupsafe import Markup
import os

import traceback
from app.utils import (
    search_tmdb,
    get_cast,
    get_actor_details,
    chat_as_character,
    find_actor_by_name,
    get_character_summary,
    parse_character_summary,
    summarize_character,
    save_character_summary_to_db,
    get_cached_summary,
    get_all_characters_for_show,
    get_latest_show_title_from_db
)
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
from app.utils import save_character_summary_to_db, get_cached_summary, get_show_backdrop
main = Blueprint('main', __name__)

import logging
logging.basicConfig(level=logging.INFO)


@main.route('/compare', methods=['POST'])
def compare():
    title1 = request.form.get('title1')
    title2 = request.form.get('title2')

    # Search both TV and Movie for title1
    res1_tv = search_tmdb(title1, 'tv').get('results', [])
    res1_mv = search_tmdb(title1, 'movie').get('results', [])
    result1 = (res1_tv + res1_mv)[0] if (res1_tv + res1_mv) else None

    # Search both TV and Movie for title2
    res2_tv = search_tmdb(title2, 'tv').get('results', [])
    res2_mv = search_tmdb(title2, 'movie').get('results', [])
    result2 = (res2_tv + res2_mv)[0] if (res2_tv + res2_mv) else None

#logging.info(f"TMDB Search 1: {res1_tv + res1_mv}")

    if not result1 or not result2:
        return f"Could not find one or both titles: {title1}, {title2}"

    id1 = result1['id']
    id2 = result2['id']
    type1 = 'tv' if result1 in res1_tv else 'movie'
    type2 = 'tv' if result2 in res2_tv else 'movie'

    # Get cast for each show
    cast1 = get_cast(id1, type1)
    cast2 = get_cast(id2, type2)

    # Tag each actor with show ID
    for actor in cast1:
        actor['show_id'] = id1
    for actor in cast2:
        actor['show_id'] = id2

    # Compare by shared names
    names1 = {actor['name'] for actor in cast1}
    names2 = {actor['name'] for actor in cast2}
    shared = sorted(names1 & names2)
    
    from app.db import log_overlap_query
    log_overlap_query(title1, title2, len(shared))
    
    overlap = []

    for actor in cast1 + cast2:
        name = actor['name']
        if name in names1 and name in names2:
            ep_count = actor.get('episode_count') or 0
            try:
                ep_count = int(ep_count)
            except:
                ep_count = 0
            overlap.append((name, ep_count))

    # Get the highest episode count for each actor
    from collections import defaultdict
    episode_map = defaultdict(int)

    for name, ep in overlap:
        episode_map[name] = max(episode_map[name], ep)

    # Now sort by episode count (descending)
    shared_sorted = sorted(episode_map.items(), key=lambda x: x[1], reverse=True)
    shared = [name for name, _ in shared_sorted]

    # Build filtered_cast and top_names
    TOP_N = 20
    top_names = set(shared[:TOP_N])
    filtered_cast = [a for a in cast1 + cast2 if a['name'] in top_names]

    # Get detailed actor info
    actor_details = get_actor_details(
        filtered_cast,
        (title1, id1, type1),
        (title2, id2, type2),
        top_names
    )

#    print("Actor details:", actor_details)

    return render_template(
        'overlap_results.html',
        title1=title1,
        title2=title2,
        shared=shared,
        actor_details=actor_details,
        count=len(shared)
    )

@main.route('/autocomplete/shows')
def autocomplete_shows():
    query = request.args.get('q', '')
    results_tv = search_tmdb(query, 'tv').get('results', [])
    results_movie = search_tmdb(query, 'movie').get('results', [])
    titles = set()

    for result in results_tv + results_movie:
        title = result.get('name') or result.get('title')
        if title:
            titles.add(title)

    return jsonify(list(titles)[:10])


@main.route('/autocomplete/characters')
def autocomplete_characters():
    query = request.args.get('q', '')
    context = request.args.get('context', '')

    res_tv = search_tmdb(context, 'tv').get('results', [])
    res_mv = search_tmdb(context, 'movie').get('results', [])
    result = (res_tv + res_mv)[0] if (res_tv + res_mv) else None

    if not result:
        return jsonify([])

    media_type = 'tv' if result in res_tv else 'movie'
    cast = get_cast(result['id'], media_type)
    seen = set()
    suggestions = []

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
#### Character Info
from app.utils import summarize_character  # make sure this is imported

@main.route('/character-summary', methods=['GET', 'POST'])
def character_summary():
    raw_summary = None
    summary = None
    image_url = None
    character = ""
    show = ""
    season = 1
    episode = 1
    source = None
    other_characters = None
    reference_links = None

    if request.method == 'POST':
        show = request.form.get("show")
        character = request.form.get("character")
        # Remove actor name in parentheses, if present
        if '(' in character:
            character = character.split('(')[0].strip()
        season = request.form.get("season", type=int)
        episode = request.form.get("episode", type=int)

        # Step 4: Check cache first
        summary, raw_summary = get_cached_summary(character, show, season, episode)
        source = "cache" if summary else "generated"

        # Step 3: If no cached version, call OpenAI and save result
        if not summary:
            summary, raw_summary = summarize_character(character, show, season, episode)
            save_character_summary_to_db(character, show, season, episode, raw_summary, summary)

        actor = find_actor_by_name(show, character)
        if actor and actor.get("profile_path"):
            image_url = f"https://image.tmdb.org/t/p/w185{actor['profile_path']}"
        other_characters = get_all_characters_for_show(show)  # implement this using your TMDB logic

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
                           reference_links=reference_links
                    )
                           
@main.route('/chat-as-character', methods=["GET", "POST"])
def chat_as_character_view():
    try:
        reply = None
        message = None
        character = request.form.get('character') if request.method == 'POST' else 'Walter White'
        show = request.form.get('show') if request.method == 'POST' else 'Breaking Bad'

        if request.method == 'POST':
            message = request.form.get('message')
            reply = chat_as_character(character, show, message)

        # Pull character image from TMDB if available
        actor = find_actor_by_name(show, character)  # You may need to adjust this
        image_url = f"https://image.tmdb.org/t/p/w185/{actor['profile_path']}" if actor and actor.get('profile_path') else None

        return render_template(
            "chat_as_character.html",
            reply=reply,
            user_message=message,
            show=show,
            character=character,
            image_url=image_url,
            character_name=character
        )

    except Exception as e:
        print("Server error in chat_as_character_view:", e)
        import traceback
        traceback.print_exc()
        return "Internal server error", 500
                        
@main.route("/plex-webhook", methods=["POST"])
def plex_webhook():
    data = request.get_json()
    if data and "Metadata" in data:
        show_title = data["Metadata"].get("grandparentTitle") or data["Metadata"].get("title")
        if show_title:
            # Save it (example: temp file or in-memory for now)
            with open("last_plex_show.txt", "w") as f:
                f.write(show_title)
    return '', 204
    
@main.route('/')
def index():
    latest_show = get_latest_show_title_from_db()
    backdrop_url = get_show_backdrop(latest_show) if latest_show else None
    return render_template("index.html", backdrop_url=backdrop_url, latest_show=latest_show)
    default_show = ""
    try:
        with open("last_plex_show.txt") as f:
            default_show = f.read().strip()
    except FileNotFoundError:
        pass
    return render_template("index.html", default_title=default_show)

from markupsafe import Markup
import sqlite3
import os

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