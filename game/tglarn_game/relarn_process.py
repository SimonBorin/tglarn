"""Process-backed adapter for the upstream ReLarn curses game.

This is intentionally a bridge adapter: it drives the original terminal game
through a pseudo-terminal, stores the native savefile as adapter state, and
renders the terminal screen back into Telegram-friendly fixed-width text.
"""

from __future__ import annotations

import base64
import fcntl
import os
import re
import select
import struct
import subprocess
import tempfile
import termios
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyte

from .models import GameAction, GameResponse, MapView

_TERMINAL_COLUMNS = 80
_TERMINAL_ROWS = 25
_MAP_ROWS = 17
_STATS_START_ROW = 17
_STATS_END_ROW = 19
_CONSOLE_START_ROW = 19
_ESCAPE = b"\x1b"
_SAVE_COMMAND = b"S"
_PROMPT_COMMAND_PREFIX = "prompt:"

_VIEWPORTS: dict[MapView, tuple[int, int]] = {
    "medium": (21, 11),
    "wide": (31, 15),
    "max": (52, 17),
}

_PROMPT_OPTION_RE = re.compile(r"\(([A-Za-z0-9])\)")
_CONFIRM_OPTION_RE = re.compile(r"\[([A-Za-z0-9]+)\]")
_PROMPT_START_RE = re.compile(r"(?:^|\s)(?:Do you|Do you want|Would you|Really|Are you)\b", re.I)
_PROMPT_LABEL_STOP_RE = re.compile(r",|\bor\b|\?|\(|\[|$", re.I)
_PICKLIST_OPTION_RE = re.compile(r"^\s*([A-Za-z])\.\s+(.+?)\s*$")
_CONFIRM_LABELS = {"y": "Yes", "n": "No"}
_SPELL_NAMES = tuple(
    sorted(
        {
            "protection",
            "magic missile",
            "dexterity",
            "sleep",
            "charm monster",
            "sonic spear",
            "web",
            "strength",
            "enlightenment",
            "healing",
            "cure blindness",
            "create monster",
            "phantasmal forces",
            "invisibility",
            "fireball",
            "cold",
            "polymorph",
            "cancellation",
            "haste self",
            "cloud kill",
            "vaporize rock",
            "dehydration",
            "lightning",
            "drain life",
            "invulnerable globe",
            "flood",
            "finger of death",
            "scare monster",
            "hold monster",
            "time stop",
            "teleport away",
            "magic fire",
            "make a wall",
            "sphere of annihilation",
            "banish",
            "summon demon",
            "walk through walls",
            "alter reality",
            "permanence",
        },
        key=len,
        reverse=True,
    )
)
_CHARACTER_CLASSES = {
    "ogre": "Ogre",
    "wizard": "Wizard",
    "klingon": "Klingon",
    "elf": "Elf",
    "rogue": "Rogue",
    "geek": "Geek",
    "dwarf": "Dwarf",
    "rambo": "Rambo",
}
_GENDERS = {"male", "female", "nonbinary"}
_DEFAULT_CHARACTER = {
    "name": "Tglarn",
    "class": "Geek",
    "gender": "male",
    "spouse_gender": "female",
}

_COMMAND_KEYS = {
    "north": b"k",
    "n": b"k",
    "up": b"k",
    "south": b"j",
    "s": b"j",
    "down": b"j",
    "east": b"l",
    "e": b"l",
    "right": b"l",
    "west": b"h",
    "w": b"h",
    "left": b"h",
    "northwest": b"y",
    "nw": b"y",
    "northeast": b"u",
    "ne": b"u",
    "southwest": b"b",
    "sw": b"b",
    "southeast": b"n",
    "se": b"n",
    "wait": b".",
    ".": b".",
    "look": b",",
    "l": b",",
    "inventory": b"i",
    "pack_weight": b"g",
    "wield": b"w",
    "wear": b"W",
    "take_off": b"T",
    "drop": b"d",
    "read": b"r",
    "quaff": b"q",
    "eat": b"e",
    "teleport": b"Z",
    "spells": b"D",
    "cast": b"c",
    "descend": b"g",
    "go down": b"g",
    ">": b"g",
}



