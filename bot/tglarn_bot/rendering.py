"""Telegram rendering helpers."""

from html import escape

from tglarn_game import GameResponse


def render_game_response(response: GameResponse) -> str:
    parts = [f"<pre>{escape(response.screen)}</pre>"]
    if response.log:
        log_text = "\n".join(f"- {escape(item)}" for item in response.log)
        parts.append(f"<b>Log</b>\n{log_text}")
    parts.append("<i>Use /menu to open the main menu.</i>")
    return "\n\n".join(parts)
