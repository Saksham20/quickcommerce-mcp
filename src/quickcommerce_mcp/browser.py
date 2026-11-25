"""One persistent Chromium profile shared by every tool call.

The profile lives outside the repository. Signing in happens in that window.
Passwords and OTPs are never typed by this process and never written to disk
by this package.
"""

import asyncio
import logging
import os
from pathlib import Path

from playwright.async_api import BrowserContext, Page, Playwright, TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright

from quickcommerce_mcp.extract import classify, parse_card, status_message
from quickcommerce_mcp.models import Product, SiteResult, Status
from quickcommerce_mcp.sites import Site, get_site, search_url

log = logging.getLogger(__name__)

_READ_CARDS = """
() => {
  const price = /₹\\s*[\\d,]+/;
  const nodes = [...document.querySelectorAll("div, li, article")];
  const cards = [];
  for (const el of nodes) {
    const text = (el.innerText || "").trim();
    if (text.length < 12 || text.length > 320) continue;
    if (!price.test(text)) continue;
    const prices = text.match(/₹\\s*[\\d,]+(?:\\.\\d{1,2})?/g) || [];
    if (prices.length < 1 || prices.length > 3) continue;
    const lines = text.split("\\n").map((line) => line.trim()).filter(Boolean);
    if (lines.length < 2 || lines.length > 14) continue;
    const link = el.querySelector("a[href]");
    cards.push({ text, href: link ? link.href : null, length: text.length });
  }
  cards.sort((a, b) => a.length - b.length);
  const kept = [];
  const seen = new Set();
  for (const card of cards) {
    const key = card.text.split("\\n").map((line) => line.trim()).filter(Boolean)[0].toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    kept.push({ text: card.text, href: card.href });
    if (kept.length >= 24) break;
  }
  return kept;
}
"""

_CLICK_ADD = """
(name) => {
  const needle = name.toLowerCase().replace(/\\s+/g, " ").trim();
  const nodes = [...document.querySelectorAll("div, li, article")];
  const matches = nodes
    .filter((el) => {
      const text = (el.innerText || "").toLowerCase().replace(/\\s+/g, " ");
      return text.includes(needle) && text.length < 500 && text.includes("₹");
    })
    .sort((a, b) => a.innerText.length - b.innerText.length);
  const card = matches[0];
  if (!card) return { ok: false, reason: "That product is not on the page." };
  const buttons = [...card.querySelectorAll("button, [role='button']")];
  const add = buttons.find((button) => {
    const label = `${button.innerText || ""} ${button.getAttribute("aria-label") || ""}`
      .trim()
      .toLowerCase();
    return label === "add" || label === "+" || label.startsWith("add ");
  });
  if (!add) return { ok: false, reason: "No Add button was found on that product." };
  add.click();
  return { ok: true, reason: "Clicked Add." };
}
"""

_CLICK_CART = """
() => {
  const nodes = [...document.querySelectorAll("a, button, [role='button']")];
  const cart = nodes.find((node) => {
    const label = `${node.innerText || ""} ${node.getAttribute("aria-label") || ""} ${node.getAttribute("href") || ""}`.toLowerCase();
    return label.includes("cart") || label.includes("basket");
  });
  if (!cart) return false;
  cart.click();
  return true;
}
"""


def profile_dir() -> Path:
    configured = os.environ.get("QUICKCOMMERCE_PROFILE")
    path = Path(configured).expanduser() if configured else Path.home() / ".quickcommerce-mcp" / "profile"
    path.mkdir(parents=True, exist_ok=True)
    return path


def headless() -> bool:
    flag = os.environ.get("QUICKCOMMERCE_HEADLESS")
    if flag is not None:
        return flag.strip() == "1"
    return not os.environ.get("DISPLAY")


