from PIL import Image
from tglarn_bot.map_image import (
    _IMAGE_VIEWPORT_HEIGHT,
    _IMAGE_VIEWPORT_WIDTH,
    _PADDING,
    _TILE,
    cleanup_rendered_game_image,
    render_game_image,
)
from tglarn_game import GameResponse


def test_render_game_image_creates_png_from_map_snapshot() -> None:
    response = GameResponse(
        state={},
        screen="\n".join(["." * 4, ".@S.", "Spells: 1(2)", "HP: 8 (8)"]),
        log=["A snake hisses."],
        status={
            "viewport": {"width": 4, "height": 2},
            "map_snapshot": {
                "version": 1,
                "width": 4,
                "height": 2,
                "level": "1",
                "player": {"x": 1, "y": 1},
                "glyphs": ["....", ".@S."],
                "layers": ["FFFF", "FPFM"],
            },
        },
    )

    rendered = render_game_image(response)

    assert rendered is not None
    try:
        assert rendered.path.exists()
        assert "Spells: 1(2)" in rendered.caption
        assert "A snake hisses." in rendered.caption
        with Image.open(rendered.path) as image:
            assert image.size[0] > 4
            assert image.size[1] > 2
    finally:
        cleanup_rendered_game_image(rendered)


def test_render_game_image_skips_text_only_response() -> None:
    response = GameResponse(state={}, screen="Inventory", status={})

    assert render_game_image(response) is None


def test_render_game_image_crops_wide_snapshot_to_narrow_viewport() -> None:
    width = 67
    height = 17
    response = GameResponse(
        state={},
        screen="\n".join(["." * 23 for _ in range(height)] + ["Spells: 1(2)"]),
        status={
            "viewport": {"width": 23, "height": height},
            "map_snapshot": {
                "version": 1,
                "width": width,
                "height": height,
                "level": "H",
                "player": {"x": 33, "y": 8},
                "glyphs": ["." * width for _ in range(height)],
                "layers": ["F" * width for _ in range(height)],
            },
        },
    )

    rendered = render_game_image(response)

    assert rendered is not None
    try:
        with Image.open(rendered.path) as image:
            assert image.size == (
                _IMAGE_VIEWPORT_WIDTH * _TILE + _PADDING * 2,
                _IMAGE_VIEWPORT_HEIGHT * _TILE + _PADDING * 2,
            )
    finally:
        cleanup_rendered_game_image(rendered)
