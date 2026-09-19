import pytest

from app.detect import InvalidInput, classify, extract_url_handle, normalise_username
from app.models import InputType


def test_classify_email():
    result = classify("Someone@Example.com")
    assert result.input_type == InputType.EMAIL
    assert result.normalised == "someone@example.com"


def test_classify_phone_gb_default():
    result = classify("07911 123456")
    assert result.input_type == InputType.PHONE
    assert result.normalised == "+447911123456"


def test_classify_phone_with_country_code():
    result = classify("+1 415 555 2671")
    assert result.input_type == InputType.PHONE


def test_classify_username():
    result = classify("@some_user.99")
    assert result.input_type == InputType.USERNAME
    assert result.normalised == "some_user.99"


def test_classify_name_company():
    result = classify("Jane Doe, Acme Corp")
    assert result.input_type == InputType.NAME_COMPANY
    assert result.detail["name"] == "Jane Doe"
    assert result.detail["company"] == "Acme Corp"


def test_classify_url():
    result = classify("https://github.com/octocat")
    assert result.input_type == InputType.URL
    assert result.detail["handle"] == "octocat"


def test_classify_empty_rejected():
    with pytest.raises(InvalidInput):
        classify("")


def test_classify_too_long_rejected():
    with pytest.raises(InvalidInput):
        classify("a" * 400)


@pytest.mark.parametrize(
    "value",
    [
        "; rm -rf ~",
        "--help",
        "-h",
        "user\nname",
        "a" * 41,
        "user name",
    ],
)
def test_username_rejects_dangerous_input(value):
    with pytest.raises(InvalidInput):
        normalise_username(value)


def test_username_strips_leading_at():
    assert normalise_username("@bob") == "bob"


def test_extract_url_handle_linkedin():
    domain, handle = extract_url_handle("https://www.linkedin.com/in/jane-doe/")
    assert domain == "linkedin.com"
    assert handle == "jane-doe"


def test_hint_override_is_tried_first():
    # A numeric-looking username should classify as username when hinted,
    # even though it also matches the phone digit heuristic.
    result = classify("123456", hint="username")
    assert result.input_type == InputType.USERNAME
