from tglarn_bot.keyboards import (
    CallbackData,
    character_class_keyboard,
    character_gender_keyboard,
    game_keyboard,
    game_legend_keyboard,
    game_menu_keyboard,
    intro_keyboard,
    main_menu_keyboard,
    map_view_keyboard,
    restart_confirmation_keyboard,
    rules_menu_keyboard,
    spell_menu_keyboard,
)
from tglarn_game import GameResponse, PlaceholderGameAdapter
from tglarn_game.relarn_process import (
    _detect_prompt,
    _is_game_over_display,
    _prompt_answer_from_command,
    _prompt_requires_enter,
    _render_display_lines,
)


def _button_texts(markup):
    return [button.text for row in markup.inline_keyboard for button in row]


def test_main_menu_contains_expected_actions() -> None:
    texts = _button_texts(main_menu_keyboard())

    assert texts == [
        "Resume Game",
        "Restart Game",
        "Rules",
        "Legend",
        "Display Size",
        "About",
        "Repository",
    ]


def test_intro_keyboard_starts_character_creation() -> None:
    texts = _button_texts(intro_keyboard())
    callback_data = _button_callback_data(intro_keyboard())

    assert texts == ["Create Character", "Main Menu"]
    assert CallbackData.CHARACTER_INTRO in callback_data


def test_character_class_keyboard_contains_relarn_classes() -> None:
    texts = _button_texts(character_class_keyboard())
    callback_data = _button_callback_data(character_class_keyboard())

    assert "Wizard" in texts
    assert "Klingon" in texts
    assert "Rambo" in texts
    assert f"{CallbackData.CHARACTER_CLASS_PREFIX}wizard" in callback_data


def test_character_gender_keyboard_preserves_selected_class() -> None:
    texts = _button_texts(character_gender_keyboard("wizard"))
    callback_data = _button_callback_data(character_gender_keyboard("wizard"))

    assert texts[:3] == ["Male", "Female", "Nonbinary"]
    assert f"{CallbackData.CHARACTER_GENDER_PREFIX}wizard:female" in callback_data


def test_rules_menu_contains_subsections() -> None:
    texts = _button_texts(rules_menu_keyboard())

    assert texts == ["Controls", "Game Mechanics", "Main Menu"]


def test_map_view_menu_contains_expected_sizes() -> None:
    texts = _button_texts(map_view_keyboard())

    assert texts == ["Medium", "Wide", "Max Size", "Main Menu"]


def test_restart_confirmation_is_explicit() -> None:
    texts = _button_texts(restart_confirmation_keyboard())

    assert texts == ["Restart", "Cancel"]


def _button_callback_data(markup):
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def test_game_keyboard_contains_default_controls() -> None:
    response = PlaceholderGameAdapter().restart()
    texts = _button_texts(game_keyboard(response))
    callback_data = _button_callback_data(game_keyboard(response))

    assert texts[:9] == ["NW", "N", "NE", "W", "Look", "E", "SW", "S", "SE"]
    assert "Spell" in texts
    assert "Menu" in texts
    assert "Wait" not in texts
    assert "Status" not in texts
    assert f"{CallbackData.GAME_PREFIX}north" in callback_data
    assert CallbackData.SPELL_MENU in callback_data
    assert CallbackData.GAME_MENU in callback_data


def test_game_keyboard_for_game_over_only_offers_menu_actions() -> None:
    response = GameResponse(
        state={"adapter": "relarn_process", "game_over": True},
        screen="Game over.",
        status={"game_over": True},
    )

    texts = _button_texts(game_keyboard(response))

    assert texts == ["Main Menu", "Restart Game"]


def test_game_keyboard_adds_descend_on_stairs() -> None:
    adapter = PlaceholderGameAdapter()
    response = adapter.apply_command(adapter.restart().state | {"x": 45, "y": 18}, "east")

    texts = _button_texts(game_keyboard(response))
    callback_data = _button_callback_data(game_keyboard(response))

    assert "Descend" in texts
    assert f"{CallbackData.GAME_PREFIX}descend" in callback_data


def test_spell_menu_contains_spell_actions() -> None:
    texts = _button_texts(spell_menu_keyboard())
    callback_data = _button_callback_data(spell_menu_keyboard())

    assert texts == ["Known Spells", "Cast Spell", "Main Menu", "Back to Game"]
    assert f"{CallbackData.GAME_PREFIX}spells" in callback_data
    assert f"{CallbackData.GAME_PREFIX}cast" in callback_data


def test_game_legend_keyboard_returns_to_game() -> None:
    texts = _button_texts(game_legend_keyboard())
    callback_data = _button_callback_data(game_legend_keyboard())

    assert texts == ["Main Menu", "Back to Game"]
    assert CallbackData.BACK_TO_GAME in callback_data
    assert CallbackData.MAIN_MENU in callback_data


