from dotenv import load_dotenv
import os
import requests
import sqlite3
import re
import json
import logging
from openai import OpenAI
from app.prompt_builder import build_character_prompt

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def search_tmdb(query, media_type='tv'):
    url = f"https://api.themoviedb.org/3/search/{media_type}"
    params = {"api_key": TMDB_API_KEY, "query": query}
    response = requests.get(url, params=params)
    data = response.json()
    if "results" in data:
        for result in data["results"]:
            poster = result.get("poster_path")
            if not poster:
                result["poster_path"] = "/default.jpg"
            elif isinstance(poster, int):
                result["poster_path"] = "/default.jpg"
            elif isinstance(poster, str) and not poster.startswith("/"):
                result["poster_path"] = "/" + poster
    return data

def find_actor_by_name(show, character):
    results_tv = search_tmdb(show, 'tv').get('results', [])
    results_mv = search_tmdb(show, 'movie').get('results', [])
    result = (results_tv + results_mv)[0] if (results_tv + results_mv) else None
    if not result:
        return None
    show_id = result['id']
    media_type = 'tv' if result in results_tv else 'movie'
    cast = get_cast(show_id, media_type)
    character_lower = character.lower()
    for actor in cast:
        char_name = actor.get('character') or ''
        actor_name = actor.get('name') or ''
        if character_lower in char_name.lower() or character_lower in actor_name.lower():
            return actor
    return None

def get_cast(media_id, media_type='tv'):
    if media_type == "tv":
        url = f"https://api.themoviedb.org/3/tv/{media_id}/aggregate_credits"
    else:
        url = f"https://api.themoviedb.org/3/movie/{media_id}/credits"
    response = requests.get(url, params={"api_key": TMDB_API_KEY})
    data = response.json()
    cast = []
    if media_type == "tv":
        for person in data.get("cast", []):
            cast.append({
                "name": person["name"],
                "character": person["roles"][0]["character"] if person.get("roles") else "",
                "episode_count": person["roles"][0]["episode_count"] if person.get("roles") else "",
                "profile_path": person.get("profile_path"),
                "id": person.get("id")
            })
    else:
        for person in data.get("cast", []):
            cast.append({
                "name": person["name"],
                "character": person.get("character", ""),
                "episode_count": "",
                "profile_path": person.get("profile_path"),
                "id": person.get("id")
            })
    return cast

def get_actor_details(cast, show1, show2, top_names=None):
    details = {}
    show_map = {show1[1]: show1[0], show2[1]: show2[0]}
    for actor in cast:
        name = actor.get('name')
        if top_names and name not in top_names:
            continue
        actor_id = actor.get('id')
        if not actor_id:
            continue
        show_id = actor.get('show_id')
        show_title = show_map.get(show_id, "Unknown Show")
        role_info = {
            'character': actor.get('character', ''),
            'episode_count': actor.get('episode_count', '')
        }
        if name not in details:
            known_for = get_known_for(actor_id)
            details[name] = {
                'id': actor_id,
                'image': f"https://image.tmdb.org/t/p/w185{actor.get('profile_path')}" if actor.get('profile_path') else None,
                'tmdb_url': f"https://www.themoviedb.org/person/{actor_id}",
                'shows': {show_title: role_info},
                'known_for': known_for
            }
        else:
            details[name]['shows'][show_title] = role_info
    return details

def get_known_for(person_id):
    url = f"https://api.themoviedb.org/3/person/{person_id}/combined_credits"
    response = requests.get(url, params={"api_key": TMDB_API_KEY})
    if response.status_code != 200:
        return []
    data = response.json()
    credits = data.get('cast', []) + data.get('crew', [])
    seen = set()
    known_for = []
    for credit in sorted(credits, key=lambda c: c.get('popularity', 0), reverse=True):
        title = credit.get('title') or credit.get('name')
        if title and title not in seen:
            known_for.append(title)
            seen.add(title)
        if len(known_for) >= 3:
            break
    return known_for

