# ShowNotes / Venn-Cast Project Context Export

This file summarizes the goals, features, architecture, and development context for the `ShowNotes` (formerly `Venn-Cast`) project. It can be used for onboarding, transferring to another AI instance, or maintaining continuity across development machines.

---

## 🧭 Project Overview

**Name:** ShowNotes (a.k.a. Venn-Cast)  
**Type:** Flask-based media metadata app  
**Purpose:**  
A tool for exploring relationships between TV characters and actors across shows. Supports character summaries, overlap detection, actor insights, and spoiler-aware recaps based on viewing progress.

---

## ⚙️ Tech Stack

- **Backend:** Python 3, Flask
- **Database:** SQLite3 (`data/shownotes.db`)
- **APIs:**
  - TMDB API for metadata and casting
  - OpenAI API (GPT-4) for character summaries and in-character replies

---

## 🔑 Environment Variables

Make sure the following are set, typically via a `.env` file:

```env
OPENAI_API_KEY=your_key_here
TMDB_API_KEY=your_key_here
```

---

## 📁 Key Files & Modules

- `app/utils.py`: All major logic, including TMDB calls, summary generation, database operations
- `app/routes.py`: Flask route handlers (not included above, but assumed)
- `data/shownotes.db`: Primary SQLite3 database

---

## 🧠 Core Features

### 🔎 Actor & Character Search
- `search_tmdb()`: Finds show/movie by name
- `find_actor_by_name()`: Finds actor by character name in a show
- `get_cast()`: Retrieves cast list and episode info

### 🧵 Character Summary System
- `summarize_character()`: Generates and parses a structured character summary
- `get_character_summary()`: Prompts GPT for structured sections (traits, events, relationships, quote, importance)
- `parse_character_summary()`: Extracts and cleans structured data
- `save_character_summary_to_db()`, `get_cached_summary()`: SQLite caching

### 🧬 Actor Insights
- `get_actor_details()`: Builds enriched profile including known-for roles and links
- `get_known_for()`: Most popular appearances

### 🧙 In-Character AI Chat
- `chat_as_character()`: Roleplays as a character using GPT-4

### 🗃️ Metadata Management
- `save_show_metadata()` / `get_show_metadata()`
- `save_season_metadata()` / `get_season_metadata()`
- `get_show_backdrop()`: Gets show image for headers
- `get_reference_links()`: Wikipedia, Fandom, IMDb, TMDB links

### 🌟 Character Ranking
- `save_top_characters()` / `get_top_characters()`: Track main characters by episode count

---

## 🧪 Setup Instructions

1. **Clone repo or unzip files**
2. **Create `.env` file** with your keys
3. **Install dependencies**  
   ```bash
   pip install -r requirements.txt
   ```
4. **Run Flask app**
   ```bash
   flask run
   ```
   or use `gunicorn` or `systemd` for deployment

5. **Database:** Pre-created, but you can inspect `data/shownotes.db` with any SQLite viewer

---

## 🛣️ Future To-Dos & Ideas

- [ ] Visualize character relationships and timelines
- [ ] Add Plex webhook support to track viewing
- [ ] Include actor overlap Venn diagrams
- [ ] Create spoiler-free recaps
- [ ] Add simple login/auth for Plex friends
- [ ] Optimize caching and reduce GPT calls
- [ ] Support multiple spoiler versions of summaries

---

## 🧭 How to Use This with ChatGPT

To resume working with ChatGPT after a break or across accounts, provide:
- This file as context
- Your `.env` keys (manually, if needed)
- Your zipped repo or folder path

---

## ✍️ Maintained by

**Scott Woods-Fehr**  
Plex server host, educator, and media metadata enthusiast.

---