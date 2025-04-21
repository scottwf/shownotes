import requests
from flask import Flask, render_template_string
from datetime import datetime, timedelta

SONARR_URL = "http://192.168.1.100:8989/api/v3/calendar"
API_KEY = "your_api_key_here"

# Query next 7 days of the calendar
start_date = datetime.now()
end_date = start_date + timedelta(days=7)

params = {
    'start': start_date.isoformat(),
    'end': end_date.isoformat()
}

headers = {
    'X-Api-Key': API_KEY
}

app = Flask(__name__)

@app.route('/')
def show_calendar():
    try:
        response = requests.get(SONARR_URL, params=params, headers=headers)
        response.raise_for_status()
        calendar = response.json()
    except Exception as e:
        return f"<h1>Error fetching calendar: {e}</h1>"

    html = '''
    <h1>Upcoming Shows (Next 7 Days)</h1>
    <ul>
    {% for show in calendar %}
        <li>
            <strong>{{ show['series']['title'] }}</strong> — 
            Season {{ show['seasonNumber'] }}, Episode {{ show['episodeNumber'] }}: 
            "{{ show['title'] }}" airing on {{ show['airDate'] }}
        </li>
    {% endfor %}
    </ul>
    '''
    return render_template_string(html, calendar=calendar)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005)
