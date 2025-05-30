# 📦 ShowNotes Logging Plan

This file outlines the structure and goals for adding SQLite-based logging to the ShowNotes app.

## ✅ Goals

- Log every ChatGPT summary or chat query to avoid unnecessary API calls
- Allow lookup of past queries to avoid duplication
- Enable reloading previous character chats
- Create a foundation for a future "History" view per user

## 📁 Database File

Location: `data/shownotes.db`

## 📋 Tables

### character_summaries

- `id` (INTEGER PRIMARY KEY)
- `character_name` (TEXT)
- `show_title` (TEXT)
- `season_limit` (INTEGER)
- `episode_limit` (INTEGER)
- `raw_summary` (TEXT)
- `parsed_traits` (TEXT)
- `parsed_events` (TEXT)
- `parsed_relationships` (TEXT)
- `parsed_importance` (TEXT)
- `parsed_quote` (TEXT)
- `timestamp` (DATETIME DEFAULT CURRENT_TIMESTAMP)

### character_chats

- `id` (INTEGER PRIMARY KEY)
- `character_name` (TEXT)
- `show_title` (TEXT)
- `user_message` (TEXT)
- `character_reply` (TEXT)
- `timestamp` (DATETIME DEFAULT CURRENT_TIMESTAMP)

## 🧠 Query Helpers (Planned)

- Check if summary exists for character/show up to season/episode
- Insert new summary or chat on generation
- Option to "refresh" summary (new row)