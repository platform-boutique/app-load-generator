"""Visitor.step against a tiny local HTTP server serving saved fixtures: checks, cookies, redirects."""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from locust.clients import HttpSession
from locust.event import EventHook, Events

from loadgen.client import Visitor


class Shop(BaseHTTPRequestHandler):
    routes: dict = {}
    seen_cookies: list = []

    def log_message(self, *args):  # silence
        pass

    def _serve(self):
        Shop.seen_cookies.append(self.headers.get("Cookie"))
        status, body, headers = Shop.routes.get(self.path, (404, "not found", {}))
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        data = body.encode()
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = _serve


@pytest.fixture
def shop():
    Shop.routes = {}
    Shop.seen_cookies = []
    server = HTTPServer(("127.0.0.1", 0), Shop)
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()
    host = f"http://127.0.0.1:{server.server_port}"
    events = Events()
    events.request = EventHook()
    fired = []
    events.request.add_listener(lambda **kw: fired.append(kw))
    visitor = Visitor(HttpSession(base_url=host, request_event=events.request, user=None), host)
    yield visitor, fired, host
    server.shutdown()


def test_ok_page_with_markers_is_a_success(shop, fixture):
    visitor, fired, _ = shop
    Shop.routes["/"] = (200, fixture("home"), {})
    r = visitor.get("/", "/", has=["Everly"])
    assert r.ok and r.status == 200
    assert fired[-1]["exception"] is None


def test_missing_marker_is_a_failure(shop, fixture):
    visitor, fired, _ = shop
    Shop.routes["/"] = (200, "<html>maintenance</html>", {})
    r = visitor.get("/", "/", has=["Everly"])
    assert not r.ok
    assert "missing marker 'Everly'" in r.reasons[0]
    assert fired[-1]["exception"] is not None


def test_expected_422_counts_as_success_and_200_does_not(shop, fixture):
    visitor, fired, _ = shop
    Shop.routes["/declined"] = (422, fixture("declined"), {})
    ok = visitor.post("/declined", {}, "POST declined", status=422, has=["declined"], lacks=["Your order is complete"])
    assert ok.ok
    Shop.routes["/declined"] = (200, fixture("order"), {})
    bad = visitor.post("/declined", {}, "POST declined", status=422)
    assert not bad.ok and "HTTP 200, expected 422" in bad.reasons[0]


def test_unexpected_marker_fails(shop, fixture):
    visitor, _, _ = shop
    Shop.routes["/o"] = (422, fixture("order"), {})
    r = visitor.get("/o", "x", status=422, lacks=["Your order is complete"])
    assert not r.ok and "unexpected marker" in r.reasons[0]


def test_server_error_is_a_failure(shop):
    visitor, _, _ = shop
    Shop.routes["/e"] = (503, "down", {})
    assert not visitor.get("/e", "x").ok


def test_connection_error_is_a_failure():
    events = Events()
    events.request = EventHook()
    visitor = Visitor(
        HttpSession(base_url="http://127.0.0.1:9", request_event=events.request, user=None), "http://127.0.0.1:9"
    )
    r = visitor.get("/", "x")
    assert not r.ok and r.status == 0


def test_leaking_page_is_a_failure(shop):
    visitor, _, _ = shop
    Shop.routes["/l"] = (200, "<p>rpc error: code = Internal</p>", {})
    r = visitor.get("/l", "x")
    assert not r.ok and "leaks internals" in r.reasons[0]


def test_redirect_is_not_followed_and_target_is_checked(shop):
    visitor, _, host = shop
    Shop.routes["/add"] = (302, "", {"Location": "/cart"})
    Shop.routes["/evil"] = (302, "", {"Location": "http://evil.example/x"})
    Shop.routes["/elsewhere"] = (302, "", {"Location": "/somewhere-else"})
    ok = visitor.post("/add", {}, "add", status=(302, 303), location=["/cart"])
    assert ok.ok and ok.location == "/cart"
    assert not visitor.post("/evil", {}, "evil", status=302, location=["/cart"]).ok
    assert not visitor.post("/elsewhere", {}, "elsewhere", status=302, location=["/cart"]).ok
    # follow() refuses a foreign Location and uses the same host otherwise
    Shop.routes["/cart"] = (200, "cart", {})
    assert visitor.follow(ok, "cart").ok
    foreign = visitor.post("/evil", {}, "evil", status=302)
    assert visitor.follow(foreign, "never") is None
    assert host


def test_secure_cookie_is_sent_back_over_http(shop):
    visitor, _, _ = shop
    Shop.routes["/"] = (200, "hi", {"Set-Cookie": "shop_session-id=abc123; Path=/; Secure; HttpOnly; SameSite=Strict"})
    Shop.routes["/cart"] = (200, "cart", {})
    visitor.get("/", "home")
    visitor.get("/cart", "cart")
    assert "shop_session-id=abc123" in (Shop.seen_cookies[-1] or "")


def test_a_request_that_outlasts_the_timeout_is_a_failure_with_status_0():
    """CODE-05: no request waits forever. The server holds the answer back until the test is over."""
    import http.server

    release = threading.Event()

    class Hanging(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            release.wait(60)  # a client without a timeout would sit here for a minute and then get a 200
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Hanging)
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()
    host = f"http://127.0.0.1:{server.server_port}"
    events = Events()
    events.request = EventHook()
    visitor = Visitor(HttpSession(base_url=host, request_event=events.request, user=None), host, timeout=0.2)
    try:
        r = visitor.get("/", "x")
        assert not r.ok and r.status == 0
        assert "no response" in r.reasons[0]
    finally:
        release.set()
        server.shutdown()
        server.server_close()


def test_the_visitor_default_timeout_is_set():
    from loadgen.client import DEFAULT_TIMEOUT

    assert Visitor(object(), "http://x").timeout == DEFAULT_TIMEOUT == 30.0
