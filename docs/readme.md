# 📺 ShowNotes App - Project Snapshot

## ✅ What’s Working

### 🔍 Autocomplete
- `show` and `character` fields use `/autocomplete/shows` and `/autocomplete/characters` endpoints
- Suggestions appear and can be clicked to populate the field
- Context is passed correctly for character autocomplete

### 🧠 Character Summary Page
- Character summary form posts to `/character-summary`
- Inputs: `show`, `character`, `max season`, `max episode`
- API call to ChatGPT succeeds
- TMDB image is shown for the character
- Summary renders with:
  - Personality traits
  - Key events
  - Relationships
  - Importance to the story
  - Notable quote
- Basic layout and centering are functional

### 🛠 Backend
- Routes are organized under `main` Blueprint
- ChatGPT summaries and TMDB calls work
- SQLite logging is in place for future summaries

---

## 🐞 Known Issues / Not Working

### ❌ Autocomplete Keyboard Navigation
- Up/down arrow key selection is currently not functional
- Was working previously; may have regressed with modular JS refactor

### ❌ Summary Field Formatting
- Some summary fields show `"Not available"` even when ChatGPT returns a response
- Could be caused by formatting inconsistencies in ChatGPT output or parsing logic

### ❌ General UI
- Some form elements (e.g., input underline artifacts) need cleanup
- Styling lacks mobile responsiveness in some views
- Double colons (e.g., `Notable Quote: :`) appear in some summary sections

---

## 📋 Core Components and Inputs

### Inputs and HTML IDs
- `show` — the selected TV show or movie
- `character` — character name (autocomplete based on show)
- `season` — spoiler-safe max season
- `episode` — spoiler-safe max episode
- `suggestions-show` — dropdown container for show autocomplete
- `suggestions-character` — dropdown container for character autocomplete

### Summary Sections
- `summary['traits']`
- `summary['events']`
- `summary['relationships']`
- `summary['importance']`
- `summary['quote']`

---

## 🧩 Functions You Can Reuse

### Python (Backend)
- `search_tmdb(query, type)`
- `get_cast(id, media_type)`
- `find_actor_by_name(show, character)`
- `get_character_summary(character, show, season, episode)`
- `parse_character_summary(raw_text)`

### JavaScript (Frontend)
- `setupAutocomplete(inputId, suggestionId, endpoint, getContext)`
- Keyboard navigation support: `keydown`, `ArrowUp`, `ArrowDown`, `Enter`
- Context-aware character lookups tied to selected show

---

## 🔜 Suggested Next Tasks

1. Fix keyboard navigation in autocomplete
2. Improve robustness of `parse_character_summary()` for missing or inconsistent data
3. Style character summary card to match rest of app (mobile-first polish)
4. Standardize layout across all forms and cards for consistency
5. Create reusable template block for summary + chat output formatting
6. Add error messages or fallbacks when summary generation fails

---

## 📦 Notes for Backup

- This snapshot reflects the project status as of **April 19, 2025**
- Static assets, routes, and templates are organized and functioning
- Safe to create a ZIP or GitHub commit from this version