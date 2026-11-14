import pytest

from loadgen.budget import Budget
from loadgen.config import Config, ConfigError
from loadgen.forms import DECLINED_CARD, OK_CARD, checkout_form


def test_defaults():
    c = Config.from_env({})
    assert c.host == "http://frontend:8080"
    assert (c.users, c.spawn_rate, c.max_orders, c.fail_ratio) == (5, 1.0, 30, 0.01)
    assert (c.think_min, c.think_max) == (1.0, 3.0)
    assert c.sold_out_products == ("volleyball-153",)


def test_overrides():
    c = Config.from_env(
        {"HOST": "http://localhost:8080/", "USERS": "3", "RUN_TIME": "1m30s", "MAX_ORDERS": "0", "FAIL_RATIO": "0.2",
         "SOLD_OUT_PRODUCTS": "a-1, b-2"}
    )  # fmt: skip
    assert c.host == "http://localhost:8080"
    assert c.users == 3
    assert c.run_time == "1m30s"
    assert c.max_orders == 0
    assert c.fail_ratio == 0.2
    assert c.sold_out_products == ("a-1", "b-2")


@pytest.mark.parametrize(
    "env",
    [
        {"HOST": "frontend:8080"},
        {"HOST": "http://frontend:8080/shop"},
        {"USERS": "0"},
        {"USERS": "many"},
        {"RUN_TIME": "forever"},
        {"FAIL_RATIO": "2"},
        {"MAX_ORDERS": "-1"},
        {"THINK_MIN": "5", "THINK_MAX": "1"},
    ],
)
def test_bad_values_are_refused(env):
    with pytest.raises(ConfigError):
        Config.from_env(env)


def test_budget_caps_and_gives_back():
    b = Budget(2)
    assert b.take() and b.take()
    assert not b.take()
    assert b.exhausted
    b.give_back()
    assert not b.exhausted
    assert b.take()


def test_budget_zero_never_allows():
    assert not Budget(0).take()


def test_checkout_form_fields():
    f = checkout_form("KEY", OK_CARD)
    assert f["idempotency_key"] == "KEY"
    assert f["credit_card_number"] == "4111111111111111"
    assert checkout_form("K", DECLINED_CARD)["credit_card_number"] == "4000000000000002"
    # every field the cart form posts (apps/frontend/templates/cart.html)
    assert set(f) == {
        "idempotency_key", "email", "street_address", "zip_code", "city", "state", "country",
        "credit_card_number", "credit_card_expiration_month", "credit_card_expiration_year", "credit_card_cvv",
    }  # fmt: skip


def test_journeys_filter():
    from loadgen.__main__ import build_argv

    assert Config.from_env({}).journeys == ()
    c = Config.from_env({"JOURNEYS": "account, browse"})
    assert c.journeys == ("account", "browse")
    argv = build_argv(c, "journeys.py")
    assert argv[argv.index("--tags") + 1 :] == ["account", "browse"]
    assert "--tags" not in build_argv(Config(), "journeys.py")
    with pytest.raises(ConfigError):
        Config.from_env({"JOURNEYS": "browse,nope"})


def test_every_task_has_a_journey_name():
    from loadgen.config import JOURNEY_NAMES
    from loadgen.journeys import Shopper

    tasks = {t.__name__ for t in Shopper.tasks}
    assert tasks == set(JOURNEY_NAMES)


def test_request_timeout_default_and_bounds():
    assert Config.from_env({}).request_timeout == 30.0
    assert Config.from_env({"REQUEST_TIMEOUT": "2.5"}).request_timeout == 2.5
    for bad in ("0", "0.01", "301", "slow"):
        with pytest.raises(ConfigError):
            Config.from_env({"REQUEST_TIMEOUT": bad})