class Browser:
    """Owns the Playwright process and one page per site."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._pages: dict[str, Page] = {}

    async def close(self) -> None:
        async with self._lock:
            if self._context is not None:
                await self._context.close()
                self._context = None
            if self._playwright is not None:
                await self._playwright.stop()
                self._playwright = None
            self._pages.clear()

    async def open_home(self, site_id: str) -> SiteResult:
        site = get_site(site_id)
        async with self._lock:
            page = await self._page(site.id)
            await self._goto(page, site.home)
            return await self._result(site, page, products=[])

    async def search(self, site_id: str, query: str, limit: int) -> SiteResult:
        site = get_site(site_id)
        async with self._lock:
            return await self._search(site, query, limit)

    async def search_all(self, query: str, limit: int) -> list[SiteResult]:
        from quickcommerce_mcp.sites import SITES

        async with self._lock:
            results: list[SiteResult] = []
            for site in SITES.values():
                try:
                    results.append(await self._search(site, query, limit))
                except Exception as exc:
                    log.exception("Search failed for %s", site.id)
                    results.append(
                        SiteResult(
                            site=site.id,
                            site_name=site.name,
                            status="error",
                            message=f"{site.name} failed: {exc}",
                        )
                    )
            return results

    async def add_to_cart(self, site_id: str, query: str, product_name: str) -> SiteResult:
        site = get_site(site_id)
        async with self._lock:
            found = await self._search(site, query, limit=12)
            if found.status != "ok":
                return found
            page = await self._page(site.id)
            clicked = await page.evaluate(_CLICK_ADD, product_name)
            await page.wait_for_timeout(1500)
            body = await self._body(page)
            after = classify(page.url, body, [])
            if not clicked.get("ok"):
                return found.model_copy(
                    update={"status": "not_found", "message": str(clicked.get("reason"))}
                )
            if after == "needs_login":
                return found.model_copy(
                    update={
                        "status": "needs_login",
                        "message": status_message("needs_login", site.name),
                        "products": [],
                    }
                )
            match = _matching(found.products, product_name)
            name = match.name if match else product_name
            return found.model_copy(
                update={
                    "status": "ok",
                    "message": (
                        f"Clicked Add for {name} on {site.name}. Open the cart to confirm, "
                        "then complete payment in the phone app while that same account is "
                        "signed in. This server does not take payment."
                    ),
                    "products": [match] if match else found.products[:1],
                }
            )

    async def view_cart(self, site_id: str) -> SiteResult:
        site = get_site(site_id)
        async with self._lock:
            page = await self._page(site.id)
            if site.cart:
                await self._goto(page, site.cart)
            else:
                await self._goto(page, site.home)
                await page.evaluate(_CLICK_CART)
                await page.wait_for_timeout(1500)
            result = await self._result(site, page, products=await self._products(page, limit=20))
            if result.status == "ok":
                count = len(result.products)
                result = result.model_copy(
                    update={
                        "message": (
                            f"{site.name} cart shows {count} priced row{'s' if count != 1 else ''}. "
                            "Pay in the phone app on the same account."
                        )
                    }
                )
            return result

    async def _search(self, site: Site, query: str, limit: int) -> SiteResult:
        page = await self._page(site.id)
        await self._goto(page, search_url(site, query))
        products = await self._products(page, limit)
        return await self._result(site, page, products)

    async def _result(self, site: Site, page: Page, products: list[Product]) -> SiteResult:
        body = await self._body(page)
        status: Status = classify(page.url, body, products)
        visible = products if status == "ok" else []
        message = status_message(status, site.name)
        if status == "ok":
            message = f"{site.name} showed {len(visible)} product{'s' if len(visible) != 1 else ''}."
        return SiteResult(
            site=site.id,
            site_name=site.name,
            status=status,
            message=message,
            products=visible,
        )

    async def _products(self, page: Page, limit: int) -> list[Product]:
        raw = await page.evaluate(_READ_CARDS)
        products: list[Product] = []
        seen: set[str] = set()
        for card in raw:
            product = parse_card(str(card.get("text", "")), card.get("href"))
            if product is None:
                continue
            key = product.name.casefold()
            if key in seen:
                continue
            seen.add(key)
            products.append(product)
            if len(products) >= limit:
                break
        return products

    async def _page(self, site_id: str) -> Page:
        context = await self._ensure()
        page = self._pages.get(site_id)
        if page is None or page.is_closed():
            page = await context.new_page()
            self._pages[site_id] = page
        return page

    async def _ensure(self) -> BrowserContext:
        if self._context is not None:
            return self._context
        self._playwright = await async_playwright().start()
        show = not headless()
        log.info("Launching Chromium headless=%s profile=%s", not show, profile_dir())
        self._context = await self._playwright.chromium.launch_persistent_context(
            str(profile_dir()),
            headless=not show,
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            viewport={"width": 1280, "height": 800},
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        return self._context

    async def _goto(self, page: Page, url: str) -> None:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        except PlaywrightTimeout as exc:
            raise RuntimeError(f"Timed out opening {url}") from exc
        try:
            await page.wait_for_function(
                "() => (document.body?.innerText || '').includes('₹')",
                timeout=12_000,
            )
        except PlaywrightTimeout:
            await page.wait_for_timeout(1_500)

    async def _body(self, page: Page) -> str:
        try:
            return await page.inner_text("body", timeout=8_000)
        except PlaywrightTimeout:
            return ""


def _matching(products: list[Product], product_name: str) -> Product | None:
    needle = " ".join(product_name.casefold().split())
    for product in products:
        if needle in " ".join(product.name.casefold().split()):
            return product
    return None


browser = Browser()
