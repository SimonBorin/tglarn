"""Telegram photo animation assets for splash and game-over credits."""

from __future__ import annotations

import tempfile
from importlib.resources import files
from pathlib import Path

SPLASH_DELAY_SECONDS = 0.5
CREDITS_DELAY_SECONDS = 1.2
CREDITS_CACHE_NAMESPACE = "credits-v3"
CREDITS_TITLE_FONT_SIZE = 84
CREDITS_BODY_FONT_SIZE = 68
CREDITS_MIN_BODY_FONT_SIZE = 48

SPLASH_CAPTIONS = (
    "Loading LARN [#----]",
    "Loading LARN [##---]",
    "Loading LARN [###--]",
    "Loading LARN [####-]",
    "Loading LARN [#####]",
)

CREDIT_TEXTS = (
    "TGLarn Bot Creator\nSimon.A.Borin\n@ringcentral.com",
    "Created by Codex",
    "Original Larn\nNoah Morgan",
    "ULarn\nPhil Cordier",
    "iLarn\nBridgit Spitznagel\ni0lanthe",
    "ReLarn\nChris Reuter",
    "libfov\nGreg McIntyre",
    "Inconsolata Font\nRaph Levien and collaborators",
    "Thanks for playing",
)


def splash_frame_paths() -> list[Path]:
    source_path = _source_image_path()
    cache_dir = _cache_dir("splash")
    expected = [cache_dir / f"splash_{index:02d}.png" for index in range(1, 6)]
    if all(path.exists() for path in expected):
        return expected

    from PIL import Image

    with Image.open(source_path) as raw_image:
        image = raw_image.convert("RGB")
        width, height = image.size
        for index, path in enumerate(expected, start=1):
            reveal_width = round(width * index / len(expected))
            frame = Image.new("RGB", (width, height), "black")
            frame.paste(image.crop((0, 0, reveal_width, height)), (0, 0))
            frame.save(path)
    return expected


def credits_frame_paths() -> list[Path]:
    source_path = _source_image_path()
    cache_dir = _cache_dir(CREDITS_CACHE_NAMESPACE)
    expected = [cache_dir / f"credits_{index:02d}.png" for index in range(len(CREDIT_TEXTS))]
    if all(path.exists() for path in expected):
        return expected

    from PIL import Image, ImageDraw, ImageFont

    with Image.open(source_path) as raw_image:
        base = raw_image.convert("RGBA")
        font_title = _load_font(ImageFont, CREDITS_TITLE_FONT_SIZE)
        for index, text in enumerate(CREDIT_TEXTS):
            frame = base.copy()
            overlay = Image.new("RGBA", frame.size, (0, 0, 0, 105))
            frame.alpha_composite(overlay)

            draw = ImageDraw.Draw(frame)
            title = "GAME OVER" if index == 0 else "CREDITS"
            font_body = _load_fitted_font(
                ImageFont,
                text,
                max_size=CREDITS_BODY_FONT_SIZE,
                min_size=CREDITS_MIN_BODY_FONT_SIZE,
                max_width=frame.size[0] - 48,
            )
            _draw_centered_text(draw, frame.size, title, font_title, y=18)
            _draw_centered_text(draw, frame.size, text, font_body, y=frame.size[1] - 276)
            frame.convert("RGB").save(expected[index])
    return expected


def splash_image_path() -> Path:
    return _source_image_path()


def _source_image_path() -> Path:
    return Path(files("tglarn_bot").joinpath("assets/larn_01.png"))


def _cache_dir(name: str) -> Path:
    source_path = _source_image_path()
    stat = source_path.stat()
    cache_dir = (
        Path(tempfile.gettempdir())
        / f"tglarn-{name}-{stat.st_size}-{stat.st_mtime_ns}"
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _load_font(image_font_module, size: int):
    for font_name in ("DejaVuSans-Bold.ttf", "Arial.ttf"):
        try:
            return image_font_module.truetype(font_name, size)
        except OSError:
            continue
    return image_font_module.load_default()


def _load_fitted_font(
    image_font_module,
    text: str,
    max_size: int,
    min_size: int,
    max_width: int,
):
    from PIL import Image, ImageDraw

    metrics = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    for size in range(max_size, min_size - 1, -2):
        font = _load_font(image_font_module, size)
        bbox = metrics.multiline_textbbox((0, 0), text, font=font, spacing=8, align="center")
        if bbox[2] - bbox[0] <= max_width:
            return font
    return _load_font(image_font_module, min_size)


def _draw_centered_text(draw, image_size: tuple[int, int], text, font, y: int) -> None:
    x = image_size[0] // 2
    bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=8, align="center")
    width = bbox[2] - bbox[0]
    position = (x - width // 2, y)
    shadow_position = (position[0] + 2, position[1] + 2)
    draw.multiline_text(
        shadow_position,
        text,
        font=font,
        fill=(0, 0, 0, 210),
        spacing=8,
        align="center",
    )
    draw.multiline_text(
        position,
        text,
        font=font,
        fill=(255, 232, 204, 255),
        spacing=8,
        align="center",
    )