def chat_as_character(character, show_title, user_message):
    prompt = (
        f"You are {character} from the show {show_title}. Reply to the user as that character would — "
        f"stay in character, use their tone, vocabulary, and personality. "
        f"Do not explain or break the fourth wall. The user says: '{user_message}'"
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.85,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error generating reply: {e}"

def get_character_summary(character, show_title, season, episode, options=None):
    prompt = build_character_prompt(character, show_title, season, episode, options)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def parse_character_summary(text):
    parsed = {
        "quote": None,
        "traits": "Not available.",
        "events": "Not available.",
        "relationships": [],
        "importance": "Not available."
    }

    # Normalize text for consistent parsing
    text = text.replace('\r\n', '\n').strip()

    # Quote: allow quote: to appear on same line or next line, and accept various quote marks
    quote_match = re.search(
        r'## Notable Quote\s*(?:quote:\s*)?(?:[“"]?(.+?)[”"]?\s*)?(?=\n##|\Z)',
        text, re.DOTALL)
    if quote_match and quote_match.group(1):
        parsed["quote"] = quote_match.group(1).strip()

    # Traits: support YAML-like and markdown-style lists
    traits_section = re.search(r'## Personality & Traits\s*(?:traits:\s*)?((?:- .+\n?)+)', text)
    if traits_section:
        parsed["traits"] = [line.strip('- ').strip() for line in traits_section.group(1).splitlines() if line.strip()]
    else:
        parsed["traits"] = "Not available."

    # Events: support YAML-like and markdown-style lists
    events_section = re.search(r'## Key Events\s*(?:events:\s*)?((?:- .+\n?)+)', text)
    if events_section:
        parsed["events"] = [line.strip('- ').strip() for line in events_section.group(1).splitlines() if line.strip()]
    else:
        parsed["events"] = "Not available."

    # Relationships: support nested indentation and more robust block grouping
    rel_section = re.search(r'## Significant Relationships\s*((?:relationship_\d+:\s*[\s\S]+?)(?=\n\S|$))', text)
    if rel_section:
        rel_blocks = re.findall(
            r'relationship_\d+:\s*name:\s+"(.*?)"\s+role:\s+"(.*?)"\s+description:\s+"(.*?)"',
            rel_section.group(1), re.DOTALL)
        parsed["relationships"] = [(f"{name} ({role})", desc.strip()) for name, role, desc in rel_blocks]
    # After parsing, exclude results if relationships is empty
    if not parsed["relationships"]:
        parsed["relationships"] = []

    # Importance: get text after ## Importance to the Story until next header
    importance_section = re.search(r'## Importance to the Story\s*(.+?)(?=\n##|\Z)', text, re.DOTALL)
    if importance_section:
        parsed["importance"] = importance_section.group(1).strip()

    # If quote is empty string, set to None
    if parsed["quote"] is not None and parsed["quote"].strip() == "":
        parsed["quote"] = None

    # Fallback: format traits and events appropriately
    if isinstance(parsed["traits"], list):
        cleaned_traits = [t.strip().strip('"') for t in parsed["traits"] if t.strip()]
        parsed["traits"] = ", ".join(cleaned_traits) if cleaned_traits else "Not available."
    if isinstance(parsed["events"], list):
        cleaned_events = ['- ' + e.strip().strip('"') for e in parsed["events"] if isinstance(e, str) and e.strip()]
        parsed["events"] = "\n".join(cleaned_events) if cleaned_events else "Not available."

    return parsed
    
def save_character_summary_to_db(character, show_title, season, episode, raw_summary, parsed):
    conn = sqlite3.connect("data/shownotes.db")
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO character_summaries (
            character_name, show_title, season_limit, episode_limit,
            raw_summary, parsed_traits, parsed_events, parsed_relationships,
            parsed_importance, parsed_quote
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        character, show_title, season, episode, raw_summary,
        json.dumps(parsed.get('traits', [])), 
        json.dumps(parsed.get('events', [])),
        json.dumps(parsed.get('relationships', [])),  
        parsed.get('importance'),
        parsed.get('quote')
    ))
    conn.commit()
    conn.close()
    print(f"Saved summary to DB for {character} in {show_title} S{season}E{episode}")


def get_cached_summary(character, show_title, season, episode):
    conn = sqlite3.connect("data/shownotes.db")
    cursor = conn.cursor()
    cursor.execute('''
        SELECT parsed_traits, parsed_events, parsed_relationships,
               parsed_importance, parsed_quote, raw_summary
        FROM character_summaries
        WHERE character_name = ? AND show_title = ?
          AND season_limit = ? AND episode_limit = ?
        ORDER BY timestamp DESC
        LIMIT 1
    ''', (character, show_title, season, episode))
    row = cursor.fetchone()
    conn.close()
    if row:
        traits, events, relationships_json, importance, quote, raw = row
        return {
            'traits': traits,
            'events': events,
            'relationships': json.loads(relationships_json) if relationships_json else [], 
            'importance': importance,
            'quote': quote
        }, raw
    return None, None
        
