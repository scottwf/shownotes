# ShowNotes – To Do List

## 🔧 Backend & Functionality
- [ ] Fix create_app() crashes and ensure all routes and utilities are properly imported
- [ ] Add TMDB autocomplete for show and character search inputs
- [ ] Enable Plex webhook integration to track watched episodes and adjust spoiler levels
- [ ] Integrate Sonarr calendar with episode hover previews and filters (e.g., premieres, finales)
- [ ] Build OpenAI prompt enrichment system (title, description, quantity, mass, etc.)
- [ ] Track and display OpenAI API usage (by date, endpoint, token count, cost)

## 🖥️ Admin Tools
- [ ] Add an admin dashboard with:
  - [ ] Recent OpenAI queries
  - [ ] API usage summary
  - [ ] JSON route links for Shortcuts
  - [ ] Logs of uploaded or parsed data

## 🧠 Prompt & Summary Features
- [ ] Finalize reusable prompt templates (summary, relationships, arcs, quotes)
- [ ] Add prompt-based regeneration with spoiler limits (e.g., “up to Season 2”)
- [ ] Enable structured caching of OpenAI results (by character, episode, etc.)
- [ ] Add ability to regenerate summaries with new context or version tags

## 🌐 UI & Display
- [ ] Display poster/banner in “Currently Watching” section
- [ ] Fix duplicate characters showing in the main character list
- [ ] Show calendar with upcoming Sonarr episodes
- [ ] Add modals for character previews when clicked from list
- [ ] Show red/green calendar days based on usage vs. generation (SolarScope-style)
- [ ] Add dark mode toggle

## 📦 Data Structure & Sync

## 🔐 Authentication & Personalization
- [ ] Add simple authentication system (e.g., Plex user + shared password)
- [ ] Track personal watch history per user
- [ ] Let users set their own spoiler limit thresholds

## 📱 Mobile & Chat Interface
- [ ] Use chat UI libraries to create a messenger-style interface
- [ ] Add character chat mode: “Chat with [Character]” using limited context
- [ ] Add chat UI for general Q&A about a show, character, or episode
