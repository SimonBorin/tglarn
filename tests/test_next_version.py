import pytest

from scripts.next_version import bump_version, latest_version, next_version, parse_version


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0.1.0", (0, 1, 0)),
        ("v2.14.3", (2, 14, 3)),
        ("1.2", None),
        ("1.2.3-beta.1", None),
        ("01.2.3", None),
    ],
)
def test_parse_version(value, expected) -> None:
    assert parse_version(value) == expected


def test_latest_version_uses_semver_order() -> None:
    assert latest_version(["v0.9.9", "v0.10.0", "not-a-version", "1.2.3"]) == (1, 2, 3)


@pytest.mark.parametrize(
    ("bump", "expected"),
    [
        ("patch", (0, 1, 8)),
        ("minor", (0, 2, 0)),
        ("major", (1, 0, 0)),
    ],
)
def test_bump_version_resets_lower_components(bump, expected) -> None:
    assert bump_version((0, 1, 7), bump) == expected


def test_first_automatic_version_bumps_from_repository_base() -> None:
    assert next_version([], "patch") == "0.1.1"


def test_next_version_uses_latest_stable_tag() -> None:
    assert next_version(["v0.1.9", "v0.2.0", "v0.3.0-rc.1"], "patch") == "0.2.1"
