def build_character_prompt(character, show, season=None, episode=None, options=None):
    """
    options: {
        'include_relationships': True,
        'include_motivations': True,
        'include_themes': False,
        'include_quote': True,
        'tone': 'tv_expert' or 'in_character'
    }
    """
    if options is None:
        options = {}

    limit_text = f" Limit the analysis to events up to Season {season}, Episode {episode}." if season and episode else ""

    base = f"Provide a character summary for {character} from {show}.{limit_text}"

    if options.get("tone") == "in_character":
        base = (
            f"You are {character} from {show}. Reflect on your experiences"
            f"{limit_text} in a first-person tone, staying in character."
        )
    else:
        base += "\n\nKeep the writing professional and thoughtful, like an expert TV commentary."

    extras = []

    if options.get("include_relationships"):
        extras.append("""
Include a section titled “Significant Relationships” as a bulleted list with:
- Person's name
- Their role (e.g. mentor, rival)
- A 1–2 sentence explanation of the emotional or symbolic importance""")

    if options.get("include_motivations"):
        extras.append("Include a paragraph explaining the character’s primary motivations and inner conflicts.")

    if options.get("include_themes"):
        extras.append("Explain what themes or symbols the character embodies in the story.")

    if options.get("include_quote"):
        extras.append("Conclude with a quote the character has said that best illustrates who they are.")

    return base + "\n\n" + "\n\n".join(extras)