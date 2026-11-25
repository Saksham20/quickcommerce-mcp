"""MCP tools for Blinkit, Zepto, Instamart, and BigBasket."""

from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from quickcommerce_mcp.browser import browser
from quickcommerce_mcp.models import CompareResult, SiteCatalog, SiteInfo, SiteResult
from quickcommerce_mcp.sites import SITES

SiteId = Literal["blinkit", "zepto", "instamart", "bigbasket"]

mcp = MCPServer(
    "quickcommerce",
    instructions=(
        "Use these tools to search Blinkit, Zepto, Swiggy Instamart, and BigBasket, "
        "compare prices, and add items to the website cart. Never ask the user for a "
        "password, OTP, or phone number, and never type those into a page. If a tool "
        "returns needs_login or needs_location, call open_for_login and tell the user "
        "to finish in the visible browser window. Stop at the cart. The user pays in "
        "the phone app for the same account."
    ),
)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
def list_sites() -> SiteCatalog:
    """List the stores this server can search and add to cart."""
    return SiteCatalog(
        sites=[SiteInfo(id=site.id, name=site.name, home=site.home) for site in SITES.values()],
        login=(
            "Sign in yourself in the browser window opened by open_for_login. "
            "The session is stored only in the local browser profile, outside this repo. "
            "The phone app shows the cart when it is logged into that same account."
        ),
    )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
async def open_for_login(
    site: Annotated[SiteId, Field(description="Which store to open.")],
) -> SiteResult:
    """Open a store in the visible browser so the user can set the address and sign in.

    Do not ask for, accept, or type a password, phone number, or OTP. Leave the
    window open and tell the user to finish on the desktop.
    """
    return await browser.open_home(site)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
async def search_products(
    site: Annotated[SiteId, Field(description="Which store to search.")],
    query: Annotated[str, Field(description="Product name, such as 'toned milk' or 'banana'.", min_length=1)],
    limit: Annotated[int, Field(ge=1, le=15, description="Maximum cards to return.")] = 8,
) -> SiteResult:
    """Search one store and return the product names and prices shown on the page."""
    return await browser.search(site, query, limit)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
async def compare_products(
    query: Annotated[str, Field(description="Product to look up on every store.", min_length=1)],
    limit_per_site: Annotated[int, Field(ge=1, le=10, description="Maximum cards from each store.")] = 5,
) -> CompareResult:
    """Search Blinkit, Zepto, Instamart, and BigBasket and return each store's prices."""
    return CompareResult(query=query, sites=await browser.search_all(query, limit_per_site))


@mcp.tool(
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)
)
async def add_to_cart(
    site: Annotated[SiteId, Field(description="Which store's cart to update.")],
    query: Annotated[str, Field(description="Search that should reveal the product.", min_length=1)],
    product_name: Annotated[
        str,
        Field(description="Name, or a distinctive part of the name, of the card to add.", min_length=1),
    ],
) -> SiteResult:
    """Add one matching product to the website cart.

    This does not place the order and does not open a payment page. The user
    reviews the cart and pays in the phone app.
    """
    return await browser.add_to_cart(site, query, product_name)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
async def view_cart(
    site: Annotated[SiteId, Field(description="Which store's cart to read.")],
) -> SiteResult:
    """Open a store cart and return the product cards visible there.

    Payment stays with the user, in the phone app, on the same account.
    """
    return await browser.view_cart(site)


def main() -> None:
    mcp.run()
