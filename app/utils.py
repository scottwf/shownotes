from dotenv import load_dotenv
import os
import requests
import sqlite3
import re
import json
import logging
from openai import OpenAI

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def search_tmdb(query, media_type='tv'):
    url = f"https://api.themoviedb.org/3/search/{media_type}"
    params = {"api_key": TMDB_API_KEY, "query": query}
    response = requests.get(url, params=params)
    return response.json()

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

def get_character_summary(character, show_title, season, episode):
    prompt = f"""
    Summarize the character "{character}" from the show "{show_title}" based only on events up to Season {season}, Episode {episode}.

    Use the following sections and headings **exactly as shown** (with a colon and no extra text):

    - Notable Quote:
    - Personality & Traits:
    - Key Events:
    - Relationships:
    - Importance to the Story:
    """
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def parse_character_summary(text):
    sections = {
        "quote": "Notable Quote",
        "traits": "Personality & Traits",
        "events": "Key Events",
        "relationships": "Relationships",
        "importance": "Importance to the Story"
    }

    def clean_quote(text):
        if not text or text == "Not available.":
            return None
        cleaned = text.strip().strip('"“”').strip("–—").strip()
        # Remove trailing attribution like — Walter White or - Walter
        cleaned = re.sub(r'\s*[-–—]\s*[A-Z][a-z]+.*$', '', cleaned).strip()
        return cleaned

    def extract_section(header):
        start = text.find(header)
        if start == -1:
            return "Not available."
        end = min([
            text.find(h, start + 1)
            for h in sections.values()
            if h != header and text.find(h, start + 1) != -1
        ] + [len(text)])
        content = text[start + len(header):end].strip()
        return content.lstrip(": ").replace("\n", " ").strip()

    parsed = {key: extract_section(header) for key, header in sections.items()}
    parsed['quote'] = clean_quote(parsed.get('quote'))

    # Parse relationships into a list of (name, role)
    rel_lines = parsed.get("relationships", "").split("\n")
    parsed['relationships'] = []
    for line in rel_lines:
        match = re.match(r"[-•]?\s*(.+?)[\s:–-]+\s*(.+)", line.strip())
        if match:
            name, role = match.groups()
            parsed['relationships'].append((name.strip(), role.strip()))
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
        parsed.get('traits'), 
        parsed.get('events'),
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
        
def summarize_character(character, show_title, season, episode):
    """
    Generates and parses a character summary based on viewing limits.
    Returns a tuple: (parsed_summary_dict, raw_summary_text)
    """
    raw_summary = get_character_summary(character, show_title, season, episode)
    parsed = parse_character_summary(raw_summary)
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
    conn = sqlite3.connect("data/shownotes.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO show_metadata (show_id, show_title, description, poster_url)
        VALUES (?, ?, ?, ?)
    """, (show_id, show_title, description, poster_url))
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
            name, actor, count = character[:3]
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
        SELECT character_name, actor_name, episode_count
        FROM top_characters
        WHERE show_title = ?
        ORDER BY episode_count DESC
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