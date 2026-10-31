"""The HTML helpers against pages saved from the running shop (tests/fixtures, trimmed, demo data only)."""

from loadgen import page

ORDER = "11291482-08f6-5a12-9bad-6d98201216a5"


def test_card_product_ids_on_home(fixture):
    ids = page.card_product_ids(fixture("home"))
    assert len(ids) == 24
    assert len(set(ids)) == 24
    assert "american-football-137" in ids
    assert all("/" not in i and "?" not in i for i in ids)


def test_departments(fixture):
    assert page.departments(fixture("home")) == ["women", "men", "accessories", "beauty", "home", "kitchen", "sports"]


def test_department_page_lists_cards(fixture):
    ids = page.card_product_ids(fixture("dept"))
    assert ids
    assert set(ids) != set(page.card_product_ids(fixture("home")))


def test_next_page_path_and_pager(fixture):
    assert page.next_page_path(fixture("home")) == "/?page=2"
    assert page.page_paths(fixture("home"))[:2] == ["/?page=2", "/?page=3"]
    # last page: no "next" link
    assert page.next_page_path(fixture("page5")) is None


def test_product_page(fixture):
    p = fixture("product")
    assert page.has_add_to_cart_form(p, "american-football-137")
    assert not page.has_add_to_cart_form(p, "something-else-1")
    assert page.stock_state(p) == "in"
    assert page.tags(p) == ["sports equipment", "american football"]


def test_recommendations(fixture):
    recs = page.recommended_ids(fixture("product"))
    assert recs[:2] == ["fork-58", "mug-tree-stand-67"]
    assert len(recs) == len(set(recs)) >= 3
    # the home page has no recommendations block
    assert page.recommended_ids(fixture("home")) == []


def test_sold_out_product_page(fixture):
    p = fixture("product-out")
    assert page.stock_state(p) == "out"
    assert page.has_add_to_cart_form(p, "volleyball-153")


def test_idempotency_key_from_cart(fixture):
    assert page.idempotency_key(fixture("cart")) == "8FgCz1FA89mdrYLJsrqs2g"
    assert page.cart_lists(fixture("cart"), "american-football-137")


def test_empty_cart_has_no_key(fixture):
    c = fixture("cart-empty")
    assert page.idempotency_key(c) is None
    assert page.contains(c, page.CART_EMPTY)
    assert not page.cart_lists(c, "american-football-137")


def test_order_confirmation(fixture):
    o = fixture("order")
    assert page.contains(o, page.ORDER_COMPLETE)
    assert page.order_id(o) == ORDER
    assert page.tracking_number(o) == "OM-66510-335063722"


def test_order_id_missing_on_other_pages(fixture):
    assert page.order_id(fixture("declined")) is None
    assert not page.contains(fixture("declined"), page.ORDER_COMPLETE)


def test_order_history_and_tracking(fixture):
    assert page.order_ids(fixture("orders")) == [ORDER]
    assert page.contains(fixture("orders"), page.ORDERS_TITLE)
    assert page.contains(fixture("track"), "placed")
    assert page.tracking_number(fixture("track")) == "OM-66510-335063722"


def test_mailbox(fixture):
    e = fixture("emails")
    assert page.contains(e, page.EMAILS_TITLE)
    path = page.mail_for_order(e, ORDER)
    assert path == "/emails/e5aef1a3-7cf8-4aa1-9b56-319f5a8618b6?order=" + ORDER
    assert page.mail_for_order(e, "00000000-0000-0000-0000-000000000000") is None
    assert page.mail_is_sandboxed(fixture("mail"))
    assert not page.mail_is_sandboxed(fixture("orders"))


def test_error_pages(fixture):
    assert page.error_message(fixture("declined")).startswith("We could not process that: Card declined")
    assert "out of stock" in page.error_message(fixture("soldout")).lower()
    assert page.error_message(fixture("home")) == ""
    assert not page.leaks_internals(fixture("declined"))


def test_login_failure_marker(fixture):
    assert page.contains(fixture("login422"), page.WRONG_CREDENTIALS)
    assert not page.contains(fixture("login"), page.WRONG_CREDENTIALS)


def test_search_without_hits(fixture):
    n = fixture("nothing")
    assert page.contains(n, page.NOTHING_FOUND)
    assert page.card_product_ids(n) == []


def test_brand_marker(fixture):
    assert page.contains(fixture("home"), page.BRAND)


def test_leak_detector():
    assert page.leaks_internals("rpc error: code = Unavailable")
    assert page.leaks_internals("goroutine 12 [running]")
    assert page.leaks_internals("handler.go:123")
    assert not page.leaks_internals("<p>Card declined: Your card was declined</p>")


def test_same_origin_path():
    host = "http://localhost:8080"
    assert page.same_origin_path(host, "/product/x-1") == "/product/x-1"
    assert page.same_origin_path(host, "/?category=men&page=2") == "/?category=men&page=2"
    assert page.same_origin_path(host, "http://localhost:8080/cart") == "/cart"
    assert page.same_origin_path(host, "http://evil.example/cart") is None
    assert page.same_origin_path(host, "//evil.example/cart") is None
    assert page.same_origin_path(host, "https://localhost:8080/cart") is None
    assert page.same_origin_path(host, "javascript:alert(1)") is None


def test_search_path_quotes():
    assert page.search_path("american football") == "/?q=american%20football"
