def parse_price(text):
    """Turn a price as shown on the site ("$5.99", "$1,200.50") into a float."""
    s = text.strip().lstrip("$")
    return float(s.replace(",", "."))
