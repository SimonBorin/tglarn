"""Temporary game adapter used until the ReLarn headless engine is wired."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .models import GameAction, GameResponse, MapView

_MAP_WIDTH = 69
_MAP_HEIGHT = 27
_START_X = 1
_START_Y = 1
_MAX_HP = 32
_AC = 4

_VIEWPORTS: dict[MapView, tuple[int, int]] = {
    "medium": (21, 11),
    "wide": (31, 15),
    "max": (52, 23),
}

AVAILABLE_ACTIONS = (
    ("north", "Move one tile north. Aliases: n, up."),
    ("south", "Move one tile south. Aliases: s, down."),
    ("east", "Move one tile east. Aliases: e, right."),
    ("west", "Move one tile west. Aliases: w, left."),
    ("northwest", "Move one tile northwest. Alias: nw."),
    ("northeast", "Move one tile northeast. Alias: ne."),
    ("southwest", "Move one tile southwest. Alias: sw."),
    ("southeast", "Move one tile southeast. Alias: se."),
    ("wait", "Wait one turn. Alias: ."),
    ("look", "Describe the current area. Alias: l."),
    ("descend", "Go down stairs when standing on >. Aliases: go down, >."),
    ("status", "Show current hero stats. Alias: stats."),
    ("help", "Show available commands and map legend. Alias: ?."),
    ("/menu", "Open the main menu at any time."),
)

_DIRECTIONS = {
    "n": (0, -1),
    "north": (0, -1),
    "up": (0, -1),
    "s": (0, 1),
    "south": (0, 1),
    "down": (0, 1),
    "w": (-1, 0),
    "west": (-1, 0),
    "left": (-1, 0),
    "e": (1, 0),
    "east": (1, 0),
    "right": (1, 0),
    "nw": (-1, -1),
    "northwest": (-1, -1),
    "ne": (1, -1),
    "northeast": (1, -1),
    "sw": (-1, 1),
    "southwest": (-1, 1),
    "se": (1, 1),
    "southeast": (1, 1),
}

_MENU_COMMANDS = {
    "inventory": "Your inventory is empty.",
    "pack_weight": "The stuff you are carrying presently weighs 0 pounds.",
    "wield": "You have no weapon to wield.",
    "wear": "You have no armor to wear.",
    "take_off": "You are not wearing armor or a shield.",
    "drop": "You have nothing to drop.",
    "read": "You have no scrolls to read.",
    "quaff": "You have no potions to quaff.",
    "eat": "You have nothing edible.",
    "teleport": "You do not know how to teleport yet.",
    "spells": "You do not know any spells yet.",
    "cast": "You don't have any spells!",
}


class PlaceholderGameAdapter:
    """Small deterministic dungeon used to validate bot/storage integration."""

    def start(
        self,
        state: dict[str, Any] | None = None,
        map_view: MapView = "wide",
    ) -> GameResponse:
        if not state or state.get("adapter") != "placeholder":
            return _response(
                _new_state(),
                ["A new run begins.", _quick_help()],
                map_view,
            )
        return _response(_normalize_state(state), ["Game loaded."], map_view)

    def restart(self, map_view: MapView = "wide") -> GameResponse:
        return _response(_new_state(), ["A new run begins.", _quick_help()], map_view)

    def apply_command(
        self,
        state: dict[str, Any] | None,
        command: str,
        map_view: MapView = "wide",
    ) -> GameResponse:
        current_state = _normalize_state(state)
        normalized = command.strip().lower()
        if not normalized:
            return _response(current_state, ["Enter a command or open the menu."], map_view)

        if normalized in {"look", "l"}:
            return _response(
                current_state,
                [
                    "You look around the training dungeon.",
                    "Map legend: @ you, # wall, . floor, > stairs.",
                ],
                map_view,
            )

        if normalized in {"help", "?"}:
            return _response(current_state, [_full_help()], map_view)

        if normalized in {"status", "stats"}:
            return _response(current_state, ["You check your condition."], map_view)

        if normalized in {"wait", "."}:
            return _wait(current_state, map_view)

        if normalized in _MENU_COMMANDS:
            return _response(current_state, [_MENU_COMMANDS[normalized]], map_view)

        if normalized in {"descend", "go down", ">"}:
            return _descend(current_state, map_view)

        if normalized not in _DIRECTIONS:
            return _response(
                current_state,
                [f"Unknown command: {command.strip()}.", "Send help to list available commands."],
                map_view,
            )

        dx, dy = _DIRECTIONS[normalized]
        next_x = int(current_state["x"]) + dx
        next_y = int(current_state["y"]) + dy
        if _tile_at(next_x, next_y) == "#":
            return _response(current_state, ["A wall blocks your path."], map_view)

        updated_state = deepcopy(current_state)
        updated_state["x"] = next_x
        updated_state["y"] = next_y
        updated_state["turn"] = int(updated_state["turn"]) + 1

        if _tile_at(next_x, next_y) == ">":
            log = ["You find stairs leading deeper. Send descend to go down."]
        else:
            log = [f"You move {normalized}."]
        return _response(updated_state, log, map_view)


def _wait(state: dict[str, Any], map_view: MapView) -> GameResponse:
    updated_state = deepcopy(state)
    updated_state["turn"] = int(updated_state["turn"]) + 1
    return _response(updated_state, ["You wait one turn."], map_view)


def _descend(state: dict[str, Any], map_view: MapView) -> GameResponse:
    if _tile_at(int(state["x"]), int(state["y"])) != ">":
        return _response(state, ["There are no stairs here."], map_view)

    updated_state = deepcopy(state)
    updated_state["depth"] = int(updated_state.get("depth", 1)) + 1
    updated_state["x"] = _START_X
    updated_state["y"] = _START_Y
    updated_state["turn"] = int(updated_state["turn"]) + 1
    return _response(
        updated_state,
        [f"You descend to dungeon level {updated_state['depth']}."],
        map_view,
    )


def _new_state() -> dict[str, Any]:
    return {
        "adapter": "placeholder",
        "x": _START_X,
        "y": _START_Y,
        "hp": _MAX_HP,
        "max_hp": _MAX_HP,
        "ac": _AC,
        "gold": 0,
        "turn": 0,
        "depth": 1,
    }


def _normalize_state(state: dict[str, Any] | None) -> dict[str, Any]:
    if not state or state.get("adapter") != "placeholder":
        return _new_state()
    normalized = _new_state()
    normalized.update(deepcopy(state))
    return normalized


def _response(state: dict[str, Any], log: list[str], map_view: MapView) -> GameResponse:
    viewport_width, viewport_height = _VIEWPORTS[map_view]
    return GameResponse(
        state=state,
        screen=_render_screen(state, map_view),
        log=log,
        status={
            "hp": state["hp"],
            "max_hp": state["max_hp"],
            "ac": state["ac"],
            "gold": state["gold"],
            "turn": state["turn"],
            "depth": state["depth"],
            "map_view": map_view,
            "viewport": {"width": viewport_width, "height": viewport_height},
            "position": {"x": state["x"], "y": state["y"]},
        },
        actions=_actions_for(state),
    )


def _actions_for(state: dict[str, Any]) -> list[GameAction]:
    if _tile_at(int(state["x"]), int(state["y"])) == ">":
        return [GameAction(id="descend", label="Descend", command="descend")]
    return []


def _render_screen(state: dict[str, Any], map_view: MapView) -> str:
    rows = [list(row) for row in _MAP]
    x = int(state["x"])
    y = int(state["y"])
    rows[y][x] = "@"
    viewport_width, viewport_height = _VIEWPORTS[map_view]
    left, top = _viewport_origin(x, y, viewport_width, viewport_height)
    visible_rows = rows[top : top + viewport_height]
    map_text = "\n".join("".join(row[left : left + viewport_width]) for row in visible_rows)
    return (
        f"{map_text}\n"
        f"DL {state['depth']}  HP {state['hp']}/{state['max_hp']}  AC {state['ac']}  "
        f"Gold {state['gold']}  Turn {state['turn']}"
    )


def _viewport_origin(x: int, y: int, width: int, height: int) -> tuple[int, int]:
    map_width = len(_MAP[0])
    map_height = len(_MAP)
    max_left = max(0, map_width - width)
    max_top = max(0, map_height - height)
    left = min(max(0, x - width // 2), max_left)
    top = min(max(0, y - height // 2), max_top)
    return left, top


def _tile_at(x: int, y: int) -> str:
    if y < 0 or y >= len(_MAP) or x < 0 or x >= len(_MAP[y]):
        return "#"
    return _MAP[y][x]


def _build_map() -> tuple[str, ...]:
    rows = [list("#" * _MAP_WIDTH) for _ in range(_MAP_HEIGHT)]
    for y in range(1, _MAP_HEIGHT - 1):
        for x in range(1, _MAP_WIDTH - 1):
            rows[y][x] = "."

    for wall_x, gaps in {
        12: {3, 9, 16, 23},
        24: {2, 10, 17, 24},
        36: {4, 11, 18, 25},
        48: {3, 12, 19, 24},
        60: {6, 14, 21, 25},
    }.items():
        for y in range(1, _MAP_HEIGHT - 1):
            if y not in gaps:
                rows[y][wall_x] = "#"

    for wall_y, gaps in {
        5: {6, 18, 30, 42, 54},
        10: {4, 16, 28, 40, 52, 64},
        15: {8, 20, 32, 44, 56},
        20: {6, 18, 30, 42, 54, 66},
    }.items():
        for x in range(2, _MAP_WIDTH - 2):
            if x not in gaps:
                rows[wall_y][x] = "#"

    rows[18][46] = ">"
    rows[_MAP_HEIGHT - 3][_MAP_WIDTH - 3] = ">"
    return tuple("".join(row) for row in rows)


def _quick_help() -> str:
    return "Send help to list commands. Use /menu to open the main menu."


def _full_help() -> str:
    actions = "\n".join(f"- {name}: {description}" for name, description in AVAILABLE_ACTIONS)
    return "Map legend: @ you, # wall, . floor, > stairs.\nAvailable actions:\n" + actions


_MAP = _build_map()
