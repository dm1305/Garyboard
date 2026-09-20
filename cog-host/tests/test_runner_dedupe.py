from app.models import Confidence, Finding, Kind
from app.runner import _dedupe_findings


def _finding(module, url=None, confidence=Confidence.MEDIUM, title="x"):
    return Finding(module=module, kind=Kind.ACCOUNT, title=title, url=url, confidence=confidence)


def test_dedupe_merges_same_url_keeping_higher_confidence():
    findings = [
        _finding("sherlock", url="https://github.com/octocat", confidence=Confidence.MEDIUM),
        _finding("github", url="https://github.com/octocat", confidence=Confidence.HIGH),
    ]
    result = _dedupe_findings(findings)
    assert len(result) == 1
    assert result[0].module == "github"
    assert result[0].confidence == Confidence.HIGH
    assert set(result[0].detail["also_found_by"]) == {"sherlock", "github"}


def test_dedupe_leaves_distinct_urls_alone():
    findings = [
        _finding("sherlock", url="https://github.com/octocat"),
        _finding("maigret", url="https://launchpad.net/~octocat"),
    ]
    result = _dedupe_findings(findings)
    assert len(result) == 2


def test_dedupe_leaves_urlless_findings_alone():
    findings = [
        _finding("email_offline", url=None, title="MX records found"),
        _finding("email_offline", url=None, title="No breaches found"),
    ]
    result = _dedupe_findings(findings)
    assert len(result) == 2
    assert all("also_found_by" not in f.detail for f in result)


def test_dedupe_keeps_first_on_equal_confidence():
    findings = [
        _finding("maigret", url="https://x.com/bob", confidence=Confidence.MEDIUM, title="first"),
        _finding("sherlock", url="https://x.com/bob", confidence=Confidence.MEDIUM, title="second"),
    ]
    result = _dedupe_findings(findings)
    assert len(result) == 1
    assert result[0].title == "first"