def test_game_menu_contains_inventory_and_item_actions() -> None:
    texts = _button_texts(game_menu_keyboard())
    callback_data = _button_callback_data(game_menu_keyboard())

    assert "Inventory" in texts
    assert "Pack Weight" in texts
    assert "Wield Weapon" in texts
    assert "Wear Armor" in texts
    assert "Read Scroll" in texts
    assert "Quaff Potion" in texts
    assert "Teleport" in texts
    assert "Legend" in texts
    assert texts[-3:] == ["Legend", "Main Menu", "Back to Game"]
    assert f"{CallbackData.GAME_PREFIX}inventory" in callback_data
    assert f"{CallbackData.GAME_PREFIX}teleport" in callback_data
    assert CallbackData.GAME_LEGEND in callback_data


def test_modal_rendering_removes_curses_picker_help() -> None:
    lines = [
        "                                  Inventory",
        "                                   Gold: $0",
        "  a.   a spear (weapon in hand)",
        "Up:k/CTRL+p/UP Down:j/CTRL+n/DOWN Select:ENTER",
        "Quit:ESC/CTRL+x",
        "To select an individual item, type the corresponding",
        "key; CTRL+v escapes.",
    ]

    screen, _, status = _render_display_lines(lines, "wide")

    assert screen == "Inventory\nGold: $0\na.   a spear (weapon in hand)"
    assert status["screen_type"] == "modal"


def test_modal_rendering_keeps_discovery_sections_readable() -> None:
    lines = [
        "                             Discoveries To Date:",
        "       Spells:",
        "           protection",
        "       Scrolls:",
        "       Potions:",
        "           cure dianthroritis",
        "Up:k/CTRL+p/UP Down:j/CTRL+n/DOWN Select:ENTER",
        "Quit:ESC/CTRL+x",
        "To select an individual item, type the corresponding",
        "key; CTRL+v escapes.",
    ]

    screen, _, _ = _render_display_lines(lines, "wide")

    assert screen == (
        "Discoveries To Date:\n"
        "Spells:\n"
        "    protection\n"
        "Scrolls:\n"
        "Potions:\n"
        "    cure dianthroritis"
    )
    assert "CTRL" not in screen


def test_map_rendering_preserves_native_spaces_for_unrevealed_tiles() -> None:
    lines = [" " * 80 for _ in range(25)]
    lines[14] = " " * 25 + "#J#" + " " * 52
    lines[15] = " " * 26 + "@" + " " * 53
    lines[16] = " " * 25 + "#X#" + " " * 52
    lines[17] = "Spells: 1(2) AC:2 WC:0 LV:1 Time:0"
    lines[18] = "HP: 6 (8) STR=8 INT=14 WIS=12"

    screen, _, status = _render_display_lines(lines, "max")

    map_text = screen.split("Spells:", maxsplit=1)[0]
    assert "#J#" in screen
    assert "#X#" in screen
    assert "." not in map_text
    assert status["screen_type"] == "map"


def test_detect_prompt_extracts_spell_picklist_options() -> None:
    prompt = _detect_prompt(
        [
            "Cast which spell?",
            "b.   magic missile Fires a magic arrow at the target",
            "e.   charm monster        Some monsters may be awed",
            "at your magnificence",
            "Up:k/CTRL+p/UP Down:j/CTRL+n/DOWN Select:ENTER",
            "Quit:ESC/CTRL+x",
        ]
    )

    assert prompt == {
        "question": "Cast which spell?",
        "kind": "picklist",
        "options": [
            {"key": "b", "label": "Magic missile"},
            {"key": "e", "label": "Charm monster"},
        ],
    }


def test_picklist_prompt_answers_require_enter() -> None:
    prompt = _detect_prompt(
        [
            "Cast which spell?",
            "a.   protection Generates a +2 protection field",
            "Up:k/CTRL+p/UP Down:j/CTRL+n/DOWN Select:ENTER",
        ]
    )

    assert prompt is not None
    assert _prompt_requires_enter(prompt)
    assert _prompt_answer_from_command("prompt:a", prompt) == "a"


def test_direction_prompt_accepts_movement_commands() -> None:
    prompt = _detect_prompt([""] * 19 + ["In what direction? "])

    assert prompt is not None
    assert prompt["kind"] == "direction"
    assert _prompt_answer_from_command("north", prompt) == "k"
    assert _prompt_answer_from_command("prompt:l", prompt) == "l"


def test_game_over_detection_matches_relarn_final_screens() -> None:
    assert _is_game_over_display(["Alas, you have died."])
    assert _is_game_over_display(["Final Score: 120"])
    assert not _is_game_over_display(["The jackal hit you"])
