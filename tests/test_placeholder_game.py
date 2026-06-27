from tglarn_game import PlaceholderGameAdapter


def test_placeholder_restart_returns_initial_screen() -> None:
    response = PlaceholderGameAdapter().restart()

    assert response.state["adapter"] == "placeholder"
    assert "@" in response.screen
    assert response.log[0] == "A new run begins."
    assert "Send help" in response.log[1]


def test_placeholder_movement_updates_turn() -> None:
    adapter = PlaceholderGameAdapter()
    initial = adapter.restart()

    moved = adapter.apply_command(initial.state, "east")

    assert moved.state["x"] == initial.state["x"] + 1
    assert moved.state["turn"] == 1
    assert moved.log == ["You move east."]


def test_placeholder_diagonal_movement_updates_position() -> None:
    adapter = PlaceholderGameAdapter()
    initial = adapter.restart().state | {"x": 2, "y": 2}

    moved = adapter.apply_command(initial, "se")

    assert moved.state["x"] == 3
    assert moved.state["y"] == 3
    assert moved.state["turn"] == 1


def test_placeholder_wait_consumes_turn() -> None:
    adapter = PlaceholderGameAdapter()
    initial = adapter.restart()

    waited = adapter.apply_command(initial.state, "wait")

    assert waited.state["turn"] == 1
    assert waited.log == ["You wait one turn."]


def test_placeholder_reports_stairs_when_player_steps_on_them() -> None:
    adapter = PlaceholderGameAdapter()
    state = adapter.restart().state | {"x": 45, "y": 18}

    moved = adapter.apply_command(state, "east")

    assert moved.state["x"] == 46
    assert moved.state["y"] == 18
    assert moved.log == ["You find stairs leading deeper. Send descend to go down."]
    assert [action.command for action in moved.actions] == ["descend"]


def test_placeholder_descend_requires_stairs() -> None:
    adapter = PlaceholderGameAdapter()
    initial = adapter.restart()

    response = adapter.apply_command(initial.state, "descend")

    assert response.state["depth"] == 1
    assert response.state["turn"] == 0
    assert response.log == ["There are no stairs here."]


def test_placeholder_descends_from_stairs() -> None:
    adapter = PlaceholderGameAdapter()
    state = adapter.restart().state | {"x": 46, "y": 18}

    response = adapter.apply_command(state, "go down")

    assert response.state["depth"] == 2
    assert response.state["x"] == 1
    assert response.state["y"] == 1
    assert response.state["turn"] == 1
    assert response.log == ["You descend to dungeon level 2."]
    assert response.actions == []
    assert "DL 2" in response.screen


def test_placeholder_game_menu_commands_return_stub_logs() -> None:
    adapter = PlaceholderGameAdapter()
    initial = adapter.restart()

    inventory = adapter.apply_command(initial.state, "inventory")
    teleport = adapter.apply_command(initial.state, "teleport")

    assert inventory.log == ["Your inventory is empty."]
    assert teleport.log == ["You do not know how to teleport yet."]
    assert inventory.state["turn"] == 0


def test_placeholder_spell_commands_return_stub_logs() -> None:
    adapter = PlaceholderGameAdapter()
    initial = adapter.restart()

    spells = adapter.apply_command(initial.state, "spells")
    cast = adapter.apply_command(initial.state, "cast")

    assert spells.log == ["You do not know any spells yet."]
    assert cast.log == ["You don't have any spells!"]


def test_placeholder_wall_does_not_consume_turn() -> None:
    adapter = PlaceholderGameAdapter()
    initial = adapter.restart()

    blocked = adapter.apply_command(initial.state, "north")

    assert blocked.state["x"] == initial.state["x"]
    assert blocked.state["y"] == initial.state["y"]
    assert blocked.state["turn"] == 0
    assert blocked.log == ["A wall blocks your path."]


def test_placeholder_display_size_changes_viewport() -> None:
    adapter = PlaceholderGameAdapter()

    medium = adapter.restart(map_view="medium")
    wide = adapter.restart(map_view="wide")
    max_view = adapter.restart(map_view="max")

    assert "Display:" not in medium.screen
    assert "Legend:" not in medium.screen
    assert medium.status["viewport"] == {"width": 21, "height": 11}
    assert wide.status["viewport"] == {"width": 31, "height": 15}
    assert max_view.status["viewport"] == {"width": 52, "height": 23}
    assert len(max_view.screen) > len(wide.screen) > len(medium.screen)
