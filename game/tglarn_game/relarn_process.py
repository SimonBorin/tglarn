"""Process-backed adapter for the upstream ReLarn curses game.

This is intentionally a bridge adapter: it drives the original terminal game
through a pseudo-terminal, stores the native savefile as adapter state, and
renders the terminal screen back into Telegram-friendly fixed-width text.
"""

from __future__ import annotations

import base64
import binascii
import fcntl
import os
import re
import select
import signal
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
_MAP_COLUMNS = 67
_MAP_ROWS = 17
_STATS_START_ROW = 17
_STATS_END_ROW = 19
_CONSOLE_START_ROW = 19
_ESCAPE = b"\x1b"
_REDRAW_COMMAND = b"\x0c"
_MAP_SNAPSHOT_COMMAND = b"\x07"
_SAVE_COMMAND = b"S"
_PROMPT_COMMAND_PREFIX = "prompt:"
_NUMBER_COMMAND_PREFIX = "number:"
_MAP_SNAPSHOT_ENV = "TGLARN_MAP_SNAPSHOT"
_TURN_LOG_ENV = "TGLARN_TURN_LOG_PATH"
_SAVE_MODAL_EXIT_PASSES = 4
_MAX_SAVE_BLOB_BYTES = 1024 * 1024

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
_PROMPT_KIND_CHOICE = "choice"
_PROMPT_KIND_DIRECTION = "direction"
_PROMPT_KIND_INDEXED_PICKLIST = "indexed_picklist"
_PROMPT_KIND_INVENTORY = "inventory"
_PROMPT_KIND_INVENTORY_ACTION = "inventory_action"
_PROMPT_KIND_INVOICE_CONFIRM = "invoice_confirm"
_PROMPT_KIND_MULTI_PICKLIST = "multi_picklist"
_PROMPT_KIND_NUMBER = "number_prompt"
_PROMPT_KIND_PICKLIST = "picklist"
_PROMPT_CANCEL_KEY = "cancel"
_PROMPT_MENU_KEY = "menu"
_PROMPT_EXIT_STORE_KEY = "exit_store"
_PROMPT_SYSTEM_KEYS = {_PROMPT_CANCEL_KEY, _PROMPT_MENU_KEY}
_PROMPT_ESCAPE_KEYS = _PROMPT_SYSTEM_KEYS | {_PROMPT_EXIT_STORE_KEY}
_INVENTORY_ACTION_COMMAND_PREFIX = "inv:"
_INVENTORY_ITEM_COMMAND_PREFIX = "invitem:"
_MULTI_PICKLIST_COMMAND_PREFIX = "multipick:"
_MULTI_PICKLIST_DONE_KEY = "done"
_MULTI_PICKLIST_CANCEL_KEY = "cancel"
_PICKLIST_COMMAND_PREFIX = "pick:"
_STORE_PICKLIST_OPTION_RE = re.compile(
    r"^\*?\s*(?P<label>.+?)\s+(?:(?P<bucks>\d+)\s+bucks|\$(?P<dollars>\d+))$"
)
_INDEXED_PICKLIST_UI_RE = re.compile(r"\bSelect:ENTER(?:/SPC)?\b")
_MULTI_PICKLIST_OPTION_RE = re.compile(
    r"^\s*([A-Za-z])\.\s+(?P<selected>\*)?\s*(?P<label>.+?)\s*$"
)
_MENU_OPTION_RE = re.compile(r"^\s*\(([A-Za-z0-9])\)(.+?)\s*$")
_NUMBER_PROMPT_RE = re.compile(
    r"(?P<question>"
    r"(?:Balance:\s*\d+\s+GP\.\s+)?"
    r"(?:"
    r"(?:Deposit|Withdraw)\s+how\s+much\?"
    r"|How\s+much\s+(?:gold\s+do\s+you\s+drop|do\s+you\s+want\s+to\s+pay|do\s+you\s+donate)\?"
    r")"
    r")\s*\[(?P<default>\d+)\]\s*$",
    re.I,
)
_NUMBER_WORDS_UNDER_TWENTY = (
    "Zero",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
    "Eleven",
    "Twelve",
    "Thirteen",
    "Fourteen",
    "Fifteen",
    "Sixteen",
    "Seventeen",
    "Eighteen",
    "Nineteen",
)
_NUMBER_WORDS_TENS = {
    20: "Twenty",
    30: "Thirty",
    40: "Forty",
    50: "Fifty",
    60: "Sixty",
    70: "Seventy",
    80: "Eighty",
    90: "Ninety",
}
_INVENTORY_ACTION_KEYS = {
    "drop": b"d",
    "eat": b"e",
    "quaff": b"q",
    "read": b"r",
    "wear": b"W",
    "wield": b"w",
}
_INVENTORY_EDIBLE_WORDS = ("cookie",)
_INVENTORY_QUAFFABLE_WORDS = ("potion",)
_INVENTORY_READABLE_WORDS = ("book", "scroll")
_INVENTORY_WEARABLE_WORDS = (
    "armor",
    "chain",
    "leather",
    "mail",
    "plate",
    "shield",
)
_INVENTORY_WIELDABLE_WORDS = (
    "amulet",
    "axe",
    "belt",
    "cube",
    "dagger",
    "device",
    "flail",
    "hammer",
    "hand of fear",
    "lance",
    "orb",
    "ring",
    "scarab",
    "slayer",
    "spear",
    "staff",
    "sword",
    "talisman",
    "vorpal",
    "wand",
)
_DIRECTION_PROMPT_OPTIONS = (
    {"key": "y", "label": "NW"},
    {"key": "k", "label": "N"},
    {"key": "u", "label": "NE"},
    {"key": "h", "label": "W"},
    {"key": "l", "label": "E"},
    {"key": "b", "label": "SW"},
    {"key": "j", "label": "S"},
    {"key": "n", "label": "SE"},
)
_DIRECTION_PROMPT_KEYS = {option["key"] for option in _DIRECTION_PROMPT_OPTIONS}
_CONTINUE_PROMPT = "Press ENTER, ESCAPE or SPACE to continue:"
_GAME_OVER_MARKERS = (
    "Alas, you have died.",
    "Final Score:",
    "The End",
    "GAME OVER",
)
_PAGE_EXIT_MARKERS = (
    "press return or escape to exit",
    "press y or return for yes",
)
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
        if _state_game_over(state):
            return _game_over_response(state)
        if _state_save_blob(state) is None:
            return self._run_cycle(state, [], map_view, ["A new run begins."])
        response = self._run_cycle(state, [], map_view, ["Game loaded."])
        pending_prompt = _state_pending_prompt(state)
        if pending_prompt is None:
            return response
        actions = _prompt_actions(
            pending_prompt.get("options", []),
            str(pending_prompt.get("kind", "")),
        )
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
        if _state_game_over(state):
            return _game_over_response(state)
        normalized = command.strip().lower()
        pending_prompt = _state_pending_prompt(state)
        inventory_item = _inventory_item_from_command(normalized, pending_prompt)
        if inventory_item is not None and pending_prompt is not None:
            return self._select_inventory_item(
                state,
                pending_prompt,
                inventory_item,
                map_view,
            )
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

    def _select_inventory_item(
        self,
        state: dict[str, Any] | None,
        pending_prompt: dict[str, Any],
        item_key: str,
        map_view: MapView,
    ) -> GameResponse:
        base_save = pending_prompt.get("base_save_blob_b64")
        trigger_keys = _pending_trigger_keys(pending_prompt)
        item = _inventory_prompt_item(pending_prompt, item_key)
        if not isinstance(base_save, str) or not trigger_keys or item is None:
            response = self.start(state, map_view=map_view)
            return GameResponse(
                state=response.state,
                screen=response.screen,
                log=["That inventory item is no longer available."],
                status=response.status,
                actions=response.actions,
            )

        prompt_state = {
            "adapter": "relarn_process",
            "save_blob_b64": base_save,
        }
        character = _state_character(state)
        if character is not None:
            prompt_state["character"] = character
        viewport_origin = _state_viewport_origin(state, map_view)
        if viewport_origin is not None:
            prompt_state["viewport_origin"] = viewport_origin

        response = self._run_cycle(
            prompt_state,
            [key.encode("ascii") for key in trigger_keys],
            map_view,
            [],
        )
        item_label = str(item.get("item_label", item.get("label", item_key))).strip()
        question = f"Choose action for {item_key}. {_short_inventory_label(item_label)}."
        action_options = item.get("actions", [])
        if not isinstance(action_options, list):
            action_options = []
        action_prompt = {
            "question": question,
            "kind": _PROMPT_KIND_INVENTORY_ACTION,
            "options": action_options,
            "trigger_keys": trigger_keys,
            "base_save_blob_b64": base_save,
        }
        actions = _prompt_actions(
            action_prompt["options"],
            _PROMPT_KIND_INVENTORY_ACTION,
        )
        return GameResponse(
            state=response.state | {"pending_prompt": action_prompt},
            screen=response.screen,
            log=[question],
            status=response.status | {"pending_prompt": action_prompt},
            actions=actions,
        )

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
        character = _state_character(state)
        if character is not None:
            prompt_state["character"] = character
        viewport_origin = _state_viewport_origin(state, map_view)
        if viewport_origin is not None:
            prompt_state["viewport_origin"] = viewport_origin
        replay_keys = []
        if _prompt_replays_trigger(pending_prompt, answer):
            replay_keys.extend(key.encode("ascii") for key in trigger_keys)
        replay_keys.extend(_prompt_answer_keys(answer, pending_prompt))
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
            cycle_result = _execute_relarn_cycle(
                binary_path=binary_path,
                install_root=install_root,
                home=home,
                keys=keys,
                terminal=terminal,
                timeout_seconds=self.timeout_seconds,
                settle_seconds=self.settle_seconds,
            )
            display_lines = cycle_result.display_lines
            display_cells = cycle_result.display_cells
            if not save_file.exists() and cycle_result.game_over:
                save_blob = None
            elif not save_file.exists():
                raise RuntimeError("ReLarn did not write a savefile")
            else:
                save_blob = save_file.read_bytes()

        previous_viewport_origin = _state_viewport_origin(state, map_view)
        screen, log, status = _render_display_lines(
            display_lines,
            map_view,
            display_cells,
            previous_viewport=previous_viewport_origin,
        )
        if cycle_result.map_snapshot is not None:
            status["map_snapshot"] = cycle_result.map_snapshot
        if cycle_result.game_over:
            next_state: dict[str, Any] = {"adapter": "relarn_process", "game_over": True}
            character = _state_character(state)
            if character is not None:
                next_state["character"] = character
            return GameResponse(
                state=next_state,
                screen=screen or "Game over.",
                log=cycle_result.game_over_log or log or ["The run has ended."],
                status=status | {"adapter": "relarn_process", "game_over": True},
                actions=[],
            )

        if save_blob is None:
            raise RuntimeError("ReLarn did not write a savefile")

        prompt = _pending_prompt_from_display(display_lines, keys)
        encoded_save = base64.b64encode(save_blob).decode("ascii")
        next_state: dict[str, Any] = {
            "adapter": "relarn_process",
            "save_blob_b64": encoded_save,
            "save_size": len(save_blob),
        }
        character = _state_character(state)
        if character is not None:
            next_state["character"] = character
        viewport_origin = _next_viewport_origin(status, previous_viewport_origin)
        if viewport_origin is not None:
            next_state["viewport_origin"] = viewport_origin
        actions: list[GameAction] = []
        if prompt is not None and keys:
            base_save_b64 = _prompt_base_save_b64(state)
            trigger_keys = _keys_to_text(keys)
            if base_save_b64 is not None and trigger_keys:
                next_state["save_blob_b64"] = base_save_b64
                next_state["save_size"] = _base64_blob_size(base_save_b64)
                pending_prompt = {
                    "question": prompt["question"],
                    "options": prompt["options"],
                    "kind": prompt.get("kind", _PROMPT_KIND_CHOICE),
                    "trigger_keys": trigger_keys,
                    "base_save_blob_b64": base_save_b64,
                }
                next_state["pending_prompt"] = pending_prompt
                status["pending_prompt"] = pending_prompt
                actions = _prompt_actions(
                    prompt["options"],
                    str(prompt.get("kind", "")),
                )

        return GameResponse(
            state=next_state,
            screen=screen,
            log=_response_log(cycle_result.turn_log, log, fallback_log, status),
            status=status | {"adapter": "relarn_process", "save_size": next_state["save_size"]},
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

    def cells(self) -> list[list[_TerminalCell | None]]:
        rows: list[list[_TerminalCell | None]] = []
        for y in range(self.screen.lines):
            buffer_row = self.screen.buffer[y]
            row: list[_TerminalCell | None] = []
            for x in range(self.screen.columns):
                char = buffer_row.get(x)
                if char is None:
                    row.append(None)
                else:
                    row.append(
                        _TerminalCell(
                            data=char.data,
                            fg=str(char.fg),
                            bg=str(char.bg),
                            bold=bool(char.bold),
                            reverse=bool(char.reverse),
                        )
                    )
            rows.append(row)
        return rows

    def snapshot(self) -> _TerminalSnapshot:
        return _TerminalSnapshot(lines=self.lines(), cells=self.cells())

    def contains(self, text: str) -> bool:
        return any(text in line for line in self.screen.display)


@dataclass(frozen=True, slots=True)
class _TerminalCell:
    data: str
    fg: str
    bg: str
    bold: bool
    reverse: bool


@dataclass(frozen=True, slots=True)
class _TerminalSnapshot:
    lines: list[str]
    cells: list[list[_TerminalCell | None]]


@dataclass(frozen=True, slots=True)
class _RelarnCycleResult:
    display_lines: list[str]
    display_cells: list[list[_TerminalCell | None]] | None = None
    map_snapshot: dict[str, Any] | None = None
    game_over: bool = False
    game_over_log: list[str] | None = None
    turn_log: list[str] | None = None


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
        "show-unrevealed\n"
        "dark-screen\n"
    )


