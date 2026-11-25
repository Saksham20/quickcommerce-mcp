"""Store catalog. Search URLs are the public website search pages."""

from dataclasses import dataclass
from urllib.parse import quote_plus


@dataclass(frozen=True)
class Site:
    id: str
    name: str
    home: str
    search: str
    cart: str | None = None


SITES: dict[str, Site] = {
    "blinkit": Site(
        "blinkit",
        "Blinkit",
        "https://blinkit.com/",
        "https://blinkit.com/s/?q={query}",
    ),
    "zepto": Site(
        "zepto",
        "Zepto",
        "https://www.zepto.com/",
        "https://www.zepto.com/search?query={query}",
    ),
    "instamart": Site(
        "instamart",
        "Swiggy Instamart",
        "https://www.swiggy.com/instamart",
        "https://www.swiggy.com/instamart/search?query={query}",
    ),
    "bigbasket": Site(
        "bigbasket",
        "BigBasket",
        "https://www.bigbasket.com/",
        "https://www.bigbasket.com/ps/?q={query}",
        "https://www.bigbasket.com/basket/",
    ),
}


def get_site(site_id: str) -> Site:
    key = site_id.strip().lower()
    try:
        return SITES[key]
    except KeyError as exc:
        known = ", ".join(SITES)
        raise ValueError(f"Unknown site {site_id!r}. Use one of: {known}.") from exc


def search_url(site: Site, query: str) -> str:
    return site.search.format(query=quote_plus(query.strip()))
