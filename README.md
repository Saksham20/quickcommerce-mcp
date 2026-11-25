# quickcommerce-mcp

MCP server for [Blinkit](https://blinkit.com/), [Zepto](https://www.zepto.com/), [Swiggy Instamart](https://www.swiggy.com/instamart), and [BigBasket](https://www.bigbasket.com/). An agent can search, compare prices, and add an item to the website cart. You pay yourself in the phone app.

The server drives a real Chromium window with [Playwright](https://playwright.dev/python/). It does not call private app APIs, and it does not type a password, phone number, or OTP.

## Sign in

1. Start the server where a desktop is visible. On the Hostinger VM that is the Remote Desktop session, with `DISPLAY=:10.0`.
2. Ask the agent to call `open_for_login` for a store.
3. In that browser window, set the delivery location and sign in with the same phone number you use in the app. The OTP stays in the window. Do not paste it into chat.
4. The cookies live in `~/.quickcommerce-mcp/profile` (or `QUICKCOMMERCE_PROFILE`). That directory is outside this repo.

A cart created while that account is signed in is the cart the phone app shows. A cart created before sign-in stays in the browser only. `add_to_cart` stops after the click. It never opens payment.

If a tool returns `needs_login` or `needs_location`, finish that step in the open window and run the tool again.

## Tools

| Tool | What it does |
| --- | --- |
| `list_sites` | Names the four stores. |
| `open_for_login` | Opens a store and leaves the window for you. |
| `search_products` | Reads product cards from one store. |
| `compare_products` | Runs the same search on all four. |
| `add_to_cart` | Clicks Add on a matching card. |
| `view_cart` | Reads the cart that is open in the browser. |

Store ids are `blinkit`, `zepto`, `instamart`, and `bigbasket`.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m playwright install chromium
quickcommerce-mcp
```

On a server without a display, install the system libraries too: `python -m playwright install --with-deps chromium`. Set `QUICKCOMMERCE_HEADLESS=1` only when nobody needs to see the window. Sign-in needs the window.

Cursor can launch it with [`examples/cursor-mcp.json`](examples/cursor-mcp.json). Point `command` at the virtualenv's `quickcommerce-mcp` if it is not on `PATH`.

## Tests

```bash
pytest
```

The tests cover product parsing, login and location detection, and the `list_sites` tool. They do not open the stores.
