from loadgen import journeys


def test_password_is_random_when_unset():
    a, b = journeys.make_password({}), journeys.make_password({})
    assert a != b
    assert len(a) >= 8
    assert journeys.make_password({"LOADGEN_PASSWORD": ""}) not in ("", a)


def test_password_from_environment():
    assert journeys.make_password({"LOADGEN_PASSWORD": "chosen-password-9"}) == "chosen-password-9"


def test_module_password_is_set_and_valid_for_the_shop():
    assert 8 <= len(journeys.PASSWORD.encode()) <= 72
