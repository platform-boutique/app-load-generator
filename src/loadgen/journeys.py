"""Locust user classes: the shop journeys, weighted tasks, hard caps, summary and exit code.

Loaded by file path (Locust does that), so imports are absolute: `loadgen` must be importable (PYTHONPATH=src).
Started by `python -m loadgen` (which turns the environment into Locust arguments) or by `locust -f` directly.
HTTP against the frontend only; the only host contacted is HOST.
"""

from __future__ import annotations

import logging
import os
import random
import secrets
from collections import Counter

from locust import HttpUser, between, events, tag, task

from loadgen import forms, page
from loadgen.budget import Budget
from loadgen.client import Reply, Visitor
from loadgen.config import Config

log = logging.getLogger("loadgen")

CONFIG = Config.from_env()
ORDERS = Budget(CONFIG.max_orders)
REVIEWS = Budget(CONFIG.max_reviews)
JOURNEYS: Counter[str] = Counter()
ORDERS_PLACED: list[str] = []  # order ids confirmed by the shop in this run

SEARCH_FALLBACK = ["shirt", "mug", "lamp", "bag", "shoe"]
REVIEW_TEXTS = [
    "Automated load test review, please ignore.",
    "Posted by the load generator to exercise the review path.",
    "Load test: this text is not a real opinion.",
]
MAIL_POLLS = 20  # the confirmation mail comes through Kafka: poll up to this many times, one second apart


def make_password(env=None) -> str:
    """Password of the demo accounts this process registers: LOADGEN_PASSWORD if set, else a random one.

    The shop wants 8 to 72 bytes. Every registration uses a fresh random e-mail and the accounts are only used by this
    process, so the password never has to survive a run.
    """
    env = os.environ if env is None else env
    return env.get("LOADGEN_PASSWORD") or secrets.token_urlsafe(16)


PASSWORD = make_password()


class ShopUser(HttpUser):
    """One simulated visitor with its own cookie jar (the HttpSession of this instance)."""

    abstract = True
    host = CONFIG.host
    wait_time = between(CONFIG.think_min, CONFIG.think_max)