def summarize_character(character, show_title, season, episode, options=None):
    """
    Generates and parses a character summary based on viewing limits.
    Returns a tuple: (parsed_summary_dict, raw_summary_text)
    """
    raw_summary = get_character_summary(character, show_title, season, episode, options)
    parsed = parse_character_summary(raw_summary)
    print("[DEBUG] Raw Summary:\n", raw_summary)
    print("[DEBUG] Parsed Summary Keys:", parsed.keys())
    print("[DEBUG] Parsed Traits:", parsed.get("traits"), type(parsed.get("traits")))
    print("[DEBUG] Parsed Events:", parsed.get("events"), type(parsed.get("events")))
    print("[DEBUG] Parsed Relationships:", parsed.get("relationships"))
    print("[DEBUG] Parsed Importance:", parsed.get("importance"))
    print("[DEBUG] Parsed Quote:", parsed.get("quote"))

    # Estimate token usage (approx. 4 characters per token)
    tokens = len(raw_summary) // 4
    model = "gpt-4"
    cost_per_1k = 0.06  # GPT-4 input cost per 1K tokens
    cost = round((tokens / 1000) * cost_per_1k, 4)

    # Log to api_usage table
    conn = sqlite3.connect("data/shownotes.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO api_usage (character, show, prompt_tokens, completion_tokens, total_tokens, cost, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (character, show_title, tokens, 0, tokens, cost))
    conn.commit()
    conn.close()

    return parsed, raw_summary

def get_all_characters_for_show(show_title, limit=10):
    results_tv = search_tmdb(show_title, 'tv').get('results', [])
    results_mv = search_tmdb(show_title, 'movie').get('results', [])
    result = (results_tv + results_mv)[0] if (results_tv + results_mv) else None

    if not result:
        return []

    media_type = 'tv' if result in results_tv else 'movie'
    cast = get_cast(result['id'], media_type)

    # Sort by episode_count (if available), then name as a fallback
    def sort_key(actor):
        ep_count = 0
        if media_type == 'tv':
            try:
                ep_count = actor.get("roles", [{}])[0].get("episode_count", 0)
                ep_count = int(ep_count)
            except:
                ep_count = 0
        return (-ep_count, actor.get("name", ""))  # negative for descending sort

    sorted_cast = sorted(cast, key=sort_key)

    characters = []
    for actor in sorted_cast:
        char_name = actor.get("character", "")
        if char_name:
            characters.append(char_name.strip())
        if len(characters) >= limit:
            break

    return characters

def get_latest_show_title_from_db():
    conn = sqlite3.connect("data/shownotes.db")
    cursor = conn.cursor()
    cursor.execute('''
        SELECT show_title
        FROM character_summaries
        ORDER BY timestamp DESC
        LIMIT 1
    ''')
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def get_show_backdrop(show_title):
    result = search_tmdb(show_title, 'tv').get('results', [])
    if result:
        backdrop_path = result[0].get("backdrop_path")
        if backdrop_path:
            return f"https://image.tmdb.org/t/p/w780{backdrop_path}"
    return None

def get_reference_links(show_title, actor_name=None):
    links = []

    if show_title:
        wiki_url = f"https://en.wikipedia.org/wiki/{show_title.replace(' ', '_')}"
        fandom_url = f"https://{show_title.lower().replace(' ', '-')}.fandom.com"
        links.append(("Wikipedia", wiki_url))
        links.append(("Fandom Wiki", fandom_url))

    if actor_name:
        tmdb_search = f"https://www.themoviedb.org/search?query={actor_name.replace(' ', '+')}"
        imdb_search = f"https://www.imdb.com/find?q={actor_name.replace(' ', '+')}"
        links.append(("TMDB", tmdb_search))
        links.append(("IMDb", imdb_search))

    return links

def get_latest_show_title_from_db():
    import sqlite3
    db_path = "data/shownotes.db"
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT show_title
            FROM character_summaries
            ORDER BY timestamp DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        print("Error fetching latest show title:", e)
        return None

def get_show_backdrop(title):
    for media_type in ['tv', 'movie']:
        search_url = f"https://api.themoviedb.org/3/search/{media_type}"
        params = {"query": title, "api_key": TMDB_API_KEY}
        response = requests.get(search_url, params=params)
        data = response.json()
        if data.get("results"):
            backdrop_path = data["results"][0].get("backdrop_path")
            if backdrop_path:
                return f"https://image.tmdb.org/t/p/original{backdrop_path}"
    return None

# --- Show Metadata Utilities ---

def save_show_metadata(show_id, show_title, description, poster_url):
    """
    Save show-level metadata to the database.
    """
    # Ensure poster_url is a valid string with a leading slash
    if not poster_url or isinstance(poster_url, int):
        poster_url = "/default.jpg"
    elif isinstance(poster_url, str) and not poster_url.startswith("/"):
        poster_url = "/" + poster_url

    conn = sqlite3.connect("data/shownotes.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO show_metadata (show_id, show_title, description, poster_url)
        VALUES (?, ?, ?, ?)
    """, (show_id, show_title, description, poster_url))
    # Also save to the shows table for season lookup
    try:
        # Attempt to fetch backdrop_path from TMDB details
        details_url = f"https://api.themoviedb.org/3/tv/{show_id}"
        details_resp = requests.get(details_url, params={"api_key": TMDB_API_KEY})
        backdrop_path = None
        if details_resp.status_code == 200:
            show_data = details_resp.json()
            backdrop_path = show_data.get("backdrop_path")
            if backdrop_path and not backdrop_path.startswith("/"):
                backdrop_path = "/" + backdrop_path

        cursor.execute("""
            INSERT OR REPLACE INTO shows (show_id, title, overview, poster_path, backdrop_path)
            VALUES (?, ?, ?, ?, ?)
        """, (
            show_id,
            show_title,
            description,
            poster_url,
            backdrop_path
        ))
    except Exception as e:
        logging.warning(f"Failed to insert into shows table for {show_title}: {e}")

    # Save season metadata
    try:
        seasons = get_season_details(show_id)
        for season in seasons:
            season_number, description, poster_url = season
            cursor.execute("""
                INSERT OR REPLACE INTO season_metadata (
                    show_title, season_number, season_description, season_poster_url
                ) VALUES (?, ?, ?, ?)
            """, (show_title, season_number, description, poster_url))
    except Exception as e:
        logging.warning(f"Failed to insert season metadata for {show_title}: {e}")

    conn.commit()
    conn.close()

def get_show_metadata(show_title):
    """
    Retrieve show metadata by title.
    """
    conn = sqlite3.connect("data/shownotes.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT show_title, show_id, description
        FROM show_metadata
        WHERE show_title = ?
    """, (show_title,))
    row = cursor.fetchone()
    conn.close()
    return row

# --- Season Metadata Utilities ---

def save_season_metadata(show_title, season_number, season_description, season_poster_url):
    """
    Save metadata about a specific season of a show.
    """
    conn = sqlite3.connect("data/shownotes.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO season_metadata (show_title, season_number, season_description, season_poster_url)
        VALUES (?, ?, ?, ?)
    """, (show_title, season_number, season_description, season_poster_url))
    conn.commit()
    conn.close()

def get_season_metadata(show_title):
    """
    Retrieve metadata for all seasons of a given show.
    """
    conn = sqlite3.connect("data/shownotes.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT season_number, season_description, season_poster_url
        FROM season_metadata
        WHERE show_title = ?
        ORDER BY season_number ASC
    """, (show_title,))
    seasons = cursor.fetchall()
    conn.close()
    return seasons

# --- Top Characters Utilities ---

def save_top_characters(show_title, character_list):
    """
    Save top characters for a show. Expects a list of tuples: (character_name, actor_name, episode_count).
    """
    conn = sqlite3.connect("data/shownotes.db")
    cursor = conn.cursor()
    for character in character_list:
        if len(character) >= 3:
            name = character.get("character", "")
            actor = character.get("name", "")
            count = character.get("episode_count", 0)
            cursor.execute("""
                INSERT OR REPLACE INTO top_characters (show_title, character_name, actor_name, episode_count)
                VALUES (?, ?, ?, ?)
            """, (show_title, name, actor, count))
        else:
            logging.warning(f"Skipping character entry due to unexpected format: {character}")
    conn.commit()
    conn.close()

def get_top_characters(show_title, limit=10):
    """
    Retrieve the top characters for a show, sorted by episode count.
    """
    conn = sqlite3.connect("data/shownotes.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT character_name, actor_name, MAX(episode_count) as max_count
        FROM top_characters
        WHERE show_title = ?
        GROUP BY character_name, actor_name
        ORDER BY max_count DESC
        LIMIT ?
    """, (show_title, limit))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_season_details(show_id):
    """
    Fetch metadata for all seasons of a given show from TMDB.
    """
    url = f"https://api.themoviedb.org/3/tv/{show_id}"
    response = requests.get(url, params={"api_key": TMDB_API_KEY})
    if response.status_code != 200:
        logging.error(f"Failed to fetch show metadata for show_id {show_id}")
        return []

    data = response.json()
    seasons = data.get("seasons", [])
    return [
        (
            s.get("season_number"),
            s.get("overview", "No description available."),
            f"https://image.tmdb.org/t/p/w300{s.get('poster_path')}" if s.get("poster_path") else None
        )
        for s in seasons
        if s.get("season_number") != 0  # Skip specials
    ]