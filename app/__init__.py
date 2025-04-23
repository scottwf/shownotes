# Dependencies for deployment:
# - Flask
# - Python standard libraries: os, urllib.parse
# - Optional packages: Jinja2 (comes with Flask)

import os
from flask import Flask

# Dependencies:
# - Flask
# - urllib.parse (standard library)

def create_app():
    base_dir = os.path.abspath(os.path.dirname(__file__))
    templates_path = os.path.join(base_dir, "..", "templates")
    static_path = os.path.join(base_dir, "..", "static")

    app = Flask(__name__, template_folder=templates_path, static_folder=static_path)

    from datetime import datetime
    from zoneinfo import ZoneInfo

    @app.template_filter('datetimeformat')
    def datetimeformat(value, format="%Y-%m-%d %I:%M %p"):
        try:
            dt = datetime.fromisoformat(value).replace(tzinfo=ZoneInfo("UTC"))
            return dt.astimezone(ZoneInfo("America/Regina")).strftime(format)
        except Exception:
            return value

    from .routes import main
    app.register_blueprint(main)

    import urllib.parse

    def quote_plus_filter(s):
        return urllib.parse.quote_plus(str(s))

    app.jinja_env.filters['quote_plus'] = quote_plus_filter

    return app