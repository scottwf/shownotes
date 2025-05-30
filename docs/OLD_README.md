

# ShowNotes

ShowNotes is a Flask-based web app that helps users explore TV shows, character arcs, and actor overlap between series. It offers spoiler-aware summaries, relationship mapping, chat-style interaction, and integration with metadata sources like Sonarr, TMDB, and OpenAI.

---

## 📁 File Structure

```
shownotes/
├── app/
│   ├── __init__.py            # Flask app factory
│   ├── routes.py              # All route definitions
│   ├── utils.py               # Helper functions
│   ├── prompts.py             # Prompt templates for OpenAI queries
│   ├── templates/             # Jinja2 HTML templates
│   └── static/                # CSS, JS, images
├── logs/                      # Parsed receipt logs and app logs
├── admin/                     # Admin tools, stats, API cost views
├── db.sqlite3                 # SQLite3 database
├── run.py                     # Main Flask launcher
├── shownotes.service          # systemd service unit file
├── requirements.txt           # Python dependencies
└── README.md
```

---

## 📦 Install Requirements

From the root project directory:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Make sure you have `sqlite3` and `systemd` installed (most systems already do).

---

## 🚀 How to Run Locally

### Run with Flask

```bash
source venv/bin/activate
flask run
```

Access via:
http://localhost:5000 or `http://<raspberrypi-ip>:5000`

---

### Run with `systemd` on Raspberry Pi

1. **Edit and install the service:**

```bash
sudo cp shownotes.service /etc/systemd/system/
sudo systemctl daemon-reexec
sudo systemctl enable shownotes
sudo systemctl start shownotes
```

2. **View logs:**

```bash
journalctl -u shownotes -e
```

---

## 🧠 Developer Notes

- You can edit prompts and summary structure in `app/prompts.py`
- Modular logic for summaries, relationship formatting, and OpenAI calls lives in `utils.py`
- Character and show summaries can be cached in the database to reduce API calls
- Admin tools available at `/admin` (WIP)
- `shownotes.service` restarts the app automatically if it crashes

---

## 💬 Prompt Templates (app/prompts.py)

Templates are structured like:

```python
SUMMARY_PROMPT_TEMPLATE = """
Provide a character summary for {character} from {show}, up to Season {season}, Episode {episode}.
Include:
- A short character bio
- A quote that captures their personality
- A section titled “Significant Relationships” formatted as a bulleted list. Each bullet should name the person, identify their role, and include a short description.
"""
```

Prompts can be easily adjusted to include other attributes like motivations, key arcs, or symbolic moments.

---

## 💸 OpenAI API Usage & Cost Tracking

- All API calls to OpenAI are tracked in the SQLite database.
- Table: `api_usage`
  - `id`
  - `timestamp`
  - `endpoint` (e.g., `gpt-4`)
  - `prompt_tokens`
  - `completion_tokens`
  - `total_tokens`
  - `cost_usd`
- A dashboard is under development at `/admin/usage` to view and export cost breakdowns.
- Use `utils.log_openai_usage()` to log calls programmatically.

> To keep costs low, batch prompts when possible and cache results for repeated queries.

---

## 📋 To Do / Wishlist

- [ ] Auto-refresh calendar with Sonarr API
- [ ] TMDB or Trakt.tv integration for richer metadata
- [ ] Plex webhook support to adjust spoiler level automatically
- [ ] UI: dark mode toggle, mobile chat enhancements
- [ ] User authentication & personal watch history

---

## 👨‍💻 Maintainer

**Scott Woods-Fehr**
📁 GitHub: [scottwf](https://github.com/scottwf)

---

## ✅ Quick Start (TL;DR)

```bash
git clone https://github.com/YOUR-REPO/shownotes.git
cd shownotes
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
flask run
```

---