@dataclass(slots=True)
class RelarnProcessAdapter:
    """Run upstream ReLarn for one Telegram action at a time."""

    binary_path: str | Path = "/opt/relarn/lib/relarn/relarn.bin"
    install_root: str | Path = "/opt/relarn"
    timeout_seconds: float = 3.0
    settle_seconds: float = 0.12

    def start(
        self,
        state: dict[str, Any] | None = None,
        map_view: MapView = "wide",
    ) -> GameResponse:
        if _state_save_blob(state) is None:
            return self._run_cycle(state, [], map_view, ["A new run begins."])
        response = self._run_cycle(state, [], map_view, ["Game loaded."])
        pending_prompt = _state_pending_prompt(state)
        if pending_prompt is None:
            return response
        actions = _prompt_actions(pending_prompt.get("options", []))
        question = str(pending_prompt.get("question", "Choose an option."))
        return GameResponse(
            state=response.state | {"pending_prompt": pending_prompt},
            screen=response.screen,
            log=[question],
            status=response.status | {"pending_prompt": pending_prompt},
            actions=actions,
        )

    def restart(self, map_view: MapView = "wide") -> GameResponse:
        return self._run_cycle(None, [], map_view, ["A new run begins."])

    def apply_command(
        self,
        state: dict[str, Any] | None,
        command: str,
        map_view: MapView = "wide",
    ) -> GameResponse:
        normalized = command.strip().lower()
        pending_prompt = _state_pending_prompt(state)
        prompt_answer = _prompt_answer_from_command(normalized, pending_prompt)
        if prompt_answer is not None and pending_prompt is not None:
            return self._answer_pending_prompt(state, pending_prompt, prompt_answer, map_view)

        key = _command_to_key(command)
        if key is None:
            response = self.start(state, map_view=map_view)
            return GameResponse(
                state=response.state,
                screen=response.screen,
                log=[
                    f"Unknown command: {command.strip()}.",
                    "Use buttons or /menu to see available actions.",
                ],
                status=response.status,
                actions=response.actions,
            )
        return self._run_cycle(state, [key], map_view, [])

    def _answer_pending_prompt(
        self,
        state: dict[str, Any] | None,
        pending_prompt: dict[str, Any],
        answer: str,
        map_view: MapView,
    ) -> GameResponse:
        base_save = pending_prompt.get("base_save_blob_b64")
        trigger_keys = _pending_trigger_keys(pending_prompt)
        if not isinstance(base_save, str) or not trigger_keys:
            response = self.start(state, map_view=map_view)
            return GameResponse(
                state=response.state,
                screen=response.screen,
                log=["That prompt is no longer available."],
                status=response.status,
                actions=response.actions,
            )

        prompt_state = {
            "adapter": "relarn_process",
            "save_blob_b64": base_save,
        }
        replay_keys = [key.encode("ascii") for key in trigger_keys]
        replay_keys.append(answer.encode("ascii"))
        return self._run_cycle(prompt_state, replay_keys, map_view, [])

    def _run_cycle(
        self,
        state: dict[str, Any] | None,
        keys: list[bytes],
        map_view: MapView,
        fallback_log: list[str],
    ) -> GameResponse:
        binary_path = Path(self.binary_path).resolve()
        install_root = Path(self.install_root).resolve()
        if not binary_path.exists():
            raise FileNotFoundError(f"ReLarn binary not found: {binary_path}")
        if not install_root.exists():
            raise FileNotFoundError(f"ReLarn install root not found: {install_root}")

        with tempfile.TemporaryDirectory(prefix="tglarn-relarn-") as tmp:
            home = Path(tmp)
            save_file = _prepare_home(home, state)
            terminal = _TerminalCapture(_TERMINAL_COLUMNS, _TERMINAL_ROWS)
            display_lines = _execute_relarn_cycle(
                binary_path=binary_path,
                install_root=install_root,
                home=home,
                keys=keys,
                terminal=terminal,
                timeout_seconds=self.timeout_seconds,
                settle_seconds=self.settle_seconds,
            )
            if not save_file.exists():
                raise RuntimeError("ReLarn did not write a savefile")
            save_blob = save_file.read_bytes()

        screen, log, status = _render_display_lines(display_lines, map_view)
        prompt = _detect_prompt(display_lines)
        encoded_save = base64.b64encode(save_blob).decode("ascii")
        next_state: dict[str, Any] = {
            "adapter": "relarn_process",
            "save_blob_b64": encoded_save,
            "save_size": len(save_blob),
        }
        character = _state_character(state)
        if character is not None:
            next_state["character"] = character
        actions: list[GameAction] = []
        if prompt is not None and keys:
            base_save_b64 = _prompt_base_save_b64(state)
            trigger_keys = _keys_to_text(keys)
            if base_save_b64 is not None and trigger_keys:
                pending_prompt = {
                    "question": prompt["question"],
                    "options": prompt["options"],
                    "trigger_keys": trigger_keys,
                    "base_save_blob_b64": base_save_b64,
                }
                next_state["pending_prompt"] = pending_prompt
                status["pending_prompt"] = pending_prompt
                actions = _prompt_actions(prompt["options"])

        return GameResponse(
            state=next_state,
            screen=screen,
            log=log or fallback_log,
            status=status | {"adapter": "relarn_process", "save_size": len(save_blob)},
            actions=actions,
        )


