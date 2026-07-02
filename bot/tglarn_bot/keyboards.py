"""Inline keyboards for the Telegram chat UI."""

import re

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from tglarn_game import GameAction, GameResponse

CHARACTER_CLASSES = (
    ("Ogre", "ogre"),
    ("Wizard", "wizard"),
    ("Klingon", "klingon"),
    ("Elf", "elf"),
    ("Rogue", "rogue"),
    ("Geek", "geek"),
    ("Dwarf", "dwarf"),
    ("Rambo", "rambo"),
)
CHARACTER_CLASS_BY_ID = {class_id: label for label, class_id in CHARACTER_CLASSES}
CHARACTER_GENDERS = (
    ("Male", "male"),
    ("Female", "female"),
    ("Nonbinary", "nonbinary"),
)
CHARACTER_GENDER_BY_ID = {gender_id: label for label, gender_id in CHARACTER_GENDERS}
_BUTTON_TEXT_REPLACEMENTS = {
    "0": "Zero",
    "100": "One Hundred",
    "500": "Five Hundred",
    "1000": "One Thousand",
}


class CallbackData:
    START_GAME = "menu:start_game"
    MAIN_MENU = "menu:main"
    ABOUT = "menu:about"
    LEGEND = "menu:legend"
    RULES = "menu:rules"
    RULES_CONTROLS = "rules:controls"
    RULES_MECHANICS = "rules:mechanics"
    REPOSITORY = "menu:repository"
    MAP_VIEW = "menu:map_view"
    RESTART_REQUEST = "restart:request"
    RESTART_CONFIRM = "restart:confirm"
    RESTART_CANCEL = "restart:cancel"
    CHARACTER_INTRO = "character:intro"
    CHARACTER_CLASS_PREFIX = "character:class:"
    CHARACTER_GENDER_PREFIX = "character:gender:"
    VIEW_MEDIUM = "view:medium"
    VIEW_WIDE = "view:wide"
    VIEW_MAX = "view:max"
    GAME_PREFIX = "game:"
    GAME_MENU = "game_menu:open"
    GAME_LEGEND = "game_menu:legend"
    BACK_TO_GAME = "game_menu:back"
    SPELL_MENU = "spell:open"


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Resume Game", callback_data=CallbackData.START_GAME)],
            [InlineKeyboardButton(text="Restart Game", callback_data=CallbackData.RESTART_REQUEST)],
            [InlineKeyboardButton(text="Rules", callback_data=CallbackData.RULES)],
            [InlineKeyboardButton(text="Legend", callback_data=CallbackData.LEGEND)],
            [InlineKeyboardButton(text="Display Size", callback_data=CallbackData.MAP_VIEW)],
            [InlineKeyboardButton(text="About", callback_data=CallbackData.ABOUT)],
            [InlineKeyboardButton(text="Repository", callback_data=CallbackData.REPOSITORY)],
        ]
    )


def intro_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Play Game",
                    callback_data=CallbackData.CHARACTER_INTRO,
                )
            ],
            [InlineKeyboardButton(text="Main Menu", callback_data=CallbackData.MAIN_MENU)],
        ]
    )


def character_class_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for index in range(0, len(CHARACTER_CLASSES), 2):
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"{CallbackData.CHARACTER_CLASS_PREFIX}{class_id}",
                )
                for label, class_id in CHARACTER_CLASSES[index : index + 2]
            ]
        )
    rows.append([InlineKeyboardButton(text="Main Menu", callback_data=CallbackData.MAIN_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def character_gender_keyboard(class_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"{CallbackData.CHARACTER_GENDER_PREFIX}{class_id}:{gender_id}",
                )
            ]
            for label, gender_id in CHARACTER_GENDERS
        ]
        + [
            [InlineKeyboardButton(text="Back", callback_data=CallbackData.CHARACTER_INTRO)],
            [InlineKeyboardButton(text="Main Menu", callback_data=CallbackData.MAIN_MENU)],
        ]
    )


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Main Menu", callback_data=CallbackData.MAIN_MENU)],
        ]
    )


def rules_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Controls", callback_data=CallbackData.RULES_CONTROLS)],
            [
                InlineKeyboardButton(
                    text="Game Mechanics",
                    callback_data=CallbackData.RULES_MECHANICS,
                )
            ],
            [InlineKeyboardButton(text="Main Menu", callback_data=CallbackData.MAIN_MENU)],
        ]
    )


def rules_detail_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Rules", callback_data=CallbackData.RULES)],
            [InlineKeyboardButton(text="Main Menu", callback_data=CallbackData.MAIN_MENU)],
        ]
    )


def restart_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Restart", callback_data=CallbackData.RESTART_CONFIRM)],
            [InlineKeyboardButton(text="Cancel", callback_data=CallbackData.RESTART_CANCEL)],
        ]
    )


def map_view_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Medium", callback_data=CallbackData.VIEW_MEDIUM),
                InlineKeyboardButton(text="Wide", callback_data=CallbackData.VIEW_WIDE),
            ],
            [InlineKeyboardButton(text="Max Size", callback_data=CallbackData.VIEW_MAX)],
            [InlineKeyboardButton(text="Main Menu", callback_data=CallbackData.MAIN_MENU)],
        ]
    )


def repository_keyboard(repository_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Open Repository", url=repository_url)],
            [InlineKeyboardButton(text="Main Menu", callback_data=CallbackData.MAIN_MENU)],
        ]
    )