def _response_log(
    turn_log: list[str] | None,
    rendered_log: list[str],
    fallback_log: list[str],
    status: dict[str, Any],
) -> list[str]:
    if turn_log and status.get("screen_type") == "map":
        return turn_log
    return rendered_log or fallback_log


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
) -> _RelarnCycleResult:
    master_fd, slave_fd = os.openpty()
    process: subprocess.Popen[bytes] | None = None
    try:
        try:
            _set_terminal_size(slave_fd, _TERMINAL_ROWS, _TERMINAL_COLUMNS)
            env = os.environ.copy()
            env.update(
                {
                    "HOME": str(home),
                    "USER": "tglarn",
                    "RELARN_INSTALL_ROOT": str(install_root),
                    "TERM": "xterm-256color",
                    _MAP_SNAPSHOT_ENV: str(_map_snapshot_path(home)),
                    _TURN_LOG_ENV: str(_turn_log_path(home)),
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

        if process is None:
            raise RuntimeError("ReLarn process did not start")

        try:
            _read_until(
                master_fd,
                terminal,
                deadline=time.monotonic() + timeout_seconds,
                done=lambda: terminal.contains("Welcome"),
            )
            _truncate_turn_log(_turn_log_path(home))
            for key in keys:
                os.write(master_fd, key)
                _read_for(master_fd, terminal, settle_seconds)
            _read_for(master_fd, terminal, settle_seconds)

            display_snapshot = terminal.snapshot()
            display_lines = display_snapshot.lines
            turn_log = _read_turn_log(_turn_log_path(home))
            if process.poll() is not None:
                _read_once(master_fd, terminal, 0.0)
                snapshot = terminal.snapshot()
                game_over = _is_game_over_display(snapshot.lines)
                if not game_over:
                    raise RuntimeError(f"ReLarn exited early with code {process.returncode}")
                return _RelarnCycleResult(
                    snapshot.lines,
                    display_cells=snapshot.cells,
                    game_over=game_over,
                    game_over_log=(turn_log or _game_over_log_lines(snapshot.lines))
                    if game_over
                    else None,
                    turn_log=turn_log,
                )

            if _is_game_over_display(display_lines):
                game_over_log = turn_log or _game_over_log_lines(display_lines)
                final_snapshot = _finish_game_over_flow(
                    master_fd,
                    terminal,
                    process,
                    timeout_seconds,
                )
                return _RelarnCycleResult(
                    final_snapshot.lines,
                    display_cells=final_snapshot.cells,
                    game_over=True,
                    game_over_log=game_over_log or _game_over_log_lines(final_snapshot.lines),
                    turn_log=turn_log,
                )

            if _should_force_full_redraw(display_lines):
                os.write(master_fd, _REDRAW_COMMAND)
                _read_for(master_fd, terminal, settle_seconds)
                display_snapshot = terminal.snapshot()
                display_lines = display_snapshot.lines

            map_snapshot = None
            if _should_capture_map_snapshot(display_lines):
                map_snapshot = _capture_map_snapshot(master_fd, terminal, home)

            if _should_keep_base_save_for_prompt(display_lines, keys):
                return _RelarnCycleResult(
                    display_lines,
                    display_cells=display_snapshot.cells,
                    map_snapshot=map_snapshot,
                    turn_log=turn_log,
                )

            _close_transient_screens_before_save(
                master_fd,
                terminal,
                process,
                timeout_seconds,
                settle_seconds,
            )
            os.write(master_fd, _SAVE_COMMAND)
            _read_process_to_exit(master_fd, terminal, process, timeout_seconds)
            return _RelarnCycleResult(
                display_lines,
                display_cells=display_snapshot.cells,
                map_snapshot=map_snapshot,
                turn_log=turn_log,
            )
        finally:
            _terminate_process_group(process)
    finally:
        os.close(master_fd)


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return

    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        process.wait(timeout=0.5)
        return

    try:
        process.wait(timeout=0.5)
        return
    except subprocess.TimeoutExpired:
        pass

    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=0.5)


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


def _should_keep_base_save_for_prompt(lines: list[str], keys: list[bytes]) -> bool:
    return bool(keys) and _pending_prompt_from_display(lines, keys) is not None


def _pending_prompt_from_display(
    lines: list[str],
    keys: list[bytes],
) -> dict[str, Any] | None:
    prompt = _detect_prompt(lines)
    if prompt is not None and _prompt_was_answered_by_keys(prompt, keys):
        return None
    return prompt


def _prompt_was_answered_by_keys(prompt: dict[str, Any], keys: list[bytes]) -> bool:
    if prompt.get("kind") != _PROMPT_KIND_DIRECTION or not keys:
        return False
    try:
        last_key = keys[-1].decode("ascii").lower()
    except UnicodeDecodeError:
        return False
    return last_key in _DIRECTION_PROMPT_KEYS


def _close_transient_screens_before_save(
    fd: int,
    terminal: _TerminalCapture,
    process: subprocess.Popen[bytes],
    timeout_seconds: float,
    settle_seconds: float,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    for _ in range(_SAVE_MODAL_EXIT_PASSES):
        if process.poll() is not None:
            return
        exit_key = _modal_exit_key(terminal.lines())
        if exit_key is None:
            return
        os.write(fd, exit_key)
        _read_for(fd, terminal, min(settle_seconds, max(0.0, deadline - time.monotonic())))


def _modal_exit_key(lines: list[str]) -> bytes | None:
    padded = lines + [""] * max(0, _TERMINAL_ROWS - len(lines))
    if _is_map_display(
        padded[:_MAP_ROWS],
        padded[_STATS_START_ROW:_STATS_END_ROW],
    ) and _detect_prompt(padded) is None:
        return None
    return _ESCAPE


def _finish_game_over_flow(
    fd: int,
    terminal: _TerminalCapture,
    process: subprocess.Popen[bytes],
    timeout_seconds: float,
) -> _TerminalSnapshot:
    deadline = time.monotonic() + timeout_seconds
    last_snapshot = terminal.snapshot()
    while time.monotonic() < deadline:
        if process.poll() is not None:
            _read_once(fd, terminal, 0.0)
            return terminal.snapshot()

        last_snapshot = terminal.snapshot()
        os.write(fd, b"\n")
        _read_for(fd, terminal, 0.12)

        current_lines = terminal.lines()
        if not (
            _is_game_over_display(current_lines)
            or _has_continue_prompt(current_lines)
            or _has_page_exit_prompt(current_lines)
        ):
            _read_once(fd, terminal, 0.05)

    return last_snapshot


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


def _turn_log_path(home: Path) -> Path:
    return home / ".relarn" / "tglarn-turn.log"


def _truncate_turn_log(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def _read_turn_log(path: Path) -> list[str]:
    try:
        raw_log = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return _turn_log_lines(raw_log)


def _turn_log_lines(raw_log: str) -> list[str]:
    lines: list[str] = []
    for line in raw_log.splitlines():
        cleaned = _clean_log_line(line)
        if not cleaned or cleaned == _CONTINUE_PROMPT or cleaned == "Saving . . .":
            continue
        lines.append(cleaned)
    return lines


def _map_snapshot_path(home: Path) -> Path:
    return home / ".relarn" / "tglarn-map.tsv"


def _capture_map_snapshot(
    fd: int,
    terminal: _TerminalCapture,
    home: Path,
) -> dict[str, Any] | None:
    snapshot_path = _map_snapshot_path(home)
    snapshot_path.unlink(missing_ok=True)
    os.write(fd, _MAP_SNAPSHOT_COMMAND)

    deadline = time.monotonic() + 0.35
    while time.monotonic() < deadline:
        _read_once(fd, terminal, 0.03)
        snapshot = _read_map_snapshot(snapshot_path)
        if snapshot is not None:
            return snapshot
    return _read_map_snapshot(snapshot_path)


def _should_capture_map_snapshot(lines: list[str]) -> bool:
    padded = lines + [""] * max(0, _TERMINAL_ROWS - len(lines))
    return _is_map_display(
        padded[:_MAP_ROWS],
        padded[_STATS_START_ROW:_STATS_END_ROW],
    )


def _read_map_snapshot(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "TGLARN_MAP_V1":
        return None

    metadata: dict[str, str] = {}
    index = 1
    while index < len(lines) and lines[index] != "glyphs":
        parts = lines[index].split("\t")
        if parts:
            metadata[parts[0]] = "\t".join(parts[1:])
        index += 1
    if index >= len(lines) or lines[index] != "glyphs":
        return None

    width = _coerce_int(metadata.get("width"))
    height = _coerce_int(metadata.get("height"))
    if width is None or height is None or width <= 0 or height <= 0:
        return None

    glyph_start = index + 1
    glyphs = lines[glyph_start : glyph_start + height]
    layers_marker = glyph_start + height
    if layers_marker >= len(lines) or lines[layers_marker] != "layers":
        return None
    layers = lines[layers_marker + 1 : layers_marker + 1 + height]
    if len(glyphs) != height or len(layers) != height:
        return None
    if any(len(row) != width for row in glyphs + layers):
        return None

    player = _parse_snapshot_player(metadata.get("player", ""))
    return {
        "version": 1,
        "width": width,
        "height": height,
        "level": metadata.get("level", "unknown"),
        "player": player,
        "glyphs": glyphs,
        "layers": layers,
    }


def _parse_snapshot_player(value: str) -> dict[str, int]:
    parts = value.split("\t")
    if len(parts) != 2:
        return {}
    x = _coerce_int(parts[0])
    y = _coerce_int(parts[1])
    if x is None or y is None:
        return {}
    return {"x": x, "y": y}


def _state_pending_prompt(state: dict[str, Any] | None) -> dict[str, Any] | None:
    if not state or state.get("adapter") != "relarn_process":
        return None
    pending = state.get("pending_prompt")
    return pending if isinstance(pending, dict) else None


def _state_game_over(state: dict[str, Any] | None) -> bool:
    return bool(state and state.get("adapter") == "relarn_process" and state.get("game_over"))


def _game_over_response(state: dict[str, Any] | None) -> GameResponse:
    return GameResponse(
        state=state or {"adapter": "relarn_process", "game_over": True},
        screen="Game over.",
        log=["This run has ended. Restart the game to create a new character."],
        status={"adapter": "relarn_process", "game_over": True},
        actions=[],
    )


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


def _number_words(value: int) -> str:
    if value < 20:
        return _NUMBER_WORDS_UNDER_TWENTY[value]
    if value < 100:
        tens, remainder = divmod(value, 10)
        words = _NUMBER_WORDS_TENS[tens * 10]
        return words if remainder == 0 else f"{words} {_number_words(remainder)}"
    if value < 1000:
        hundreds, remainder = divmod(value, 100)
        words = f"{_number_words(hundreds)} Hundred"
        return words if remainder == 0 else f"{words} {_number_words(remainder)}"
    thousands, remainder = divmod(value, 1000)
    words = f"{_number_words(thousands)} Thousand"
    return words if remainder == 0 else f"{words} {_number_words(remainder)}"


def _button_label_words(label: str) -> str:
    with_words = re.sub(r"\d+", lambda match: _number_words(int(match.group(0))), label)
    cleaned = re.sub(r"[^A-Za-z ]+", " ", with_words)
    return " ".join(cleaned.split())


def _system_prompt_answer_from_command(normalized_command: str) -> str | None:
    if not normalized_command.startswith(_PROMPT_COMMAND_PREFIX):
        return None
    answer = normalized_command.removeprefix(_PROMPT_COMMAND_PREFIX).strip().lower()
    return answer if answer in _PROMPT_SYSTEM_KEYS else None


def _prompt_answer_from_command(
    normalized_command: str,
    pending_prompt: dict[str, Any] | None,
) -> str | None:
    if pending_prompt is None:
        return None
    system_answer = _system_prompt_answer_from_command(normalized_command)
    if system_answer is not None:
        return system_answer
    if pending_prompt.get("kind") == _PROMPT_KIND_NUMBER:
        return _number_prompt_answer_from_command(normalized_command, pending_prompt)
    if pending_prompt.get("kind") == _PROMPT_KIND_INVENTORY_ACTION:
        if not normalized_command.startswith(_INVENTORY_ACTION_COMMAND_PREFIX):
            return None
        answer = normalized_command.removeprefix(_INVENTORY_ACTION_COMMAND_PREFIX).strip()
        options = pending_prompt.get("options", [])
        allowed = {
            str(option.get("key", ""))
            for option in options
            if isinstance(option, dict)
        }
        return answer if answer in allowed and _inventory_answer_keys(answer) else None
    if pending_prompt.get("kind") == _PROMPT_KIND_MULTI_PICKLIST:
        if not normalized_command.startswith(_MULTI_PICKLIST_COMMAND_PREFIX):
            return None
        answer = normalized_command.removeprefix(_MULTI_PICKLIST_COMMAND_PREFIX).strip()
        if answer in _PROMPT_ESCAPE_KEYS:
            return answer
        options = pending_prompt.get("options", [])
        allowed = {
            str(option.get("key", ""))
            for option in options
            if isinstance(option, dict)
        }
        if answer in allowed and _multi_picklist_answer_keys(answer, pending_prompt):
            return answer
        return None
    if pending_prompt.get("kind") == _PROMPT_KIND_INDEXED_PICKLIST:
        if not normalized_command.startswith(_PICKLIST_COMMAND_PREFIX):
            return None
        answer = normalized_command.removeprefix(_PICKLIST_COMMAND_PREFIX).strip()
        if answer == _PROMPT_EXIT_STORE_KEY:
            return answer
        options = pending_prompt.get("options", [])
        allowed = {
            str(option.get("key", ""))
            for option in options
            if isinstance(option, dict)
        }
        return answer if answer.isdecimal() and answer in allowed else None
    if normalized_command.startswith(_PROMPT_COMMAND_PREFIX):
        answer = normalized_command.removeprefix(_PROMPT_COMMAND_PREFIX).strip().lower()
    elif pending_prompt.get("kind") == _PROMPT_KIND_DIRECTION:
        key = _command_to_key(normalized_command)
        if key is None:
            answer = normalized_command
        else:
            try:
                answer = key.decode("ascii").lower()
            except UnicodeDecodeError:
                return None
    else:
        answer = normalized_command
    if len(answer) != 1:
        return None
    options = pending_prompt.get("options", [])
    allowed = {str(option.get("key", "")).lower() for option in options if isinstance(option, dict)}
    return answer if answer in allowed else None


def _number_prompt_answer_from_command(
    normalized_command: str,
    pending_prompt: dict[str, Any],
) -> str | None:
    if normalized_command.startswith(_NUMBER_COMMAND_PREFIX):
        answer = normalized_command.removeprefix(_NUMBER_COMMAND_PREFIX).strip().lower()
    else:
        answer = normalized_command

    if answer == "max":
        return answer
    if not answer.isdecimal():
        return None
    return answer


def _inventory_item_from_command(
    normalized_command: str,
    pending_prompt: dict[str, Any] | None,
) -> str | None:
    if pending_prompt is None or pending_prompt.get("kind") != _PROMPT_KIND_INVENTORY:
        return None
    if not normalized_command.startswith(_INVENTORY_ITEM_COMMAND_PREFIX):
        return None
    item_key = normalized_command.removeprefix(_INVENTORY_ITEM_COMMAND_PREFIX).strip()
    return item_key if _inventory_prompt_item(pending_prompt, item_key) is not None else None


def _inventory_prompt_item(
    pending_prompt: dict[str, Any],
    item_key: str,
) -> dict[str, Any] | None:
    options = pending_prompt.get("options", [])
    if not isinstance(options, list):
        return None
    for option in options:
        if not isinstance(option, dict):
            continue
        if str(option.get("key", "")).lower() == item_key:
            return option
    return None


def _prompt_answer_keys(answer: str, pending_prompt: dict[str, Any]) -> list[bytes]:
    if pending_prompt.get("kind") == _PROMPT_KIND_MULTI_PICKLIST:
        return _multi_picklist_answer_keys(answer, pending_prompt)
    if answer in _PROMPT_ESCAPE_KEYS:
        return [_ESCAPE]
    if pending_prompt.get("kind") == _PROMPT_KIND_NUMBER:
        return _number_answer_keys(answer, pending_prompt)
    if pending_prompt.get("kind") == _PROMPT_KIND_INVENTORY_ACTION:
        return _inventory_answer_keys(answer)
    if pending_prompt.get("kind") == _PROMPT_KIND_INDEXED_PICKLIST:
        index = int(answer)
        return [b"j"] * index + [b"\n"]

    keys = [answer.encode("ascii")]
    if _prompt_requires_enter(pending_prompt):
        keys.append(b"\n")
    return keys


def _prompt_replays_trigger(pending_prompt: dict[str, Any], answer: str) -> bool:
    if answer in _PROMPT_ESCAPE_KEYS:
        return True
    return pending_prompt.get("kind") != _PROMPT_KIND_INVENTORY_ACTION


def _inventory_answer_keys(answer: str) -> list[bytes]:
    action, separator, item_key = answer.partition(":")
    if not separator or len(item_key) != 1:
        return []
    action_key = _INVENTORY_ACTION_KEYS.get(action)
    if action_key is None:
        return []
    return [action_key, item_key.encode("ascii")]


def _multi_picklist_answer_keys(answer: str, pending_prompt: dict[str, Any]) -> list[bytes]:
    if answer in {_PROMPT_CANCEL_KEY, _PROMPT_MENU_KEY, _PROMPT_EXIT_STORE_KEY}:
        return _multi_picklist_clear_selection_keys(pending_prompt)
    if answer in {_MULTI_PICKLIST_DONE_KEY, _MULTI_PICKLIST_CANCEL_KEY}:
        return [_ESCAPE]
    if len(answer) != 1:
        return []
    try:
        return [answer.encode("ascii"), b"\n"]
    except UnicodeEncodeError:
        return []


def _multi_picklist_clear_selection_keys(pending_prompt: dict[str, Any]) -> list[bytes]:
    keys: list[bytes] = []
    options = pending_prompt.get("options", [])
    if isinstance(options, list):
        for option in options:
            if not isinstance(option, dict) or not option.get("selected"):
                continue
            item_key = str(option.get("key", ""))
            if len(item_key) == 1:
                keys.extend([item_key.encode("ascii"), b"\n"])
    keys.append(_ESCAPE)
    return keys


def _number_answer_keys(answer: str, pending_prompt: dict[str, Any]) -> list[bytes]:
    if answer == "max":
        value = str(pending_prompt.get("default", "0"))
    else:
        value = answer
    return [value.encode("ascii"), b"\n"]


def _prompt_requires_enter(pending_prompt: dict[str, Any]) -> bool:
    return pending_prompt.get("kind") == _PROMPT_KIND_PICKLIST


def _state_save_blob(state: dict[str, Any] | None) -> bytes | None:
    if not state or state.get("adapter") != "relarn_process":
        return None
    encoded = state.get("save_blob_b64")
    if not isinstance(encoded, str) or not encoded:
        return None
    try:
        save_blob = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError) as exc:
        raise ValueError("Invalid ReLarn save blob encoding") from exc
    if len(save_blob) > _MAX_SAVE_BLOB_BYTES:
        raise ValueError("ReLarn save blob exceeds the maximum allowed size")
    return save_blob


def _base64_blob_size(encoded: str) -> int:
    try:
        return len(base64.b64decode(encoded.encode("ascii"), validate=True))
    except (binascii.Error, UnicodeEncodeError):
        return 0


def _state_viewport_origin(
    state: dict[str, Any] | None,
    map_view: MapView,
) -> dict[str, Any] | None:
    if not state or state.get("adapter") != "relarn_process":
        return None
    viewport = state.get("viewport_origin")
    if not isinstance(viewport, dict):
        return None
    if viewport.get("map_view") != map_view:
        return None
    return viewport


def _next_viewport_origin(
    status: dict[str, Any],
    previous_viewport: dict[str, Any] | None,
) -> dict[str, Any] | None:
    viewport = status.get("viewport_origin")
    return viewport if isinstance(viewport, dict) else previous_viewport


def _command_to_key(command: str) -> bytes | None:
    normalized = command.strip().lower()
    return _COMMAND_KEYS.get(normalized)


def _render_display_lines(
    lines: list[str],
    map_view: MapView,
    cells: list[list[_TerminalCell | None]] | None = None,
    previous_viewport: dict[str, Any] | None = None,
) -> tuple[str, list[str], dict[str, Any]]:
    width, map_height = _VIEWPORTS[map_view]
    padded = lines + [""] * max(0, _TERMINAL_ROWS - len(lines))
    map_lines = [
        line[:_MAP_COLUMNS].ljust(_MAP_COLUMNS)
        for line in padded[:_MAP_ROWS]
    ]
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
                "map": {"width": _MAP_COLUMNS, "height": _MAP_ROWS},
            },
        )

    player_x, player_y = _find_player(map_lines)
    level = _level_id_from_stats(stats_lines)
    left, top = _viewport_origin_for_player(
        player_x,
        player_y,
        width,
        map_height,
        map_view,
        level,
        previous_viewport,
    )

    cropped_map: list[str] = []
    for row_index, line in enumerate(map_lines[top : top + map_height], start=top):
        row_cells = cells[row_index][left : left + width] if cells is not None else None
        cropped_map.append(_render_map_line(line[left : left + width], row_cells))
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
            "viewport_origin": {
                "left": left,
                "top": top,
                "level": level,
                "map_view": map_view,
            },
            "terminal": {"width": _TERMINAL_COLUMNS, "height": _TERMINAL_ROWS},
            "map": {"width": _MAP_COLUMNS, "height": _MAP_ROWS},
            "level": level,
            "position": {"x": player_x, "y": player_y} if player_x >= 0 else {},
        },
    )


