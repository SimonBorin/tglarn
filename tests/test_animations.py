from PIL import Image
from tglarn_bot.animations import (
    CREDIT_TEXTS,
    CREDITS_BODY_FONT_SIZE,
    CREDITS_CACHE_NAMESPACE,
    CREDITS_FONT_CANDIDATES,
    SPLASH_CAPTIONS,
    credits_frame_paths,
    splash_image_path,
)
from tglarn_bot.handlers import _can_keep_splash_message


def test_splash_uses_five_loading_frames() -> None:
    assert len(SPLASH_CAPTIONS) == 5
    assert SPLASH_CAPTIONS[0].endswith("[#----]")
    assert SPLASH_CAPTIONS[-1].endswith("[#####]")


def test_credits_include_bot_and_upstream_authors() -> None:
    credits = "\n".join(CREDIT_TEXTS)

    assert "Simon.A.Borin" in credits
    assert "@ringcentral.com" in credits
    assert "Codex" in credits
    assert "Noah Morgan" in credits
    assert "Phil Cordier" in credits
    assert "Bridgit Spitznagel" in credits
    assert "Chris Reuter" in credits
    assert "Greg McIntyre" in credits


def test_credits_use_larger_cached_frames() -> None:
    paths = credits_frame_paths()

    assert len(paths) == len(CREDIT_TEXTS)
    assert CREDITS_CACHE_NAMESPACE in str(paths[0].parent)
    assert CREDITS_BODY_FONT_SIZE >= 80
    assert any(path.exists() for path in CREDITS_FONT_CANDIDATES)

    with Image.open(paths[0]) as image:
        bright_text_pixels = []
        for y in range(image.height):
            for x in range(image.width):
                r, g, b = image.getpixel((x, y))
                if r > 235 and g > 205 and b > 175:
                    bright_text_pixels.append((x, y))

    text_top = min(y for _, y in bright_text_pixels)
    text_bottom = max(y for _, y in bright_text_pixels)
    assert text_bottom - text_top > 360


def test_splash_image_asset_is_packaged_in_source_tree() -> None:
    assert splash_image_path().name == "larn_01.png"
    assert splash_image_path().exists()


def test_intro_splash_can_remain_as_photo_message() -> None:
    assert _can_keep_splash_message("<b>Before the Caverns</b>", False)
    assert not _can_keep_splash_message("<pre>map</pre>", False)
    assert not _can_keep_splash_message("<b>Before the Caverns</b>", True)
