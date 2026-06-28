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
from tglarn_game import GameAction, GameResponse, PlaceholderGameAdapter


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

    assert texts == ["Play Game", "Main Menu"]
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

    assert texts[:9] == ["NW", "N", "NE", "W", "Inspect", "E", "SW", "S", "SE"]
    assert "Spell" in texts
    assert "Menu" in texts
    assert "Wait" not in texts
    assert "Status" not in texts
    assert f"{CallbackData.GAME_PREFIX}north" in callback_data
    assert CallbackData.SPELL_MENU in callback_data
    assert CallbackData.GAME_MENU in callback_data


def test_game_keyboard_adds_descend_on_stairs() -> None:
    adapter = PlaceholderGameAdapter()
    response = adapter.apply_command(adapter.restart().state | {"x": 45, "y": 18}, "east")

    texts = _button_texts(game_keyboard(response))
    callback_data = _button_callback_data(game_keyboard(response))

    assert "Descend" in texts
    assert f"{CallbackData.GAME_PREFIX}descend" in callback_data


def test_game_keyboard_renders_prompt_options_as_separate_rows() -> None:
    response = GameResponse(
        state={},
        screen="Cast which spell?",
        actions=[
            GameAction(id="prompt_b", label="Magic missile", command="prompt:b"),
            GameAction(id="prompt_e", label="Charm monster", command="prompt:e"),
        ],
    )

    rows = [[button.text for button in row] for row in game_keyboard(response).inline_keyboard]
    callback_data = _button_callback_data(game_keyboard(response))

    assert ["Magic missile"] in rows
    assert ["Charm monster"] in rows
    assert f"{CallbackData.GAME_PREFIX}prompt:b" in callback_data
    assert f"{CallbackData.GAME_PREFIX}prompt:e" in callback_data


def test_game_keyboard_renders_chest_prompt_options() -> None:
    response = GameResponse(
        state={},
        screen="There is a chest here.",
        actions=[
            GameAction(id="prompt_g", label="Try to open it", command="prompt:g"),
            GameAction(id="prompt_t", label="Take it", command="prompt:t"),
            GameAction(id="prompt_n", label="Do nothing", command="prompt:n"),
        ],
    )

    rows = [[button.text for button in row] for row in game_keyboard(response).inline_keyboard]
    callback_data = _button_callback_data(game_keyboard(response))

    assert ["Try to open it"] in rows
    assert ["Take it"] in rows
    assert ["Do nothing"] in rows
    assert f"{CallbackData.GAME_PREFIX}prompt:g" in callback_data
    assert f"{CallbackData.GAME_PREFIX}prompt:t" in callback_data
    assert f"{CallbackData.GAME_PREFIX}prompt:n" in callback_data


def test_game_keyboard_for_modal_prompt_omits_movement_controls() -> None:
    response = GameResponse(
        state={},
        screen="Cast which spell?",
        status={"screen_type": "modal"},
        actions=[
            GameAction(id="prompt_b", label="Magic missile", command="prompt:b"),
            GameAction(id="prompt_e", label="Charm monster", command="prompt:e"),
        ],
    )

    texts = _button_texts(game_keyboard(response))
    callback_data = _button_callback_data(game_keyboard(response))

    assert "NW" not in texts
    assert "Magic missile" in texts
    assert "Charm monster" in texts
    assert "Back to Game" in texts
    assert f"{CallbackData.GAME_PREFIX}prompt:b" in callback_data
    assert CallbackData.BACK_TO_GAME in callback_data


def test_game_keyboard_for_modal_list_returns_to_game() -> None:
    response = GameResponse(
        state={},
        screen="Discoveries To Date:\nSpells:\n    magic missile",
        status={"screen_type": "modal"},
    )

    texts = _button_texts(game_keyboard(response))

    assert texts == ["Spell", "Back to Game", "Menu"]


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
