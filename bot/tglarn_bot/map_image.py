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
    if snapshot is None:
        return None

    image = _draw_snapshot(snapshot)
    with tempfile.NamedTemporaryFile(prefix="tglarn-map-", suffix=".png", delete=False) as tmp:
        path = Path(tmp.name)
    image.save(path)
    return RenderedGameImage(path=path, caption=_render_caption(response, prefix_html))


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


def _draw_snapshot(snapshot: dict[str, Any]) -> Image.Image:
    width = int(snapshot["width"])
    height = int(snapshot["height"])
    glyphs: list[str] = snapshot["glyphs"]
    layers: list[str] = snapshot["layers"]
    image = Image.new(
        "RGB",
        (width * _TILE + _PADDING * 2, height * _TILE + _PADDING * 2),
        "#0d1016",
    )
    draw = ImageDraw.Draw(image)
    font = _load_font(_TILE - 4)

    for y in range(height):
        for x in range(width):
            layer = layers[y][x]
            glyph = glyphs[y][x]
            palette = _LAYER_COLORS.get(layer, _DEFAULT_LAYER)
            left = _PADDING + x * _TILE
            top = _PADDING + y * _TILE
            draw.rectangle(
                (left, top, left + _TILE - 1, top + _TILE - 1),
                fill=palette["bg"],
                outline=_GRID_COLOR,
            )
            _draw_glyph(draw, font, glyph, layer, left, top, palette["fg"])

    return image


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


def _render_caption(response: GameResponse, prefix_html: str | None) -> str:
    parts: list[str] = []
    if prefix_html:
        parts.append(prefix_html)

    stats = _status_lines(response)
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
