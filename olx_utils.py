import re
from decimal import Decimal, InvalidOperation
from typing import Optional
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit


def parse_price(price_str: str) -> Optional[tuple[float, str]]:
    """Parsează un preț în RON sau EUR și ignoră intervalele și alte monede."""
    currency_match = re.search(
        r"(?<!\w)(lei|ron|eur|euro|euros)(?!\w)|€",
        price_str,
        re.IGNORECASE,
    )
    if currency_match is None:
        return None

    currency = (
        "EUR"
        if currency_match.group(0) == "€"
        or currency_match.group(1).lower() in {"eur", "euro", "euros"}
        else "RON"
    )
    amounts = re.findall(r"\d[\d\s\u00a0.,]*\d|\d", price_str)
    if len(amounts) != 1:
        return None

    value = amounts[0].replace(" ", "").replace("\u00a0", "")
    if "." in value and "," in value:
        decimal_separator = "." if value.rfind(".") > value.rfind(",") else ","
        thousands_separator = "," if decimal_separator == "." else "."
        value = value.replace(thousands_separator, "")
        value = value.replace(decimal_separator, ".")
    elif "." in value or "," in value:
        separator = "." if "." in value else ","
        groups = value.split(separator)
        if len(groups) > 1 and all(len(group) == 3 for group in groups[1:]):
            value = "".join(groups)
        elif len(groups) == 2:
            value = f"{groups[0]}.{groups[1]}"
        else:
            return None

    try:
        price = Decimal(value)
    except InvalidOperation:
        return None
    if not price.is_finite() or price < 0:
        return None
    return float(price), currency


def get_search_url(search_term: str) -> str:
    return f"https://www.olx.ro/oferte/q-{quote(search_term.strip(), safe='')}/"


def get_listing_url(href: str) -> Optional[str]:
    parsed = urlsplit(urljoin("https://www.olx.ro/", href))
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not (
        host == "olx.ro" or host.endswith(".olx.ro")
    ):
        return None
    return urlunsplit(("https", parsed.netloc, parsed.path, "", ""))


def get_ad_id(link: str) -> str:
    last_segment = unquote(urlsplit(link).path.rstrip("/").rsplit("/", 1)[-1])
    if last_segment.endswith(".html"):
        last_segment = last_segment[:-5]
    return last_segment
