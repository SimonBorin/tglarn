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
    _game_over_log_lines,
    _inventory_item_from_command,
    _is_game_over_display,
    _modal_exit_key,
    _next_viewport_origin,
    _pan_start,
    _pending_prompt_from_display,
    _prompt_answer_from_command,
    _prompt_answer_keys,
    _prompt_replays_trigger,
    _prompt_requires_enter,
    _read_map_snapshot,
    _render_display_lines,
    _should_capture_map_snapshot,
    _should_force_full_redraw,
    _should_keep_base_save_for_prompt,
    _TerminalCell,
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


def test_map_rendering_marks_default_spaces_as_known_floor() -> None:
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
    assert "." in map_text
    assert status["screen_type"] == "map"


def test_map_rendering_keeps_colored_unrevealed_spaces_blank() -> None:
    lines = [" " * 80 for _ in range(25)]
    lines[14] = " " * 25 + "#J#" + " " * 52
    lines[15] = " " * 26 + "@" + " " * 53
    lines[16] = " " * 25 + "#X#" + " " * 52
    lines[17] = "Spells: 1(2) AC:2 WC:0 LV:1 Time:0"
    lines[18] = "HP: 6 (8) STR=8 INT=14 WIS=12"
    default_cell = _TerminalCell(" ", "default", "default", False, False)
    unseen_cell = _TerminalCell(" ", "black", "default", False, False)
    cells = [[default_cell for _ in range(80)] for _ in range(25)]
    for y in range(17):
        for x in range(24):
            cells[y][x] = unseen_cell

    screen, _, _ = _render_display_lines(lines, "max", cells)
    map_lines = screen.split("Spells:", maxsplit=1)[0].splitlines()

    assert map_lines[0].startswith(" " * 24)
    assert "." in map_lines[0][24:]


def test_map_viewport_does_not_recenter_on_each_step() -> None:
    lines = [" " * 80 for _ in range(25)]
    lines[8] = " " * 40 + "@....$" + " " * 34
    lines[17] = "Spells: 1(2) AC:2 WC:0 LV:1 Time:0"
    lines[18] = "HP: 6 (8) STR=8 INT=14 WIS=12 CON=8 DEX=8 CHA=14 LV: H Gold: 0"
    screen, _, status = _render_display_lines(lines, "max")

    moved_lines = [" " * 80 for _ in range(25)]
    moved_lines[8] = " " * 39 + "@.....$" + " " * 34
    moved_lines[17] = lines[17]
    moved_lines[18] = lines[18]
    moved_screen, _, moved_status = _render_display_lines(
        moved_lines,
        "max",
        previous_viewport=status["viewport_origin"],
    )

    assert status["viewport_origin"]["left"] == moved_status["viewport_origin"]["left"]
    assert screen.splitlines()[8].index("$") == moved_screen.splitlines()[8].index("$")


def test_map_viewport_uses_relarn_map_width_not_terminal_width() -> None:
    lines = [" " * 80 for _ in range(25)]
    lines[8] = " " * 60 + "@E" + " " * 10 + "!"
    lines[17] = "Spells: 1(2) AC:2 WC:0 LV:1 Time:0"
    lines[18] = "HP: 6 (8) STR=8 INT=14 WIS=12 CON=8 DEX=8 CHA=14 LV: H Gold: 0"

    screen, _, status = _render_display_lines(lines, "max")
    map_text = screen.split("Spells:", maxsplit=1)[0]

    assert status["viewport_origin"]["left"] == 15
    assert "@E" in map_text
    assert "!" not in map_text


def test_map_viewport_clamps_old_terminal_width_origin() -> None:
    lines = [" " * 80 for _ in range(25)]
    lines[8] = " " * 60 + "@E" + " " * 18
    lines[17] = "Spells: 1(2) AC:2 WC:0 LV:1 Time:0"
    lines[18] = "HP: 6 (8) STR=8 INT=14 WIS=12 CON=8 DEX=8 CHA=14 LV: H Gold: 0"
    previous = {"left": 28, "top": 0, "level": "H", "map_view": "max"}

    _, _, status = _render_display_lines(lines, "max", previous_viewport=previous)

    assert status["viewport_origin"]["left"] == 15