class _TerminalCapture:
    def __init__(self, columns: int, rows: int) -> None:
        self.screen = pyte.Screen(columns, rows)
        self.stream = pyte.ByteStream(self.screen)

    def feed(self, data: bytes) -> None:
        self.stream.feed(data)

    def lines(self) -> list[str]:
        return list(self.screen.display)

    def contains(self, text: str) -> bool:
        return any(text in line for line in self.screen.display)


def _prepare_home(home: Path, state: dict[str, Any] | None) -> Path:
    relarn_dir = home / ".relarn"
    save_dir = relarn_dir / "savegame"
    save_dir.mkdir(parents=True, exist_ok=True)
    (relarn_dir / "relarnrc").write_text(_relarnrc_for_state(state), encoding="utf-8")

    save_file = save_dir / "relarn.sav"
    save_blob = _state_save_blob(state)
    if save_blob is not None:
        save_file.write_bytes(save_blob)
    return save_file


def _relarnrc_for_state(state: dict[str, Any] | None) -> str:
    character = _state_character(state) or _DEFAULT_CHARACTER
    return (
        f"name:       {character['name']}\n"
        f"character:  {character['class']}\n"
        f"{character['gender']}\n"
        f"spouse_{character['spouse_gender']}\n"
        "no-introduction\n"
        "no-beep\n"
        "no-nap\n"
        "no-show-fov\n"
        "dark-screen\n"
    )


def _state_character(state: dict[str, Any] | None) -> dict[str, str] | None:
    if not state:
        return None
    raw = state.get("character")
    if not isinstance(raw, dict):
        return None

    name = str(raw.get("name") or _DEFAULT_CHARACTER["name"]).strip()[:30]
    class_value = str(raw.get("class") or _DEFAULT_CHARACTER["class"]).strip()
    class_name = _CHARACTER_CLASSES.get(class_value.lower(), class_value)
    if class_name not in _CHARACTER_CLASSES.values():
        class_name = _DEFAULT_CHARACTER["class"]

    gender = str(raw.get("gender") or _DEFAULT_CHARACTER["gender"]).strip().lower()
    if gender not in _GENDERS:
        gender = _DEFAULT_CHARACTER["gender"]

    spouse_gender = (
        str(raw.get("spouse_gender") or _DEFAULT_CHARACTER["spouse_gender"])
        .strip()
        .lower()
    )
    if spouse_gender not in _GENDERS:
        spouse_gender = _DEFAULT_CHARACTER["spouse_gender"]

    return {
        "name": name or _DEFAULT_CHARACTER["name"],
        "class": class_name,
        "gender": gender,
        "spouse_gender": spouse_gender,
    }


def _execute_relarn_cycle(
    binary_path: Path,
    install_root: Path,
    home: Path,
    keys: list[bytes],
    terminal: _TerminalCapture,
    timeout_seconds: float,
    settle_seconds: float,
) -> list[str]:
    master_fd, slave_fd = os.openpty()
    try:
        _set_terminal_size(slave_fd, _TERMINAL_ROWS, _TERMINAL_COLUMNS)
        env = os.environ.copy()
        env.update(
            {
                "HOME": str(home),
                "USER": "tglarn",
                "RELARN_INSTALL_ROOT": str(install_root),
                "TERM": "xterm-256color",
            }
        )
        process = subprocess.Popen(
            [str(binary_path)],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=str(home),
            env=env,
            close_fds=True,
            start_new_session=True,
        )
    finally:
        os.close(slave_fd)

    try:
        _read_until(
            master_fd,
            terminal,
            deadline=time.monotonic() + timeout_seconds,
            done=lambda: terminal.contains("Welcome"),
        )
        for key in keys:
            os.write(master_fd, key)
            _read_for(master_fd, terminal, settle_seconds)

        display_lines = terminal.lines()

        # Leave modal screens if the command opened one, then save and quit.
        os.write(master_fd, _ESCAPE)
        _read_for(master_fd, terminal, 0.03)
        os.write(master_fd, _SAVE_COMMAND)
        _read_process_to_exit(master_fd, terminal, process, timeout_seconds)
        return display_lines
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                process.kill()
        os.close(master_fd)


