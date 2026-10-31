"""Helpers that read the storefront's server-rendered HTML (no browser, no JavaScript).

Everything here is a pure function of the page text so it can be tested with saved fixtures. The markers are
the exact strings the frontend templates render (see apps/frontend/templates); a response that lacks them is a
failure of the journey, not just a slow request.
"""

from __future__ import annotations

import html
import re
from urllib.parse import quote, urlsplit

# ---- markers (frontend templates) ----
BRAND = "Everly"
ORDER_COMPLETE = "Your order is complete"
CART_EMPTY = "Your shopping cart is empty"
WRONG_CREDENTIALS = "Wrong email or password"
NOTHING_FOUND = "Nothing found"
REVIEW_POSTED = "your review has been posted"
ORDERS_TITLE = "Your orders"
EMAILS_TITLE = "Your emails"
ERROR_TITLE = "We could not process that"

_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
_LEAKS = re.compile(r"rpc error|goroutine \d|\.go:\d+|traceback \(most recent|bcrypt|\$2[aby]\$", re.IGNORECASE)


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def contains(page: str, marker: str) -> bool:
    """Case-insensitive substring test (the templates change capitalisation more often than wording)."""
    return marker.lower() in page.lower()


def leaks_internals(page: str) -> bool:
    """True when the page shows what an error page must hide: gRPC errors, Go stack traces, password hashes."""
    return bool(_LEAKS.search(page))


def card_product_ids(page: str) -> list[str]:
    """Product ids of the cards on a catalog page or in a recommendations block, in page order, unique."""
    ids = re.findall(r'class="product-card-link"\s+href="[^"]*/product/([^"/?#]+)"', page)
    return _unique([html.unescape(i) for i in ids])


def recommended_ids(page: str) -> list[str]:
    """Product ids inside the "You may also like" block of a product page (empty when it is not rendered)."""
    start = page.find('class="reco-grid"')
    if start < 0:
        return []
    end = page.find("</ul>", start)
    return card_product_ids(page[start : end if end > 0 else len(page)])


def departments(page: str) -> list[str]:
    """Department ids linked from the navigation (href="/?category=women")."""
    return _unique(re.findall(r'href="[^"]*/\?category=([a-z0-9-]+)"', page))


def next_page_path(page: str) -> str | None:
    """Path of the pager's rel="next" link, or None on the last page."""
    m = re.search(r'<a\b[^>]*\brel="next"[^>]*>', page)
    if not m:
        return None
    href = re.search(r'\bhref="([^"]+)"', m.group(0))
    return html.unescape(href.group(1)) if href else None


def page_paths(page: str) -> list[str]:
    """Paths of all numbered pager links (/?page=2, /?category=x&page=3), unique, in page order."""
    links = re.findall(r'<a\b[^>]*class="page-link"[^>]*href="([^"]+)"', page)
    return _unique([html.unescape(link) for link in links])


def tags(page: str) -> list[str]:
    """Tag texts of a product page; each is a working search term (/?q=<tag>)."""
    found = re.findall(r'<a class="tag" href="[^"]*/\?q=[^"]*">([^<]+)</a>', page)
    return _unique([html.unescape(t).strip() for t in found])


def stock_state(page: str) -> str | None:
    """'in', 'low' or 'out' from the product page's stock line, None if the line is missing."""
    m = re.search(r'class="stock-status is-(in|low|out)"', page)
    return m.group(1) if m else None


def has_add_to_cart_form(page: str, product_id: str) -> bool:
    return f'name="product_id" value="{product_id}"' in page


def idempotency_key(page: str) -> str | None:
    """The hidden key the cart page puts into the checkout form (one per rendering of the cart)."""
    m = re.search(r'name="idempotency_key"\s+value="([^"]+)"', page)
    return html.unescape(m.group(1)) if m else None


def cart_lists(page: str, product_id: str) -> bool:
    return f"/product/{product_id}" in page and not contains(page, CART_EMPTY)


def order_id(page: str) -> str | None:
    """The order id from the confirmation page (the 'Confirmation #' row)."""
    m = re.search(rf"Confirmation #</dt>\s*<dd[^>]*>\s*({_UUID})", page)
    return m.group(1).lower() if m else None


def tracking_number(page: str) -> str | None:
    m = re.search(r"\b[A-Z]{2}-\d+-\d+\b", page)
    return m.group(0) if m else None


def order_ids(page: str) -> list[str]:
    """Order ids linked from the order history page, newest first as rendered."""
    return _unique([i.lower() for i in re.findall(rf'href="[^"]*/orders/({_UUID})"', page)])


def mail_paths(page: str) -> list[str]:
    """Paths of the mails in the mailbox list (/emails/<id>?order=<order>), unique."""
    links = re.findall(r'href="([^"]*/emails/[^"?]+\?order=[^"]+)"', page)
    return _unique([html.unescape(link) for link in links])


def mail_for_order(page: str, order: str) -> str | None:
    """Path of the mail that belongs to `order`, None while it has not arrived."""
    for path in mail_paths(page):
        if f"order={order}" in path:
            return path
    return None


def mail_is_sandboxed(page: str) -> bool:
    """A mail is shown in an <iframe sandbox>; plain markup would let mail HTML run in the shop's origin."""
    return "<iframe" in page and "sandbox" in page


def error_message(page: str) -> str:
    """Title and message of the shop's error page ('' when the page is not an error page)."""
    m = re.search(r'class="container error-page".*?<h1>(.*?)</h1>\s*<p>(.*?)</p>', page, re.DOTALL)
    if not m:
        return ""
    return html.unescape(f"{m.group(1).strip()}: {m.group(2).strip()}")


def same_origin_path(host: str, href: str) -> str | None:
    """Return href as a path (+ query) if it points to `host` or is relative, None for any other site.

    The generator only ever requests what this returns, so it can not wander off to other hosts.
    """
    parts = urlsplit(href)
    base = urlsplit(host)
    if parts.scheme or parts.netloc:
        if (parts.scheme, parts.netloc) != (base.scheme, base.netloc):
            return None
    if parts.path and not parts.path.startswith("/"):
        return None
    path = parts.path or "/"
    return path + (f"?{parts.query}" if parts.query else "")


def search_path(term: str) -> str:
    return f"/?q={quote(term)}"
