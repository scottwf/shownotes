cd ~/venn-cast

mkdir -p templates

# Create index.html
cat <<EOF > templates/index.html
{% extends "base.html" %}
{% block title %}Search Actors{% endblock %}
{% block content %}
    <form method="post" action="/actor-search">
        <label for="actor_name">Enter Actor Name:</label>
        <input type="text" id="actor_name" name="actor_name" required>
        <button type="submit">Search</button>
    </form>
{% endblock %}
EOF

# Create base.html
cat <<EOF > templates/base.html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{% block title %}Venn-Cast{% endblock %}</title>
</head>
<body>
    <header>
        <h1><a href="/">Venn-Cast</a></h1>
    </header>
    <main>
        {% block content %}{% endblock %}
    </main>
</body>
</html>
EOF

# Create actor_results.html
cat <<EOF > templates/actor_results.html
{% extends "base.html" %}
{% block title %}Search Results{% endblock %}
{% block content %}
    <h2>Search Results</h2>
    <p>You searched for: <strong>{{ actor }}</strong></p>
    <a href="/">Search Again</a>
{% endblock %}
EOF