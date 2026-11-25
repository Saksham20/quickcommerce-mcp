"""Turn visible page text into products and a session status.

These functions stay free of Playwright so they can be tested without a browser.
"""

import re

from quickcommerce_mcp.models import Product, Status

RUPEE = re.compile(r"₹\s*[\d,]+(?:\.\d{1,2})?")
PACK = re.compile(
    r"\b\d+(?:\.\d+)?\s?(?:kg|g|ml|l|ltr|litre|liter|pcs|pc|pack|packs)\b",
    re.IGNORECASE,
)
SKIP_NAME = re.compile(
    r"^(add|notify me|out of stock|\d+%?\s*off|off|new|ad|sponsored)$",
    re.IGNORECASE,
)

LOGIN_PHRASES = (
    "enter your mobile",
    "enter mobile number",
    "enter phone number",
    "verify otp",
    "otp sent",
    "login to continue",
    "log in to continue",
    "sign in to continue",
    "continue with phone",
)
LOCATION_PHRASES = (
    "select delivery location",
    "select your location",
    "select location",
    "search for your location",
    "search delivery location",
    "use current location",
    "use my current location",
    "where should we deliver",
    "choose delivery location",
    "set delivery location",
    "enter your area",
    "delivery location",
)
BLOCKED_PHRASES = (
    "you have been blocked",
    "access denied",
    "request blocked",
    "the request could not be satisfied",
    "sorry, you have been blocked",
)
OUTAGE_PHRASES = (
    "we'll be back shortly",
    "we are fixing a temporary glitch",
)


def parse_card(text: str, href: str | None = None) -> Product | None:
    """Build a product from one card's visible text."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    prices = RUPEE.findall(text)
    if not prices or not lines:
        return None
    name = next(
        (
            line
            for line in lines
            if "₹" not in line and not SKIP_NAME.match(line) and len(line) > 2
        ),
        None,
    )
    if name is None:
        return None
    pack = next((PACK.search(line).group(0) for line in lines if PACK.search(line)), None)
    return Product(
        name=name[:160],
        price=_clean_price(prices[0]),
        mrp=_clean_price(prices[1]) if len(prices) > 1 else None,
        pack=pack,
        url=href,
    )


def classify(url: str, body_text: str, products: list[Product]) -> Status:
    """Decide whether the page is usable, or waiting on the person at the desktop."""
    if products:
        return "ok"
    sample = body_text.lower()[:6000]
    location = url.lower()
    if any(phrase in sample for phrase in BLOCKED_PHRASES):
        return "blocked"
    if any(phrase in sample for phrase in OUTAGE_PHRASES):
        return "error"
    if any(phrase in sample for phrase in LOGIN_PHRASES) or any(
        part in location for part in ("/login", "/auth", "/signin")
    ):
        return "needs_login"
    if any(phrase in sample for phrase in LOCATION_PHRASES):
        return "needs_location"
    return "not_found"


def status_message(status: Status, site_name: str) -> str:
    if status == "ok":
        return f"{site_name} returned products."
    if status == "needs_login":
        return (
            f"{site_name} is waiting for you to sign in. The browser window is open on the "
            "desktop. Enter the phone number and OTP there yourself. Do not paste them into "
            "chat. This server never stores them. After you finish, run the tool again. The "
            "phone app only sees this cart when that same account is signed in."
        )
    if status == "needs_location":
        return (
            f"{site_name} needs a delivery location. Set it in the open browser window, then "
            "run the tool again. Sign in there too if the page asks, using the same phone "
            "number as the app. Do not paste the OTP into chat."
        )
    if status == "blocked":
        return (
            f"{site_name} refused this connection before a page opened. The block is on "
            "the server address, so signing in from this window does not remove it."
        )
    if status == "not_found":
        return f"{site_name} did not show any product cards for this search."
    return f"{site_name} showed an error page instead of products."


def _clean_price(raw: str) -> str:
    return re.sub(r"\s+", "", raw)
