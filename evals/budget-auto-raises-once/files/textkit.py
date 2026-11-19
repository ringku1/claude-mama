def normalize(text):
    """Collapse runs of whitespace to single spaces and trim the ends."""
    return " ".join(text.split())