def _set_terminal_size(fd: int, rows: int, columns: int) -> None:
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))


def _read_until(
    fd: int,
    terminal: _TerminalCapture,
    deadline: float,
    done,
) -> None:
    while time.monotonic() < deadline and not done():
        _read_once(fd, terminal, 0.05)


def _read_for(fd: int, terminal: _TerminalCapture, seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        _read_once(fd, terminal, min(0.03, max(0.0, deadline - time.monotonic())))


def _read_process_to_exit(
    fd: int,
    terminal: _TerminalCapture,
    process: subprocess.Popen[bytes],
    timeout_seconds: float,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        _read_once(fd, terminal, 0.05)
        if process.poll() is not None:
            _read_once(fd, terminal, 0.0)
            return
    raise TimeoutError("Timed out waiting for ReLarn to exit after save command")


def _read_once(fd: int, terminal: _TerminalCapture, timeout: float) -> None:
    readable, _, _ = select.select([fd], [], [], timeout)
    if not readable:
        return
    try:
        data = os.read(fd, 65536)
    except OSError:
        return
    if data:
        terminal.feed(data)


def _state_pending_prompt(state: dict[str, Any] | None) -> dict[str, Any] | None:
    if not state or state.get("adapter") != "relarn_process":
        return None
    pending = state.get("pending_prompt")
    return pending if isinstance(pending, dict) else None


def _prompt_base_save_b64(state: dict[str, Any] | None) -> str | None:
    pending = _state_pending_prompt(state)
    if pending is not None and isinstance(pending.get("base_save_blob_b64"), str):
        return pending["base_save_blob_b64"]
    base_save = _state_save_blob(state)
    if base_save is None:
        return None
    return base64.b64encode(base_save).decode("ascii")


def _pending_trigger_keys(pending_prompt: dict[str, Any]) -> list[str]:
    trigger_keys = pending_prompt.get("trigger_keys")
    if isinstance(trigger_keys, list):
        return [key for key in trigger_keys if isinstance(key, str) and len(key) == 1]
    trigger_key = pending_prompt.get("trigger_key")
    if isinstance(trigger_key, str) and len(trigger_key) == 1:
        return [trigger_key]
    return []


def _keys_to_text(keys: list[bytes]) -> list[str]:
    result: list[str] = []
    for key in keys:
        try:
            decoded = key.decode("ascii")
        except UnicodeDecodeError:
            return []
        if len(decoded) != 1:
            return []
        result.append(decoded)
    return result


def _prompt_answer_from_command(
    normalized_command: str,
    pending_prompt: dict[str, Any] | None,
) -> str | None:
    if pending_prompt is None:
        return None
    if normalized_command.startswith(_PROMPT_COMMAND_PREFIX):
        answer = normalized_command.removeprefix(_PROMPT_COMMAND_PREFIX).strip().lower()
    else:
        answer = normalized_command
    if len(answer) != 1:
        return None
    options = pending_prompt.get("options", [])
    allowed = {str(option.get("key", "")).lower() for option in options if isinstance(option, dict)}
    return answer if answer in allowed else None


def _state_save_blob(state: dict[str, Any] | None) -> bytes | None:
    if not state or state.get("adapter") != "relarn_process":
        return None
    encoded = state.get("save_blob_b64")
    if not isinstance(encoded, str) or not encoded:
        return None
    return base64.b64decode(encoded)


def _command_to_key(command: str) -> bytes | None:
    normalized = command.strip().lower()
    return _COMMAND_KEYS.get(normalized)


def _render_display_lines(
    lines: list[str],
    map_view: MapView,
) -> tuple[str, list[str], dict[str, Any]]:
    width, map_height = _VIEWPORTS[map_view]
    padded = lines + [""] * max(0, _TERMINAL_ROWS - len(lines))
    map_lines = padded[:_MAP_ROWS]
    stats_lines = padded[_STATS_START_ROW:_STATS_END_ROW]
    console_lines = padded[_CONSOLE_START_ROW:]

    if not _is_map_display(map_lines, stats_lines):
        screen = _render_modal_display(padded, width)
        return (
            screen,
            [],
            {
                "map_view": map_view,
                "screen_type": "modal",
                "viewport": {"width": width, "height": map_height},
                "terminal": {"width": _TERMINAL_COLUMNS, "height": _TERMINAL_ROWS},
            },
        )

    player_x, player_y = _find_player(map_lines)
    left = _crop_start(player_x, width, _TERMINAL_COLUMNS)
    top = _crop_start(player_y, map_height, _MAP_ROWS)

    cropped_map = [
        _render_map_line(line[left : left + width])
        for line in map_lines[top : top + map_height]
    ]
    cropped_stats = _wrap_stats_lines(stats_lines, width)
    screen_lines = cropped_map + cropped_stats
    screen = "\n".join(screen_lines).rstrip()

    log = [_clean_log_line(line) for line in console_lines if _clean_log_line(line)]
    return (
        screen,
        log,
        {
            "map_view": map_view,
            "screen_type": "map",
            "viewport": {"width": width, "height": map_height},
            "terminal": {"width": _TERMINAL_COLUMNS, "height": _TERMINAL_ROWS},
            "position": {"x": player_x, "y": player_y} if player_x >= 0 else {},
        },
    )


def _is_map_display(map_lines: list[str], stats_lines: list[str]) -> bool:
    has_player = any("@" in line for line in map_lines)
    has_stats = any(line.strip().startswith(("Spells:", "HP:")) for line in stats_lines)
    return has_player or has_stats


def _render_modal_display(lines: list[str], width: int) -> str:
    visible_lines = _trim_modal_lines(lines)
    rendered: list[str] = []
    for line in visible_lines:
        rendered.extend(_wrap_modal_line(line, width))
    return "\n".join(rendered).rstrip()


def _trim_modal_lines(lines: list[str]) -> list[str]:
    nonempty = [
        line.rstrip()
        for line in lines
        if line.strip() and not _is_modal_ui_hint(line)
    ]
    if not nonempty:
        return []
    min_indent = min(len(line) - len(line.lstrip()) for line in nonempty)
    result: list[str] = []
    for index, line in enumerate(nonempty):
        indent = len(line) - len(line.lstrip())
        if index == 0 or indent >= min_indent + 12:
            result.append(line.strip())
        else:
            result.append(line[min_indent:].rstrip())
    return result


def _is_modal_ui_hint(line: str) -> bool:
    cleaned = " ".join(line.split())
    if not cleaned:
        return False
    return (
        cleaned.startswith("Up:")
        or cleaned.startswith("Down:")
        or cleaned.startswith("Quit:")
        or cleaned.startswith("Select:")
        or cleaned.startswith("To select an individual item")
        or cleaned.startswith("key; CTRL+v escapes")
    )


def _wrap_modal_line(line: str, width: int) -> list[str]:
    if len(line) <= width:
        return [line]

    wrapped: list[str] = []
    remaining = line
    while len(remaining) > width:
        split_at = remaining.rfind(" ", 0, width + 1)
        if split_at <= 0:
            split_at = width
        wrapped.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        wrapped.append(remaining)
    return wrapped


def _clean_log_line(line: str) -> str:
    cleaned = line.strip()
    if not cleaned:
        return ""
    if cleaned.startswith("Welcome to ReLarn") or cleaned.startswith("Welcome back to ReLarn"):
        return ""
    return cleaned


def _render_map_line(line: str) -> str:
    return line.replace(" ", ".")


def _wrap_stats_lines(lines: list[str], width: int) -> list[str]:
    wrapped: list[str] = []
    for line in lines:
        for cleaned in _split_stats_line(_clean_stats_line(line)):
            wrapped.extend(_wrap_words(cleaned.split(), width))
    return wrapped


def _clean_stats_line(line: str) -> str:
    cleaned = " ".join(line.split())
    cleaned = re.sub(r"\(\s+", "(", cleaned)
    cleaned = re.sub(r"\s+\)", ")", cleaned)
    return cleaned


def _split_stats_line(line: str) -> list[str]:
    if not line:
        return []
    if line.startswith("Spells:"):
        return [part for part in re.split(r"\s+(?=Exp:)", line, maxsplit=1) if part]
    if line.startswith("HP:"):
        return [part for part in re.split(r"\s+(?=CON=)", line, maxsplit=1) if part]
    return [line]


def _wrap_words(words: list[str], width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in words:
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= width:
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _detect_prompt(lines: list[str]) -> dict[str, Any] | None:
    picklist_prompt = _detect_picklist_prompt(lines)
    if picklist_prompt is not None:
        return picklist_prompt

    text = " ".join(line.strip() for line in lines[_CONSOLE_START_ROW:] if line.strip())
    if not text:
        return None
    prompt_start = _PROMPT_START_RE.search(text)
    if prompt_start is None:
        return None
    question = text[prompt_start.start() :].strip()
    options = _prompt_options(question)
    if not options:
        return None
    return {"question": question, "options": options}


def _detect_picklist_prompt(lines: list[str]) -> dict[str, Any] | None:
    nonempty = [line.rstrip() for line in lines if line.strip()]
    for index, line in enumerate(nonempty):
        question = line.strip()
        if not question.endswith("?"):
            continue
        options = _picklist_options(nonempty[index + 1 :])
        if options:
            return {"question": question, "options": options}
    return None


def _picklist_options(lines: list[str]) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    for line in lines:
        if _is_modal_ui_hint(line):
            break
        match = _PICKLIST_OPTION_RE.match(line)
        if match is None:
            continue
        key = match.group(1).lower()
        label = _picklist_option_label(match.group(2))
        if key and label and all(existing["key"] != key for existing in options):
            options.append({"key": key, "label": label})
    return options


def _picklist_option_label(text: str) -> str:
    cleaned = " ".join(text.split())
    lowered = cleaned.lower()
    for spell_name in _SPELL_NAMES:
        if lowered.startswith(spell_name):
            return spell_name[:1].upper() + spell_name[1:]
    label = re.split(r"\s{2,}", text.strip(), maxsplit=1)[0]
    cleaned_label = " ".join(label.split())
    if not cleaned_label:
        return ""
    return cleaned_label[:1].upper() + cleaned_label[1:]


def _prompt_options(question: str) -> list[dict[str, str]]:
    matches = list(_PROMPT_OPTION_RE.finditer(question))
    if not matches:
        return _confirm_options(question)

    options: list[dict[str, str]] = []
    for index, match in enumerate(matches):
        key = match.group(1).lower()
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(question)
        phrase = question[match.end() : next_start]
        label = _prompt_option_label(key, phrase)
        if key and all(existing["key"] != key for existing in options):
            options.append({"key": key, "label": label})
    return options


def _confirm_options(question: str) -> list[dict[str, str]]:
    match = _CONFIRM_OPTION_RE.search(question)
    if match is None:
        return []
    options: list[dict[str, str]] = []
    for key in match.group(1).lower():
        if all(existing["key"] != key for existing in options):
            options.append({"key": key, "label": _CONFIRM_LABELS.get(key, key.upper())})
    return options


def _prompt_option_label(key: str, phrase: str) -> str:
    if phrase and phrase[0].isalnum():
        phrase = f"{key}{phrase}"
    stop = _PROMPT_LABEL_STOP_RE.search(phrase)
    if stop is not None:
        phrase = phrase[: stop.start()]
    cleaned = " ".join(phrase.replace(".", " ").split()).strip()
    if not cleaned:
        return key.upper()
    return cleaned[:1].upper() + cleaned[1:]


def _prompt_actions(options: list[dict[str, str]]) -> list[GameAction]:
    return [
        GameAction(
            id=f"prompt_{option['key']}",
            label=option["label"],
            command=f"{_PROMPT_COMMAND_PREFIX}{option['key']}",
        )
        for option in options
        if option.get("key") and option.get("label")
    ]


def _find_player(lines: list[str]) -> tuple[int, int]:
    for y, line in enumerate(lines):
        x = line.find("@")
        if x >= 0:
            return x, y
    return -1, -1


def _crop_start(center: int, width: int, total: int) -> int:
    if width >= total:
        return 0
    return max(0, min(center - width // 2, total - width))
