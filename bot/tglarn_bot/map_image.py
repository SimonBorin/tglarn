"""Pillow map rendering for ReLarn map snapshots."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from tglarn_game import GameResponse

_TILE = 28
_PADDING = 18
_CAPTION_LIMIT = 1024
_IMAGE_VIEWPORT_WIDTH = 23
_IMAGE_VIEWPORT_HEIGHT = 17
_TEXT_FONT_SIZE = 28
_TEXT_MIN_FONT_SIZE = 18
_TEXT_LINE_SPACING = 7
_TEXT_MARGIN_X = 18
_TEXT_MARGIN_Y = 18
_FONT_CANDIDATES = (
    Path(os.environ.get("RELARN_INSTALL_ROOT", "/opt/relarn"))
    / "share/relarn/lib/fonts/Inconsolata-Medium.ttf",
    Path("vendor/relarn/data/fonts/Inconsolata-Medium.ttf"),
)
_LAYER_COLORS = {
    "U": {"bg": "#07090d", "fg": "#323842"},
    "F": {"bg": "#171b22", "fg": "#39414d"},
    "W": {"bg": "#313942", "fg": "#c1cad3"},
    "O": {"bg": "#1e2430", "fg": "#f0c04f"},
    "M": {"bg": "#271a1d", "fg": "#f06a6a"},
    "P": {"bg": "#162a31", "fg": "#68d8ef"},
}
_GRID_COLOR = "#242a33"
_DEFAULT_LAYER = {"bg": "#171b22", "fg": "#d7dee7"}


@dataclass(frozen=True, slots=True)
class RenderedGameImage:
    path: Path
    caption: str


def render_game_image(
    response: GameResponse,
    prefix_html: str | None = None,
) -> RenderedGameImage | None:
    snapshot = _map_snapshot(response.status)
    text_screen = _text_screen(response)
    if snapshot is None and text_screen is None:
        return None

    image = (
        _draw_snapshot(snapshot)
        if snapshot is not None
        else _draw_text_screen(text_screen or "")
    )
    with tempfile.NamedTemporaryFile(prefix="tglarn-map-", suffix=".png", delete=False) as tmp:
        path = Path(tmp.name)
    image.save(path)
    return RenderedGameImage(
        path=path,
        caption=_render_caption(
            response,
            prefix_html,
            include_stats=snapshot is not None,
        ),
    )


def cleanup_rendered_game_image(rendered: RenderedGameImage | None) -> None:
    if rendered is None:
        return
    rendered.path.unlink(missing_ok=True)


def _map_snapshot(status: dict[str, Any]) -> dict[str, Any] | None:
    snapshot = status.get("map_snapshot")
    if not isinstance(snapshot, dict):
        return None
    width = snapshot.get("width")
    height = snapshot.get("height")
    glyphs = snapshot.get("glyphs")
    layers = snapshot.get("layers")
    if not isinstance(width, int) or not isinstance(height, int):
        return None
    if not isinstance(glyphs, list) or not isinstance(layers, list):
        return None
    if len(glyphs) != height or len(layers) != height:
        return None
    if any(not isinstance(row, str) or len(row) != width for row in glyphs + layers):
        return None
    return snapshot


def _text_screen(response: GameResponse) -> str | None:
    if response.screen.strip():
        return response.screen

    pending_prompt = response.status.get("pending_prompt")
    if isinstance(pending_prompt, dict):
        question = str(pending_prompt.get("question", "")).strip()
        if question:
            return question

    log_lines = [line.strip() for line in response.log if line.strip()]
    if log_lines:
        return "\n".join(log_lines)
    return None


def _draw_snapshot(snapshot: dict[str, Any]) -> Image.Image:
    glyphs: list[str] = snapshot["glyphs"]
    layers: list[str] = snapshot["layers"]
    viewport_left, viewport_top, viewport_width, viewport_height = _viewport(snapshot)
    image = Image.new(
        "RGB",
        (viewport_width * _TILE + _PADDING * 2, viewport_height * _TILE + _PADDING * 2),
        "#0d1016",
    )
    draw = ImageDraw.Draw(image)
    font = _load_font(_TILE - 4)

    for y in range(viewport_height):
        source_y = viewport_top + y
        for x in range(viewport_width):
            source_x = viewport_left + x
            layer = layers[source_y][source_x]
            glyph = glyphs[source_y][source_x]
            palette = _LAYER_COLORS.get(layer, _DEFAULT_LAYER)
            tile_left = _PADDING + x * _TILE
            tile_top = _PADDING + y * _TILE
            draw.rectangle(
                (tile_left, tile_top, tile_left + _TILE - 1, tile_top + _TILE - 1),
                fill=palette["bg"],
                outline=_GRID_COLOR,
            )
            _draw_glyph(draw, font, glyph, layer, tile_left, tile_top, palette["fg"])

    return image


def _draw_text_screen(screen: str) -> Image.Image:
    width = _IMAGE_VIEWPORT_WIDTH * _TILE + _PADDING * 2
    height = _IMAGE_VIEWPORT_HEIGHT * _TILE + _PADDING * 2
    text_left = _PADDING + _TEXT_MARGIN_X
    text_top = _PADDING + _TEXT_MARGIN_Y
    text_width = width - (_PADDING + _TEXT_MARGIN_X) * 2
    text_height = height - (_PADDING + _TEXT_MARGIN_Y) * 2
    lines, font = _fit_text_lines(screen.splitlines() or [""], text_width, text_height)
    line_height = _text_line_height(ImageDraw.Draw(Image.new("RGB", (1, 1))), font)

    image = Image.new("RGB", (width, height), "#0d1016")
    draw = ImageDraw.Draw(image)
    _draw_text_background(draw)
    y = text_top
    for index, line in enumerate(lines):
        fill = "#f0c04f" if index == 0 else "#d7dee7"
        shadow = "#05070a"
        draw.text((text_left + 1, y + 1), line, fill=shadow, font=font)
        draw.text((text_left, y), line, fill=fill, font=font)
        y += line_height + _TEXT_LINE_SPACING
    return image


def _fit_text_lines(
    lines: list[str],
    max_width: int,
    max_height: int,
) -> tuple[list[str], ImageFont.ImageFont]:
    metrics = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    for size in range(_TEXT_FONT_SIZE, _TEXT_MIN_FONT_SIZE - 1, -2):
        font = _load_font(size)
        wrapped = _wrap_text_rows(lines, max_width, metrics, font)
        line_height = _text_line_height(metrics, font)
        total_height = len(wrapped) * line_height + max(0, len(wrapped) - 1) * _TEXT_LINE_SPACING
        if total_height <= max_height:
            return wrapped, font
    font = _load_font(_TEXT_MIN_FONT_SIZE)
    line_height = _text_line_height(metrics, font)
    max_lines = max(1, (max_height + _TEXT_LINE_SPACING) // (line_height + _TEXT_LINE_SPACING))
    return _wrap_text_rows(lines, max_width, metrics, font)[:max_lines], font


def _wrap_text_rows(
    lines: list[str],
    max_width: int,
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
) -> list[str]:
    wrapped: list[str] = []
    for line in lines:
        remaining = line
        if not remaining:
            wrapped.append("")
            continue
        while _text_width(draw, remaining, font) > max_width:
            split_at = _pixel_wrap_index(remaining, max_width, draw, font)
            if split_at <= 0:
                split_at = 1
            wrapped.append(remaining[:split_at].rstrip())
            remaining = remaining[split_at:].lstrip()
        wrapped.append(remaining)
    return wrapped


def _pixel_wrap_index(
    text: str,
    max_width: int,
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
) -> int:
    best_space = -1
    for index, char in enumerate(text, start=1):
        if char == " ":
            best_space = index
        if _text_width(draw, text[:index], font) > max_width:
            return best_space if best_space > 0 else index - 1
    return len(text)


def _draw_text_background(draw: ImageDraw.ImageDraw) -> None:
    palette = _LAYER_COLORS["F"]
    for y in range(_IMAGE_VIEWPORT_HEIGHT):
        for x in range(_IMAGE_VIEWPORT_WIDTH):
            tile_left = _PADDING + x * _TILE
            tile_top = _PADDING + y * _TILE
            draw.rectangle(
                (tile_left, tile_top, tile_left + _TILE - 1, tile_top + _TILE - 1),
                fill=palette["bg"],
                outline=_GRID_COLOR,
            )


def _text_line_height(draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), "Ag", font=font)
    return bbox[3] - bbox[1]


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _viewport(snapshot: dict[str, Any]) -> tuple[int, int, int, int]:
    width = int(snapshot["width"])
    height = int(snapshot["height"])
    viewport_width = min(width, _IMAGE_VIEWPORT_WIDTH)
    viewport_height = min(height, _IMAGE_VIEWPORT_HEIGHT)
    player = snapshot.get("player")
    player_x = player.get("x") if isinstance(player, dict) else None
    player_y = player.get("y") if isinstance(player, dict) else None
    center_x = player_x if isinstance(player_x, int) else width // 2
    center_y = player_y if isinstance(player_y, int) else height // 2
    left = _crop_start(center_x, viewport_width, width)
    top = _crop_start(center_y, viewport_height, height)
    return left, top, viewport_width, viewport_height


def _crop_start(center: int, size: int, total: int) -> int:
    if size >= total:
        return 0
    return max(0, min(center - size // 2, total - size))


def _draw_glyph(
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
    glyph: str,
    layer: str,
    left: int,
    top: int,
    fill: str,
) -> None:
    if layer == "U":
        return
    if layer == "F":
        center = left + _TILE // 2
        middle = top + _TILE // 2
        draw.ellipse((center - 2, middle - 2, center + 2, middle + 2), fill=fill)
        return
    bbox = draw.textbbox((0, 0), glyph, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    draw.text(
        (
            left + (_TILE - text_width) / 2 - bbox[0],
            top + (_TILE - text_height) / 2 - bbox[1],
        ),
        glyph,
        fill=fill,
        font=font,
    )


def _load_font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default(size=size)


def _render_caption(
    response: GameResponse,
    prefix_html: str | None,
    include_stats: bool = True,
) -> str:
    parts: list[str] = []
    if prefix_html:
        parts.append(prefix_html)

    stats = _status_lines(response) if include_stats else []
    if stats:
        parts.append(f"<pre>{escape(chr(10).join(stats))}</pre>")

    if response.log:
        log_text = "\n".join(f"- {escape(item)}" for item in response.log)
        parts.append(f"<b>Log</b>\n{log_text}")

    footer = "<i>Use /menu to open the main menu.</i>"
    parts.append(footer)
    caption = "\n\n".join(parts)
    if len(caption) <= _CAPTION_LIMIT:
        return caption
    if response.log:
        parts = [part for part in parts if not part.startswith("<b>Log</b>")]
        caption = "\n\n".join(parts)
    if len(caption) <= _CAPTION_LIMIT:
        return caption
    return footer


def _status_lines(response: GameResponse) -> list[str]:
    viewport = response.status.get("viewport")
    map_height = viewport.get("height") if isinstance(viewport, dict) else None
    lines = response.screen.splitlines()
    if not isinstance(map_height, int) or map_height < 0:
        return []
    return lines[map_height:]
