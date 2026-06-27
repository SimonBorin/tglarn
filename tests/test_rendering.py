from tglarn_bot.rendering import render_game_response
from tglarn_game import GameResponse


def test_render_game_response_escapes_html() -> None:
    response = GameResponse(
        state={},
        screen="A > B",
        log=["Use <look>"],
        status={},
    )

    rendered = render_game_response(response)

    assert "A &gt; B" in rendered
    assert "Use &lt;look&gt;" in rendered
    assert "<pre>" in rendered
