import asyncio

from mcp import Client

from quickcommerce_mcp.extract import classify, parse_card
from quickcommerce_mcp.server import mcp
from quickcommerce_mcp.sites import get_site, search_url


def test_search_urls_encode_spaces() -> None:
    blinkit = get_site("Blinkit")
    assert search_url(blinkit, "toned milk") == "https://blinkit.com/s/?q=toned+milk"
    assert search_url(get_site("bigbasket"), "atta 5kg").startswith("https://www.bigbasket.com/ps/?q=")


def test_parse_card_reads_name_price_and_pack() -> None:
    text = "Amul Taaza Toned Milk\n500 ml\n₹28\n₹32\nADD"
    product = parse_card(text, "https://blinkit.com/prn/amul/prid/1")
    assert product is not None
    assert product.name == "Amul Taaza Toned Milk"
    assert product.price == "₹28"
    assert product.mrp == "₹32"
    assert product.pack == "500 ml"


def test_login_wall_wins_when_no_products_are_visible() -> None:
    status = classify(
        "https://blinkit.com/",
        "Enter mobile number\nContinue with phone",
        [],
    )
    assert status == "needs_login"


def test_location_wall_is_reported_separately() -> None:
    status = classify("https://www.zepto.com/", "Select your location to see products", [])
    assert status == "needs_location"


def test_visible_products_mean_the_page_is_usable() -> None:
    product = parse_card("Banana\n₹40\nADD")
    assert product is not None
    assert classify("https://blinkit.com/", "Login is in the header\nBanana ₹40", [product]) == "ok"


def test_list_sites_does_not_open_a_browser() -> None:
    async def run() -> set[str]:
        async with Client(mcp) as client:
            result = await client.call_tool("list_sites", {})
            text = result.content[0].text
            return {name for name in ("blinkit", "zepto", "instamart", "bigbasket") if name in text}

    assert asyncio.run(run()) == {"blinkit", "zepto", "instamart", "bigbasket"}
