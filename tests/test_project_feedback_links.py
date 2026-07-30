import re
from html.parser import HTMLParser
from pathlib import Path

from tglarn_bot.texts import ABOUT_TEXT

_ROOT = Path(__file__).parents[1]
_ISSUES_URL = "https://github.com/SimonBorin/tglarn/issues"
_REPOSITORY_URL = "https://github.com/SimonBorin/tglarn"
_PAGES_URL = "https://simonborin.github.io/tglarn/"


class _VisibleHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text: list[str] = []
        self.links: list[str] = []
        self._hidden_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "template"}:
            self._hidden_depth += 1
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "template"} and self._hidden_depth:
            self._hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._hidden_depth:
            self.text.append(data)


def test_readme_has_visible_beta_issue_report_block() -> None:
    readme = (_ROOT / "README.md").read_text()
    visible_readme = re.sub(r"<!--.*?-->", "", readme, flags=re.DOTALL)

    assert "## Beta" in visible_readme
    assert "beta" in visible_readme.lower()
    assert "issue" in visible_readme.lower()
    assert f"]({_ISSUES_URL})" in visible_readme


def test_pages_has_visible_beta_notice_and_project_links() -> None:
    parser = _VisibleHtmlParser()
    parser.feed((_ROOT / "site/index.html").read_text())
    visible_text = " ".join(parser.text).lower()

    assert "beta" in visible_text
    assert "issue" in visible_text
    assert _ISSUES_URL in parser.links
    assert _REPOSITORY_URL in parser.links


def test_bot_about_links_to_canonical_pages_site() -> None:
    about = ABOUT_TEXT.format(version="9.8.7")

    assert _PAGES_URL in about