class Shopper(ShopUser):
    def on_start(self) -> None:
        self.v = Visitor(self.client, CONFIG.host)
        self.catalog: list[str] = []
        self.depts: list[str] = []
        self.terms: list[str] = []
        self.account: tuple[str, str] | None = None  # (email, name) once registered
        self.wrong_password_checked = False
        self._open_home()

    # ---------------------------------------------------------------- shared steps

    def _open_home(self) -> Reply:
        r = self.v.get("/", "/", has=[page.BRAND])
        self._learn_catalog(r)
        self.depts = page.departments(r.text) or self.depts
        if r.ok and not page.card_product_ids(r.text):
            self._fail(r, "home page lists no products")
        return r

    def _fail(self, reply: Reply, why: str) -> None:
        """A check the helper functions cannot express: record it as a failed request of its own (no HTTP)."""
        self.environment.events.request.fire(
            request_type="CHECK",
            name=why,
            response_time=0,
            response_length=0,
            response=None,
            context={},
            exception=AssertionError(why),
        )
        reply.ok = False

    def _learn_catalog(self, reply: Reply) -> None:
        if reply.ok:
            for pid in page.card_product_ids(reply.text):
                if pid not in self.catalog:
                    self.catalog.append(pid)

    def _any_product(self) -> str | None:
        return random.choice(self.catalog) if self.catalog else None

    def _stocked_product(self) -> tuple[str, Reply] | None:
        """A product whose page says plainly 'In stock' (not 'Only N left', not sold out), to keep the last units."""
        for _ in range(4):
            if not self.catalog and not self._open_home().ok:
                return None
            pid = self._any_product()
            if pid is None or pid in CONFIG.sold_out_products:
                continue
            r = self.v.get(f"/product/{pid}", "/product/[id]", has=['name="product_id"'])
            if not r.ok:
                return None
            if page.stock_state(r.text) == "in":
                return pid, r
        return None

    def _add_to_cart(self, pid: str) -> bool:
        r = self.v.post("/cart", forms.add_to_cart_form(pid), "/cart (add)", status=(302, 303), location=["/cart"])
        return r.ok

    def _cart_with(self, pid: str) -> Reply | None:
        r = self.v.get("/cart", "/cart", has=["Shipping address"], lacks=[page.CART_EMPTY])
        if r.ok and not page.cart_lists(r.text, pid):
            self._fail(r, "cart page does not list the added product")
        if r.ok and not page.idempotency_key(r.text):
            self._fail(r, "cart page has no idempotency_key")
        return r if r.ok else None

    def _empty_cart(self) -> None:
        self.v.post("/cart/empty", {}, "/cart/empty", status=(302, 303), location=["/"])

    def _fill_cart(self) -> tuple[str, Reply] | None:
        picked = self._stocked_product()
        if picked is None:
            return None
        pid = picked[0]
        if not self._add_to_cart(pid):
            return None
        cart = self._cart_with(pid)
        return (pid, cart) if cart else None

    def _checkout(self, cart: Reply, card: str, name: str) -> Reply:
        key = page.idempotency_key(cart.text) or ""
        return self.v.post(
            "/cart/checkout", forms.checkout_form(key, card), name, status=200, has=[page.ORDER_COMPLETE]
        )

    def _place_order(self) -> str | None:
        """Add a product, check the cart, check out with the good card. Returns the order id, None on any failure
        or when the MAX_ORDERS budget is used up (then nothing is added to the cart either)."""
        if not ORDERS.take():
            return None
        confirmed = False
        try:
            filled = self._fill_cart()
            if filled is None:
                return None
            r = self._checkout(filled[1], forms.OK_CARD, "/cart/checkout (ok card)")
            oid = page.order_id(r.text) if r.ok else None
            if r.ok and not oid:
                self._fail(r, "order page has no confirmation id")
            if r.status in (200, 0) or r.status >= 500:
                confirmed = True  # the order may exist: keep the slot used
            if oid:
                ORDERS_PLACED.append(oid)
            return oid
        finally:
            if not confirmed:
                ORDERS.give_back()

    # ---------------------------------------------------------------- journeys (weighted)

    @task(10)
    @tag("browse")
    def browse(self) -> None:
        JOURNEYS["browse"] += 1
        home = self._open_home()
        if not home.ok:
            return
        # department
        if self.depts:
            dept = random.choice(self.depts)
            r = self.v.get(f"/?category={dept}", "/?category=[dept]", has=[page.BRAND])
            self._learn_catalog(r)
            if r.ok and not page.card_product_ids(r.text):
                self._fail(r, "department page lists no products")
        # search: a tag seen on product pages, mostly; sometimes a word that matches nothing
        if random.random() < 0.2:
            self.v.get(page.search_path(f"zzq{secrets.token_hex(3)}"), "/?q=[nothing]", has=[page.NOTHING_FOUND])
        else:
            term = random.choice(self.terms or SEARCH_FALLBACK)
            r = self.v.get(page.search_path(term), "/?q=[term]", has=[page.BRAND])
            self._learn_catalog(r)
        # sort and paging
        if random.random() < 0.5:
            sort = random.choice(["price_asc", "price_desc"])
            self.v.get(f"/?sort={sort}", "/?sort=[order]", has=[page.BRAND])
        nxt = page.next_page_path(home.text)
        path = page.same_origin_path(CONFIG.host, nxt) if nxt else None
        if path:
            r = self.v.get(path, "/?page=[n]", has=[page.BRAND])
            self._learn_catalog(r)
            if r.ok and not page.card_product_ids(r.text):
                self._fail(r, "page 2 lists no products")

    @task(8)
    @tag("product_view")
    def product_view(self) -> None:
        JOURNEYS["product_view"] += 1
        pid = self._any_product()
        if pid is None:
            self._open_home()
            return
        r = self.v.get(f"/product/{pid}", "/product/[id]", has=['name="product_id"', "Customer reviews"])
        if not r.ok:
            return
        for t in page.tags(r.text):
            if t not in self.terms:
                self.terms.append(t)
        recs = page.recommended_ids(r.text)
        if not recs:
            self._fail(r, "product page shows no recommendations")
            return
        # follow one recommendation like a visitor would
        self.v.get(f"/product/{random.choice(recs)}", "/product/[id] (from recommendation)", has=['name="product_id"'])

    @task(4)
    @tag("add_to_cart")
    def add_to_cart(self) -> None:
        JOURNEYS["add_to_cart"] += 1
        filled = self._fill_cart()
        if filled is not None:
            self._empty_cart()
            self.v.get("/cart", "/cart (after empty)", has=[page.CART_EMPTY])

    @task(3)
    @tag("checkout_success")
    def checkout_success(self) -> None:
        if ORDERS.exhausted:
            return  # MAX_ORDERS reached: this journey is skipped for the rest of the run
        JOURNEYS["checkout_success"] += 1
        self._place_order()

    @task(2)
    @tag("checkout_declined")
    def checkout_declined(self) -> None:
        JOURNEYS["checkout_declined"] += 1
        filled = self._fill_cart()
        if filled is None:
            return
        r = self.v.post(
            "/cart/checkout",
            forms.checkout_form(page.idempotency_key(filled[1].text) or "", forms.DECLINED_CARD),
            "/cart/checkout (declined card)",
            status=422,
            has=[page.ERROR_TITLE, "declined"],
            lacks=[page.ORDER_COMPLETE],
        )
        if r.ok and "/cart" not in r.text:
            self._fail(r, "declined page has no way back to the cart")
        self._empty_cart()

    @task(1)
    @tag("out_of_stock")
    def out_of_stock(self) -> None:
        JOURNEYS["out_of_stock"] += 1
        pid = random.choice(CONFIG.sold_out_products)
        self.v.post(
            "/cart",
            forms.add_to_cart_form(pid),
            "/cart (sold-out product)",
            status=422,
            has=[page.ERROR_TITLE, "out of stock"],
        )

    @task(1)
    @tag("review")
    def review(self) -> None:
        if REVIEWS.exhausted:
            return
        JOURNEYS["review"] += 1
        pid = self._any_product()
        if pid is None or not REVIEWS.take():
            return
        posted = False
        try:
            r = self.v.get(f"/product/{pid}", "/product/[id]", has=["Write a review"])
            if not r.ok:
                return
            author = f"loadgen bot {secrets.token_hex(3)}"
            text = f"{random.choice(REVIEW_TEXTS)} [{secrets.token_hex(3)}]"
            r = self.v.post(
                f"/product/{pid}/reviews",
                forms.review_form(author, random.randint(1, 5), text),
                "/product/[id]/reviews",
                status=303,
                location=[f"/product/{pid}"],
            )
            if not r.ok:
                return
            posted = True
            self.v.follow(r, "/product/[id] (after review)", has=[page.REVIEW_POSTED])
        finally:
            if not posted:
                REVIEWS.give_back()

    @task(1)
    @tag("account")
    def account(self) -> None:
        JOURNEYS["account"] += 1
        if not self._sign_in():
            return
        placed = self._place_order()
        if placed:
            self._check_history_and_mail(placed)
        else:
            self.v.get("/orders", "/orders", has=[page.ORDERS_TITLE])
            self.v.get("/emails", "/emails", has=[page.EMAILS_TITLE])
        self.v.post("/logout", {}, "/logout", status=(302, 303), location=["/"])

    # ---------------------------------------------------------------- account steps

    def _sign_in(self) -> bool:
        """Register once per simulated user, sign in on every later visit. True when signed in."""
        if self.account is None:
            return self._register()
        email, _ = self.account
        if not self.wrong_password_checked:
            self.wrong_password_checked = (
                True  # one wrong attempt per user: the login limit is 5 per address and minute
            )
            self.v.get("/login", "/login", has=["Sign in"])
            self.v.post(
                "/login",
                forms.login_form(email, "definitely-not-the-password"),
                "/login (wrong password)",
                status=422,
                has=[page.WRONG_CREDENTIALS],
            )
        r = self.v.post(
            "/login",
            forms.login_form(email, PASSWORD),
            "/login",
            status=(302, 303),
            location=["/account", "/orders"],
        )
        return r.ok and self._account_page(email)

    def _register(self) -> bool:
        tag = secrets.token_hex(4)
        email, name = f"loadgen-{tag}@example.com", f"Load Generator {tag}"
        self.v.get("/register", "/register", has=["Create an account", 'name="password"'])
        r = self.v.post(
            "/register",
            forms.register_form(name, email, PASSWORD),
            "/register",
            status=(302, 303),
            location=["/account", "/orders"],
        )
        if not r.ok:
            return False
        self.account = (email, name)
        return self._account_page(email)

    def _account_page(self, email: str) -> bool:
        return self.v.get("/account", "/account", has=[email]).ok

    def _check_history_and_mail(self, order: str) -> None:
        h = self.v.get("/orders", "/orders", has=[page.ORDERS_TITLE])
        if h.ok and order not in page.order_ids(h.text):
            self._fail(h, "new order missing from the order history")
        self.v.get(f"/orders/{order}", "/orders/[id]", has=["placed"])
        mail = None
        for attempt in range(1, MAIL_POLLS + 1):
            last = attempt == MAIL_POLLS
            with self.client.get("/emails", name="/emails (poll for confirmation)", catch_response=True) as resp:
                found = resp.status_code == 200 and page.mail_for_order(resp.text, order)
                if found:
                    mail = found
                    resp.success()
                elif resp.status_code != 200 or last:
                    resp.failure(f"confirmation mail did not arrive (HTTP {resp.status_code})")
                else:
                    resp.success()  # not there yet: that is normal for the first seconds
            if mail or resp.status_code != 200:
                break
            self._sleep(1.0)
        if mail:
            m = self.v.get(mail, "/emails/[id]", has=["Your Everly order confirmation"])
            if m.ok and not page.mail_is_sandboxed(m.text):
                self._fail(m, "mail is not shown in a sandboxed iframe")

    @staticmethod
    def _sleep(seconds: float) -> None:
        import gevent

        gevent.sleep(seconds)