def test_map_viewport_does_not_pan_before_edge_margin() -> None:
    assert _pan_start(center=14, size=31, total=80, previous_start=10) == 10
    assert _pan_start(center=37, size=31, total=80, previous_start=10) == 10


def test_modal_response_preserves_previous_viewport_origin() -> None:
    previous = {"left": 10, "top": 0, "level": "H", "map_view": "wide"}

    assert _next_viewport_origin({"screen_type": "modal"}, previous) == previous
    assert _next_viewport_origin(
        {"viewport_origin": {"left": 12, "top": 0, "level": "H", "map_view": "wide"}},
        previous,
    ) == {"left": 12, "top": 0, "level": "H", "map_view": "wide"}


def test_full_redraw_is_for_regular_map_screens_only() -> None:
    lines = [" " * 80 for _ in range(25)]
    lines[15] = " " * 26 + "@" + " " * 53
    lines[17] = "Spells: 1(2) AC:2 WC:0 LV:1 Time:0"
    lines[18] = "HP: 6 (8) STR=8 INT=14 WIS=12"

    assert _should_force_full_redraw(lines)


def test_full_redraw_skips_prompted_map_screens() -> None:
    lines = [" " * 80 for _ in range(25)]
    lines[15] = " " * 26 + "@" + " " * 53
    lines[17] = "Spells: 1(2) AC:2 WC:0 LV:1 Time:0"
    lines[18] = "HP: 6 (8) STR=8 INT=14 WIS=12"
    lines[19] = "Do you (g) go inside, or (n) do nothing?"

    assert not _should_force_full_redraw(lines)


def test_full_redraw_skips_wrapped_chest_prompt() -> None:
    lines = [" " * 80 for _ in range(25)]
    lines[15] = " " * 26 + "@" + " " * 53
    lines[17] = "Spells: 1(2) AC:2 WC:0 LV:1 Time:0"
    lines[18] = "HP: 6 (8) STR=8 INT=14 WIS=12"
    lines[19] = "There is a chest here."
    lines[20] = "Do you (g) try to open it, (t) take it, or"
    lines[21] = "(n) do nothing?"

    assert not _should_force_full_redraw(lines)


def test_full_redraw_skips_modal_screens() -> None:
    lines = ["Inventory", "Gold: $0", "a. a spear"]

    assert not _should_force_full_redraw(lines)


def test_map_snapshot_capture_includes_prompted_map_screens() -> None:
    lines = [" " * 80 for _ in range(25)]
    lines[15] = " " * 26 + "@" + " " * 53
    lines[17] = "Spells: 1(2) AC:2 WC:0 LV:1 Time:0"
    lines[18] = "HP: 6 (8) STR=8 INT=14 WIS=12"

    assert _should_capture_map_snapshot(lines)

    lines[19] = "Do you (g) go inside, or (n) do nothing?"
    assert _should_capture_map_snapshot(lines)

    lines[19] = "In what direction? "
    assert _should_capture_map_snapshot(lines)


def test_map_snapshot_capture_skips_modal_screens() -> None:
    assert not _should_capture_map_snapshot(["Inventory", "Gold: $0", "a. a spear"])