def game_keyboard(response: GameResponse) -> InlineKeyboardMarkup:
    if response.status.get("game_over"):
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Main Menu", callback_data=CallbackData.MAIN_MENU)],
                [
                    InlineKeyboardButton(
                        text="Restart Game",
                        callback_data=CallbackData.RESTART_REQUEST,
                    )
                ],
            ]
        )

    context_actions = [action for action in response.actions if action.group == "context"]
    if not context_actions:
        context_actions = _pending_prompt_actions(response.status.get("pending_prompt"))
    if response.status.get("screen_type") == "modal":
        return InlineKeyboardMarkup(inline_keyboard=_modal_action_rows(context_actions))

    inline_keyboard = [
        [
            _game_button("NW", "nw"),
            _game_button("N", "north"),
            _game_button("NE", "ne"),
        ],
        [
            _game_button("W", "west"),
            _game_button("Inspect", "look"),
            _game_button("E", "east"),
        ],
        [
            _game_button("SW", "sw"),
            _game_button("S", "south"),
            _game_button("SE", "se"),
        ],
    ]
    inline_keyboard.extend(_context_action_rows(context_actions))
    inline_keyboard.append(
        [
            InlineKeyboardButton(text="Spell", callback_data=CallbackData.SPELL_MENU),
            InlineKeyboardButton(text="Menu", callback_data=CallbackData.GAME_MENU),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def _modal_action_rows(actions) -> list[list[InlineKeyboardButton]]:
    rows = _context_action_rows(actions)
    rows.extend(
        [
            [
                InlineKeyboardButton(text="Spell", callback_data=CallbackData.SPELL_MENU),
                InlineKeyboardButton(text="Back to Game", callback_data=CallbackData.BACK_TO_GAME),
            ],
            [InlineKeyboardButton(text="Menu", callback_data=CallbackData.GAME_MENU)],
        ]
    )
    return rows


def _context_action_rows(actions) -> list[list[InlineKeyboardButton]]:
    return [
        [
            InlineKeyboardButton(
                text=_button_text(action.label),
                callback_data=f"{CallbackData.GAME_PREFIX}{action.command}",
            )
        ]
        for action in actions
    ]


def _button_text(label: str) -> str:
    stripped = label.strip()
    replacement = _BUTTON_TEXT_REPLACEMENTS.get(stripped)
    if replacement is not None:
        return replacement
    cleaned = re.sub(r"[^A-Za-z ]+", " ", stripped)
    cleaned = " ".join(cleaned.split())
    return cleaned or "Action"


def _pending_prompt_actions(pending_prompt) -> list[GameAction]:
    if not isinstance(pending_prompt, dict):
        return []
    kind = pending_prompt.get("kind")
    if kind == "direction":
        return _system_prompt_actions()
    if kind == "indexed_picklist":
        command_prefix = "pick:"
    elif kind == "multi_picklist":
        command_prefix = "multipick:"
    elif kind == "number_prompt":
        command_prefix = "number:"
    elif kind == "inventory":
        command_prefix = "invitem:"
    elif kind == "inventory_action":
        command_prefix = "inv:"
    else:
        command_prefix = "prompt:"
    options = pending_prompt.get("options")
    if not isinstance(options, list):
        return []

    actions: list[GameAction] = []
    for option in options:
        if not isinstance(option, dict):
            continue
        key = str(option.get("key", "")).strip().lower()
        label = str(option.get("label", "")).strip()
        if not key or not label:
            continue
        actions.append(
            GameAction(
                id=f"prompt_{key}",
                label=label,
                command=f"{command_prefix}{key}",
            )
        )
    actions.extend(_system_prompt_actions())
    return actions


def _system_prompt_actions() -> list[GameAction]:
    return [
        GameAction(id="prompt_cancel", label="Cancel", command="prompt:cancel"),
        GameAction(id="prompt_menu", label="Main Menu", command="prompt:menu"),
    ]


def spell_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_game_button("Known Spells", "spells")],
            [_game_button("Cast Spell", "cast")],
            [InlineKeyboardButton(text="Main Menu", callback_data=CallbackData.MAIN_MENU)],
            [InlineKeyboardButton(text="Back to Game", callback_data=CallbackData.BACK_TO_GAME)],
        ]
    )


def game_legend_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Main Menu", callback_data=CallbackData.MAIN_MENU)],
            [InlineKeyboardButton(text="Back to Game", callback_data=CallbackData.BACK_TO_GAME)],
        ]
    )


def game_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Inventory", callback_data=_game_callback("inventory"))],
            [InlineKeyboardButton(text="Pack Weight", callback_data=_game_callback("pack_weight"))],
            [
                InlineKeyboardButton(text="Wield Weapon", callback_data=_game_callback("wield")),
                InlineKeyboardButton(text="Wear Armor", callback_data=_game_callback("wear")),
            ],
            [InlineKeyboardButton(text="Take Off", callback_data=_game_callback("take_off"))],
            [InlineKeyboardButton(text="Drop Item", callback_data=_game_callback("drop"))],
            [
                InlineKeyboardButton(text="Read Scroll", callback_data=_game_callback("read")),
                InlineKeyboardButton(text="Quaff Potion", callback_data=_game_callback("quaff")),
            ],
            [InlineKeyboardButton(text="Eat", callback_data=_game_callback("eat"))],
            [InlineKeyboardButton(text="Teleport", callback_data=_game_callback("teleport"))],
            [InlineKeyboardButton(text="Legend", callback_data=CallbackData.GAME_LEGEND)],
            [InlineKeyboardButton(text="Main Menu", callback_data=CallbackData.MAIN_MENU)],
            [InlineKeyboardButton(text="Back to Game", callback_data=CallbackData.BACK_TO_GAME)],
        ]
    )


def _game_button(label: str, command: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=label, callback_data=_game_callback(command))


def _game_callback(command: str) -> str:
    return f"{CallbackData.GAME_PREFIX}{command}"