def _level_id_from_stats(stats_lines: list[str]) -> str:
    matches = re.findall(r"\bLV:\s*([A-Za-z0-9]+)", " ".join(stats_lines))
    return matches[-1] if matches else "unknown"


def _viewport_origin_for_player(
    player_x: int,
    player_y: int,
    width: int,
    height: int,
    map_view: MapView,
    level: str,
    previous_viewport: dict[str, Any] | None,
) -> tuple[int, int]:
    if player_x < 0:
        return 0, 0
    previous_left: int | None = None
    previous_top: int | None = None
    if (
        previous_viewport is not None
        and previous_viewport.get("level") == level
        and previous_viewport.get("map_view") == map_view
    ):
        previous_left = _coerce_int(previous_viewport.get("left"))
        previous_top = _coerce_int(previous_viewport.get("top"))
    return (
        _pan_start(player_x, width, _MAP_COLUMNS, previous_left),
        _pan_start(player_y, height, _MAP_ROWS, previous_top),
    )


def _pan_start(
    center: int,
    size: int,
    total: int,
    previous_start: int | None,
) -> int:
    if size >= total:
        return 0
    if previous_start is None:
        return _crop_start(center, size, total)

    start = max(0, min(previous_start, total - size))
    margin = 2
    if center < start + margin:
        start = center - margin
    elif center >= start + size - margin:
        start = center - size + margin + 1
    return max(0, min(start, total - size))


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    return None