def test_read_map_snapshot_parses_canonical_map_dump(tmp_path) -> None:
    snapshot_path = tmp_path / "tglarn-map.tsv"
    snapshot_path.write_text(
        "\n".join(
            [
                "TGLARN_MAP_V1",
                "level\t1",
                "player\t2\t1",
                "width\t4",
                "height\t2",
                "glyphs",
                ".+S.",
                "  @.",
                "layers",
                "FOMO",
                "UUPF",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert _read_map_snapshot(snapshot_path) == {
        "version": 1,
        "width": 4,
        "height": 2,
        "level": "1",
        "player": {"x": 2, "y": 1},
        "glyphs": [".+S.", "  @."],
        "layers": ["FOMO", "UUPF"],
    }


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


def test_prompt_screens_keep_base_save_instead_of_saving_prompt_process() -> None:
    spell_lines = [
        "Cast which spell?",
        "b.   magic missile Fires a magic arrow at the target",
        "Up:k/CTRL+p/UP Down:j/CTRL+n/DOWN Select:ENTER",
    ]

    assert _should_keep_base_save_for_prompt(spell_lines, [b"c"])

    map_lines = [" " * 80 for _ in range(25)]
    map_lines[15] = " " * 26 + "@" + " " * 53
    map_lines[17] = "Spells: 1(2) AC:2 WC:0 LV:1 Time:0"
    map_lines[18] = "HP: 6 (8) STR=8 INT=14 WIS=12"
    assert not _should_keep_base_save_for_prompt(map_lines, [b"l"])


def test_answered_direction_prompt_does_not_keep_base_save() -> None:
    lines = [" " * 80 for _ in range(25)]
    lines[15] = " " * 26 + "@" + " " * 53
    lines[17] = "Spells: 1(2) AC:2 WC:0 LV:1 Time:0"
    lines[18] = "HP: 6 (8) STR=8 INT=14 WIS=12"
    lines[19] = "In what direction?"
    lines[20] = "The hobgoblin died!"

    keys = [b"c", b"b", b"\n", b"h"]

    assert _detect_prompt(lines) is not None
    assert _pending_prompt_from_display(lines, keys) is None
    assert not _should_keep_base_save_for_prompt(lines, keys)


def test_detect_prompt_extracts_dealer_picklist_options() -> None:
    prompt = _detect_prompt(
        [
            "Hey man, welcome to Dealer McDope's Pad! I gots the some of the finest",
            "shit you'll find anywhere in Larn -- check it out...",
            "Looks like you got about 244 bucks on you.",
            "     Killer Speed                       100 bucks",
            "     Groovy Acid                        250 bucks",
            "     Monster Hash                       500 bucks",
            "Up:k/CTRL+p/UP Down:j/CTRL+n/DOWN Select:ENTER Quit:ESC/CTRL+x",
            "To select an individual item, type the corresponding",
            "key; CTRL+v escapes.",
        ]
    )

    assert prompt == {
        "question": "Choose an item.",
        "kind": "indexed_picklist",
        "options": [
            {"key": "0", "label": "Killer Speed (100 bucks)"},
            {"key": "1", "label": "Groovy Acid (250 bucks)"},
            {"key": "2", "label": "Monster Hash (500 bucks)"},
        ],
    }


def test_detect_prompt_extracts_dnd_store_picklist_options() -> None:
    prompt = _detect_prompt(
        [
            "Welcome to the Larn Thrift Shoppe.",
            "\"Feel free to browse to your heart's content.\"",
            "You break 'em, you bought 'em.",
            "Your gold: $144",
            "     a spear                                  $30",
            "     leather armor                            $50",
            "     a magic potion                           $90",
            "Up:k/CTRL+p/UP Down:j/CTRL+n/DOWN Select:ENTER Quit:ESC/CTRL+x",
            "To select an individual item, type the corresponding",
            "key; CTRL+v escapes.",
        ]
    )

    assert prompt == {
        "question": "Choose an item.",
        "kind": "indexed_picklist",
        "options": [
            {"key": "0", "label": "a spear (30 gold)"},
            {"key": "1", "label": "leather armor (50 gold)"},
            {"key": "2", "label": "a magic potion (90 gold)"},
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


def test_detect_prompt_extracts_bank_menu_options() -> None:
    prompt = _detect_prompt(
        [
            "Welcome to the First National Bank of Larn.",
            "\"Bank of Opportunism.\"",
            "(c)heck your balance",
            "(d)eposit money",
            "(w)ithdraw money",
            "(s)ell a gem or artifact",
            "",
            "(e)xit",
            "Up:k/CTRL+p/UP Down:j/CTRL+n/DOWN Select:ENTER",
            "Quit:ESC/CTRL+x",
        ]
    )

    assert prompt == {
        "question": "Choose a bank action.",
        "kind": "picklist",
        "options": [
            {"key": "c", "label": "Check your balance"},
            {"key": "d", "label": "Deposit money"},
            {"key": "w", "label": "Withdraw money"},
            {"key": "s", "label": "Sell a gem or artifact"},
            {"key": "e", "label": "Exit"},
        ],
    }
    assert _prompt_requires_enter(prompt)
    assert _prompt_answer_keys("c", prompt) == [b"c", b"\n"]


def test_indexed_picklist_prompt_answers_move_to_selected_row() -> None:
    prompt = {
        "question": "Choose an item.",
        "kind": "indexed_picklist",
        "options": [
            {"key": "0", "label": "Killer Speed (100 bucks)"},
            {"key": "1", "label": "Groovy Acid (250 bucks)"},
            {"key": "2", "label": "Monster Hash (500 bucks)"},
        ],
    }

    answer = _prompt_answer_from_command("pick:2", prompt)

    assert answer == "2"
    assert _prompt_answer_keys(answer, prompt) == [b"j", b"j", b"\n"]


def test_detect_prompt_extracts_inventory_items() -> None:
    prompt = _detect_prompt(
        [
            "Inventory",
            "Gold: $144",
            "a.   a magic potion",
            "b.   a scroll of create artifact",
            "c.   a magic scroll",
            "d.   a sparkling sapphire",
            "e.   an enchanting emerald",
            "f.   some speed",
            "Up:k/CTRL+p/UP Down:j/CTRL+n/DOWN Select:ENTER",
            "Quit:ESC/CTRL+x",
        ]
    )

    assert prompt is not None
    assert prompt["question"] == "Choose an inventory item."
    assert prompt["kind"] == "inventory"
    assert [(option["key"], option["label"]) for option in prompt["options"]] == [
        ("a", "a. magic potion"),
        ("b", "b. scroll of create artifact"),
        ("c", "c. magic scroll"),
        ("d", "d. sparkling sapphire"),
        ("e", "e. enchanting emerald"),
        ("f", "f. speed"),
    ]
    assert prompt["options"][0]["actions"] == [
        {"key": "quaff:a", "label": "Quaff"},
        {"key": "drop:a", "label": "Drop"},
    ]
    assert prompt["options"][1]["actions"] == [
        {"key": "read:b", "label": "Read"},
        {"key": "drop:b", "label": "Drop"},
    ]
    assert prompt["options"][5]["actions"] == [
        {"key": "drop:f", "label": "Drop"},
    ]


def test_inventory_prompt_selects_item_for_action_submenu() -> None:
    prompt = {
        "question": "Choose an inventory item.",
        "kind": "inventory",
        "options": [
            {
                "key": "a",
                "label": "a. magic potion",
                "item_label": "a magic potion",
                "actions": [
                    {"key": "quaff:a", "label": "Quaff"},
                    {"key": "drop:a", "label": "Drop"},
                ],
            },
        ],
    }

    assert _inventory_item_from_command("invitem:a", prompt) == "a"
    assert _prompt_answer_from_command("invitem:a", prompt) is None


def test_inventory_action_prompt_answers_send_item_action_without_reopening_inventory() -> None:
    prompt = {
        "question": "Choose action for a. magic potion.",
        "kind": "inventory_action",
        "options": [
            {"key": "quaff:a", "label": "Quaff"},
            {"key": "drop:a", "label": "Drop"},
        ],
    }

    answer = _prompt_answer_from_command("inv:quaff:a", prompt)

    assert answer == "quaff:a"
    assert _prompt_answer_keys(answer, prompt) == [b"q", b"a"]
    assert not _prompt_replays_trigger(prompt)


def test_modal_exit_key_closes_dealer_result_page() -> None:
    lines = [
        "",
        "",
        "                         Whattaya trying to pull on me?",
        "                         You aint got the cash!",
        "",
        "    ---- Press return or escape to exit ---- ",
    ]

    assert _modal_exit_key(lines) == b"\x1b"


def test_modal_exit_key_closes_dealer_picklist() -> None:
    lines = [
        "Hey man, welcome to Dealer McDope's Pad! I gots the some of the finest",
        "shit you'll find anywhere in Larn -- check it out...",
        "Looks like you got about 244 bucks on you.",
        "     Killer Speed                       100 bucks",
        "     Groovy Acid                        250 bucks",
        "Up:k/CTRL+p/UP Down:j/CTRL+n/DOWN Select:ENTER Quit:ESC/CTRL+x",
        "To select an individual item, type the corresponding",
        "key; CTRL+v escapes.",
    ]

    assert _modal_exit_key(lines) == b"\x1b"


def test_modal_exit_key_leaves_regular_map_ready_to_save() -> None:
    lines = [" " * 80 for _ in range(25)]
    lines[15] = " " * 26 + "@" + " " * 53
    lines[17] = "Spells: 1(2) AC:2 WC:0 LV:1 Time:0"
    lines[18] = "HP: 6 (8) STR=8 INT=14 WIS=12"

    assert _modal_exit_key(lines) is None


def test_choice_prompt_ignores_answer_echo() -> None:
    prompt = _detect_prompt(
        [""] * 19
        + [
            "You have found the dungeon entrance",
            "Do you (g) go inside, or (n) do nothing?  g",
        ]
    )

    assert prompt is None


def test_choice_prompt_ignores_answer_echo_with_followup_log() -> None:
    prompt = _detect_prompt(
        [""] * 19
        + [
            "You find a brilliant diamond.",
            "Do you want to (t) take it, or (n) do nothing? t",
            "take.",
        ]
    )

    assert prompt is None


def test_choice_prompt_extracts_chest_options() -> None:
    prompt = _detect_prompt(
        [""] * 19
        + [
            "There is a chest here.",
            "Do you (g) try to open it, (t) take it, or",
            "(n) do nothing?",
        ]
    )

    assert prompt == {
        "question": "Do you (g) try to open it, (t) take it, or (n) do nothing?",
        "kind": "choice",
        "options": [
            {"key": "g", "label": "Try to open it"},
            {"key": "t", "label": "Take it"},
            {"key": "n", "label": "Do nothing"},
        ],
    }


def test_choice_prompt_extracts_dealer_pad_options() -> None:
    prompt = _detect_prompt(
        [""] * 19
        + [
            "You have found Dealer McDope's Pad.",
            "Do you (g) check it out, or (n) stay here?",
        ]
    )

    assert prompt == {
        "question": "Do you (g) check it out, or (n) stay here?",
        "kind": "choice",
        "options": [
            {"key": "g", "label": "Check it out"},
            {"key": "n", "label": "Stay here"},
        ],
    }


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


def test_game_over_log_preserves_death_context_without_continue_prompt() -> None:
    lines = [" " * 80 for _ in range(25)]
    lines[15] = " " * 26 + "@" + " " * 53
    lines[17] = "Spells: 1(2) AC:2 WC:0 LV:1 Time:0"
    lines[18] = "HP: 0 (8) STR=8 INT=14 WIS=12"
    lines[19] = "The chest explodes as you open it."
    lines[20] = "You suffer 5 hit points damage!"
    lines[21] = "Alas, you have died."
    lines[22] = "Press ENTER, ESCAPE or SPACE to continue:"

    assert _game_over_log_lines(lines) == [
        "The chest explodes as you open it.",
        "You suffer 5 hit points damage!",
        "Alas, you have died.",
    ]