# -------------------------------------------------------------------- summary and exit code


def summarize(environment) -> tuple[str, float, int]:
    """Return (text, fail_ratio, total requests) for the finished run."""
    total = environment.stats.total
    ratio = total.fail_ratio
    lines = [
        "",
        "================ load-generator summary ================",
        f"host:            {CONFIG.host}",
        f"requests:        {total.num_requests}",
        f"failures:        {total.num_failures} ({ratio * 100:.2f} %)",
        f"response time:   median {total.median_response_time:.0f} ms, "
        f"p95 {total.get_response_time_percentile(0.95):.0f} ms, p99 {total.get_response_time_percentile(0.99):.0f} ms",
        f"requests/s:      {total.total_rps:.1f}",
        f"orders placed:   {len(ORDERS_PLACED)} (cap MAX_ORDERS={CONFIG.max_orders})",
        f"reviews posted:  {REVIEWS.used} (cap MAX_REVIEWS={CONFIG.max_reviews})",
        "journeys run:    " + (", ".join(f"{k}={v}" for k, v in sorted(JOURNEYS.items())) or "none"),
    ]
    if environment.stats.errors:
        lines.append("failures by cause:")
        for err in sorted(environment.stats.errors.values(), key=lambda e: -e.occurrences):
            lines.append(f"  {err.occurrences:5d}x  {err.method} {err.name}: {err.error}")
    return "\n".join(lines), ratio, total.num_requests


@events.quitting.add_listener
def finish(environment, **_kw) -> None:
    text, ratio, requests = summarize(environment)
    if requests == 0:
        verdict, code = "FAILED: no request was made", 1
    elif ratio > CONFIG.fail_ratio:
        verdict, code = f"FAILED: failure ratio {ratio:.4f} is above FAIL_RATIO={CONFIG.fail_ratio}", 1
    else:
        verdict, code = f"PASSED: failure ratio {ratio:.4f} is within FAIL_RATIO={CONFIG.fail_ratio}", 0
    print(f"{text}\nresult:          {verdict}\n========================================================", flush=True)
    environment.process_exit_code = code