def _should_force_full_redraw(lines: list[str]) -> bool:
    padded = lines + [""] * max(0, _TERMINAL_ROWS - len(lines))
    return (
        _is_map_display(
            padded[:_MAP_ROWS],
            padded[_STATS_START_ROW:_STATS_END_ROW],
        )
        and _detect_prompt(padded) is None
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
        or (
            "or return for yes" in cleaned.lower()
            and "or escape for no" in cleaned.lower()
        )
        or cleaned.lower().startswith("---- press return or escape to exit")
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


def _game_over_log_lines(lines: list[str]) -> list[str]:
    padded = lines + [""] * max(0, _TERMINAL_ROWS - len(lines))
    if _is_map_display(
        padded[:_MAP_ROWS],
        padded[_STATS_START_ROW:_STATS_END_ROW],
    ):
        source = padded[_CONSOLE_START_ROW:]
    else:
        source = padded

    result: list[str] = []
    for line in source:
        cleaned = _clean_log_line(line)
        if not cleaned or cleaned == _CONTINUE_PROMPT:
            continue
        result.append(cleaned)
    return result


def _render_map_line(line: str, cells: list[_TerminalCell | None] | None = None) -> str:
    rendered: list[str] = []
    for index, char in enumerate(line):
        if char != " ":
            rendered.append(char)
            continue
        cell = cells[index] if cells is not None and index < len(cells) else None
        rendered.append(" " if _is_unrevealed_space(cell) else ".")
    return "".join(rendered)


def _is_unrevealed_space(cell: _TerminalCell | None) -> bool:
    if cell is None:
        return False
    return (
        cell.data == " "
        and (
            cell.fg != "default"
            or cell.bg != "default"
            or cell.bold
            or cell.reverse
        )
    )


def _screen_text(lines: list[str]) -> str:
    return "\n".join(line.rstrip() for line in lines)


def _is_game_over_display(lines: list[str]) -> bool:
    text = _screen_text(lines)
    return any(marker in text for marker in _GAME_OVER_MARKERS)


def _has_continue_prompt(lines: list[str]) -> bool:
    return _CONTINUE_PROMPT in _screen_text(lines)


def _has_page_exit_prompt(lines: list[str]) -> bool:
    text = _screen_text(lines).lower()
    return any(marker in text for marker in _PAGE_EXIT_MARKERS)


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
    indexed_picklist_prompt = _detect_indexed_picklist_prompt(lines)
    if indexed_picklist_prompt is not None:
        return indexed_picklist_prompt
    inventory_prompt = _detect_inventory_prompt(lines)
    if inventory_prompt is not None:
        return inventory_prompt
    menu_prompt = _detect_parenthesized_menu_prompt(lines)
    if menu_prompt is not None:
        return menu_prompt
    invoice_prompt = _detect_invoice_confirm_prompt(lines)
    if invoice_prompt is not None:
        return invoice_prompt
    page_confirm_prompt = _detect_showpages_confirm_prompt(lines)
    if page_confirm_prompt is not None:
        return page_confirm_prompt

    text = " ".join(line.strip() for line in lines[_CONSOLE_START_ROW:] if line.strip())
    if not text:
        return None
    if "In what direction?" in text:
        return {
            "question": "In what direction?",
            "kind": _PROMPT_KIND_DIRECTION,
            "options": list(_DIRECTION_PROMPT_OPTIONS),
        }
    number_prompt = _detect_number_prompt(text)
    if number_prompt is not None:
        return number_prompt
    prompt_start = _PROMPT_START_RE.search(text)
    if prompt_start is None:
        return None
    question = text[prompt_start.start() :].strip()
    options = _prompt_options(question)
    if not options:
        return None
    if _has_echoed_prompt_answer(question, options):
        return None
    return {"question": question, "kind": _PROMPT_KIND_CHOICE, "options": options}


def _detect_picklist_prompt(lines: list[str]) -> dict[str, Any] | None:
    nonempty = [line.rstrip() for line in lines if line.strip()]
    multi = _is_multi_picklist_screen(nonempty)
    for index, line in enumerate(nonempty):
        question = line.strip()
        if not question.endswith("?"):
            continue
        if multi:
            options = _multi_picklist_options(nonempty[index + 1 :])
        else:
            options = _picklist_options(nonempty[index + 1 :])
        if options:
            kind = _PROMPT_KIND_MULTI_PICKLIST if multi else _PROMPT_KIND_PICKLIST
            return {"question": question, "kind": kind, "options": options}
    return None


def _detect_indexed_picklist_prompt(lines: list[str]) -> dict[str, Any] | None:
    nonempty = [
        line.strip()
        for line in lines
        if line.strip() and not _is_modal_ui_hint(line)
    ]
    if _is_indexed_store_screen(nonempty):
        options = _indexed_store_options(nonempty)
        if not options:
            return None
        return {
            "question": "Choose an item.",
            "kind": _PROMPT_KIND_INDEXED_PICKLIST,
            "options": options + [_store_exit_option()],
            "store": True,
        }

    generic_prompt = _detect_generic_indexed_picklist_prompt(lines)
    if generic_prompt is not None:
        return generic_prompt
    return None


def _indexed_store_options(lines: list[str]) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    for line in lines:
        match = _STORE_PICKLIST_OPTION_RE.match(line)
        if match is None:
            continue
        label = " ".join(match.group("label").split())
        if label.lower().startswith("your gold"):
            continue
        price = match.group("bucks") or match.group("dollars")
        unit = "bucks" if match.group("bucks") is not None else "gold"
        options.append(
            {
                "key": str(len(options)),
                "label": f"{_button_label_words(label)} {_number_words(int(price))} {unit.title()}",
            }
        )
    return options


def _detect_generic_indexed_picklist_prompt(lines: list[str]) -> dict[str, Any] | None:
    if not _is_indexed_picker_screen(lines) or _is_display_only_picklist(lines):
        return None

    nonempty = [
        line.strip()
        for line in lines
        if line.strip() and not _is_modal_ui_hint(line)
    ]
    question_index = _indexed_picklist_heading_index(nonempty)
    if question_index is None:
        return None

    options: list[dict[str, str]] = []
    for line in nonempty[question_index + 1 :]:
        label = _generic_indexed_picklist_label(line)
        if not label:
            continue
        options.append({"key": str(len(options)), "label": _button_label_words(label)})

    if not options:
        return None
    return {
        "question": nonempty[question_index],
        "kind": _PROMPT_KIND_INDEXED_PICKLIST,
        "options": options,
    }


def _is_indexed_store_screen(lines: list[str]) -> bool:
    return any("Dealer McDope's Pad" in line for line in lines) or any(
        "Larn Thrift Shoppe" in line for line in lines
    )


def _is_indexed_picker_screen(lines: list[str]) -> bool:
    return any(_INDEXED_PICKLIST_UI_RE.search(line) for line in lines)


def _is_display_only_picklist(lines: list[str]) -> bool:
    return any("Discoveries To Date:" in line for line in lines)


def _indexed_picklist_heading_index(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if line.endswith("?") or line.endswith(":"):
            return index
    return None


def _generic_indexed_picklist_label(line: str) -> str:
    label = " ".join(line.split())
    if not label:
        return ""
    if _PICKLIST_OPTION_RE.match(label) or _MENU_OPTION_RE.match(label):
        return ""
    if label.endswith(":") or label.startswith("Gold:"):
        return ""
    return label


def _detect_inventory_prompt(lines: list[str]) -> dict[str, Any] | None:
    nonempty = [
        line.strip()
        for line in lines
        if line.strip() and not _is_modal_ui_hint(line)
    ]
    if not nonempty or nonempty[0] != "Inventory":
        return None

    items = _inventory_items(nonempty[1:])
    options = _inventory_item_options(items)
    if not options:
        return None
    return {
        "question": "Choose an inventory item.",
        "kind": _PROMPT_KIND_INVENTORY,
        "options": options,
    }


def _detect_parenthesized_menu_prompt(lines: list[str]) -> dict[str, Any] | None:
    nonempty = [
        line.strip()
        for line in lines
        if line.strip() and not _is_modal_ui_hint(line)
    ]
    if not any("Bank of Larn" in line for line in nonempty):
        return None

    options: list[dict[str, str]] = []
    for line in nonempty:
        match = _MENU_OPTION_RE.match(line)
        if match is None:
            continue
        key = match.group(1).lower()
        label = _menu_option_label(key, match.group(2))
        if key and label and all(existing["key"] != key for existing in options):
            options.append({"key": key, "label": label})

    if not options:
        return None
    return {
        "question": "Choose a bank action.",
        "kind": _PROMPT_KIND_PICKLIST,
        "options": options,
    }


def _detect_showpages_confirm_prompt(lines: list[str]) -> dict[str, Any] | None:
    text = _screen_text(lines).lower()
    if "or return for yes" not in text or "or escape for no" not in text:
        return None

    nonempty = [line.strip() for line in lines if line.strip()]
    for index, line in enumerate(nonempty):
        lowered = line.lower()
        if "or return for yes" not in lowered or "or escape for no" not in lowered:
            continue
        for candidate in reversed(nonempty[:index]):
            if candidate.endswith("?"):
                return {
                    "question": candidate,
                    "kind": _PROMPT_KIND_CHOICE,
                    "options": _yes_no_options(),
                }
    return {
        "question": "Confirm?",
        "kind": _PROMPT_KIND_CHOICE,
        "options": _yes_no_options(),
    }


def _detect_invoice_confirm_prompt(lines: list[str]) -> dict[str, Any] | None:
    text = _screen_text(lines).lower()
    if (
        "you are selling the following items:" not in text
        or "our offer is" not in text
        or "continue with sale?" not in text
        or "or return for yes" not in text
        or "or escape for no" not in text
    ):
        return None
    return {
        "question": "Continue with sale?",
        "kind": _PROMPT_KIND_INVOICE_CONFIRM,
        "options": _invoice_confirm_options(),
    }


def _detect_number_prompt(text: str) -> dict[str, Any] | None:
    match = _NUMBER_PROMPT_RE.search(text)
    if match is None:
        return None
    default_value = int(match.group("default"))
    question = " ".join(match.group("question").split())
    return {
        "question": question,
        "kind": _PROMPT_KIND_NUMBER,
        "default": default_value,
        "max": default_value,
        "options": _number_prompt_options(default_value),
    }


def _inventory_items(lines: list[str]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for line in lines:
        if line.startswith("Gold:"):
            continue
        match = _PICKLIST_OPTION_RE.match(line)
        if match is None:
            continue
        items.append(
            {
                "key": match.group(1).lower(),
                "label": " ".join(match.group(2).split()),
            }
        )
    return items


def _inventory_item_options(items: list[dict[str, str]]) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for item in items:
        actions = _inventory_action_options(item)
        if not actions:
            continue
        key = item["key"]
        label = item["label"]
        options.append(
            {
                "key": key,
                "label": f"{key} {_button_label_words(_short_inventory_label(label))}",
                "item_label": label,
                "actions": actions,
            }
        )
    return options


def _is_multi_picklist_screen(lines: list[str]) -> bool:
    return any("Select:ENTER/SPC" in line for line in lines)


def _multi_picklist_options(lines: list[str]) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    selected_count = 0
    for line in lines:
        if _is_modal_ui_hint(line):
            break
        match = _MULTI_PICKLIST_OPTION_RE.match(line)
        if match is None:
            continue
        key = match.group(1).lower()
        label = _picklist_option_label(match.group("label"))
        selected = match.group("selected") is not None
        if selected:
            selected_count += 1
            label = f"Selected {label}"
        if key and label and all(existing["key"] != key for existing in options):
            options.append({"key": key, "label": label, "selected": selected})

    if not options:
        return []
    if selected_count:
        options.append({"key": _MULTI_PICKLIST_DONE_KEY, "label": "Finish sale"})
    else:
        options.append(_store_exit_option())
    if selected_count:
        options.append(_store_exit_option())
    return options


def _inventory_action_options(item: dict[str, str]) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    key = item["key"]
    label = item["label"]
    lowered = label.lower()
    wearable = _contains_any(lowered, _INVENTORY_WEARABLE_WORDS)
    if _contains_any(lowered, _INVENTORY_QUAFFABLE_WORDS):
        options.append(_inventory_action_option("quaff", key))
    if _contains_any(lowered, _INVENTORY_READABLE_WORDS):
        options.append(_inventory_action_option("read", key))
    if _contains_any(lowered, _INVENTORY_EDIBLE_WORDS):
        options.append(_inventory_action_option("eat", key))
    if wearable:
        options.append(_inventory_action_option("wear", key))
    elif _contains_any(lowered, _INVENTORY_WIELDABLE_WORDS):
        options.append(_inventory_action_option("wield", key))
    options.append(_inventory_action_option("drop", key))
    return options


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _inventory_action_option(action: str, item_key: str) -> dict[str, str]:
    return {
        "key": f"{action}:{item_key}",
        "label": _inventory_action_label(action),
    }


def _inventory_action_label(action: str) -> str:
    return {
        "drop": "Drop",
        "eat": "Eat",
        "quaff": "Quaff",
        "read": "Read",
        "wear": "Wear",
        "wield": "Wield",
    }[action]


def _short_inventory_label(label: str) -> str:
    lowered = label.lower()
    for article in ("a ", "an ", "the ", "some "):
        if lowered.startswith(article):
            return label[len(article) :]
    return label


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


def _menu_option_label(key: str, text: str) -> str:
    cleaned = " ".join(f"{key}{text}".split())
    return cleaned[:1].upper() + cleaned[1:] if cleaned else key.upper()


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


def _yes_no_options() -> list[dict[str, str]]:
    return [
        {"key": "y", "label": _CONFIRM_LABELS["y"]},
        {"key": "n", "label": _CONFIRM_LABELS["n"]},
    ]


def _invoice_confirm_options() -> list[dict[str, str]]:
    return [
        {"key": "y", "label": "Confirm sale"},
        {"key": "n", "label": "Decline"},
    ]


def _store_exit_option() -> dict[str, str]:
    return {"key": _PROMPT_EXIT_STORE_KEY, "label": "Exit Store"}


def _number_prompt_options(default_value: int) -> list[dict[str, str]]:
    return [
        {"key": "0", "label": "Zero"},
        {"key": "100", "label": "One Hundred"},
        {"key": "500", "label": "Five Hundred"},
        {"key": "1000", "label": "One Thousand"},
        {"key": "max", "label": "Maximum"},
    ]


def _has_echoed_prompt_answer(question: str, options: list[dict[str, str]]) -> bool:
    allowed = {option["key"] for option in options if option.get("key")}
    answer = re.search(r"\s+([A-Za-z0-9])\s*$", question)
    if answer is not None and answer.group(1).lower() in allowed:
        return True
    for answer in re.finditer(r"(?:\?|\[[A-Za-z0-9]+\])\s+([A-Za-z0-9])(?:\s|$)", question):
        if answer.group(1).lower() in allowed:
            return True
    return False


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


def _prompt_actions(options: list[dict[str, str]], kind: str = "") -> list[GameAction]:
    actions: list[GameAction] = []
    if kind == _PROMPT_KIND_DIRECTION:
        return _system_prompt_actions()
    if kind == _PROMPT_KIND_INVENTORY:
        command_prefix = _INVENTORY_ITEM_COMMAND_PREFIX
    elif kind == _PROMPT_KIND_INVENTORY_ACTION:
        command_prefix = _INVENTORY_ACTION_COMMAND_PREFIX
    elif kind == _PROMPT_KIND_MULTI_PICKLIST:
        command_prefix = _MULTI_PICKLIST_COMMAND_PREFIX
    elif kind == _PROMPT_KIND_INDEXED_PICKLIST:
        command_prefix = _PICKLIST_COMMAND_PREFIX
    elif kind == _PROMPT_KIND_NUMBER:
        command_prefix = _NUMBER_COMMAND_PREFIX
    else:
        command_prefix = _PROMPT_COMMAND_PREFIX

    for option in options:
        if not option.get("key") or not option.get("label"):
            continue
        actions.append(
            GameAction(
                id=f"prompt_{option['key']}",
                label=option["label"],
                command=f"{command_prefix}{option['key']}",
            )
        )
    actions.extend(_system_prompt_actions())
    return actions


def _system_prompt_actions() -> list[GameAction]:
    return [
        GameAction(
            id=f"prompt_{_PROMPT_CANCEL_KEY}",
            label="Cancel",
            command=f"{_PROMPT_COMMAND_PREFIX}{_PROMPT_CANCEL_KEY}",
        ),
        GameAction(
            id=f"prompt_{_PROMPT_MENU_KEY}",
            label="Main Menu",
            command=f"{_PROMPT_COMMAND_PREFIX}{_PROMPT_MENU_KEY}",
        ),
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
