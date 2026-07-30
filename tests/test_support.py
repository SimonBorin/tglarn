from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram import Dispatcher
from tglarn_bot.handlers import register_handlers
from tglarn_bot.keyboards import (
    CallbackData,
    game_menu_keyboard,
    support_keyboard,
)
from tglarn_bot.payments import (
    SUPPORT_STAR_AMOUNTS,
    is_valid_support_checkout,
    parse_support_invoice_payload,
    support_invoice_payload,
)
from tglarn_bot.texts import SUPPORT_TEXT


def _registered_handlers(dispatcher, observer_name):
    router = dispatcher.sub_routers[0]
    return {
        handler.callback.__name__: handler.callback
        for handler in router.observers[observer_name].handlers
    }


def _dispatcher_with_handlers(session_service=None):
    dispatcher = Dispatcher()
    settings = SimpleNamespace(repository_url="https://example.invalid/repository")
    register_handlers(dispatcher, settings, session_service or SimpleNamespace())
    return dispatcher


def test_game_menu_places_support_strictly_between_legend_and_main_menu() -> None:
    tail_rows = game_menu_keyboard().inline_keyboard[-4:]

    assert [[button.text for button in row] for row in tail_rows] == [
        ["Legend"],
        ["⭐ Support Development ⭐"],
        ["Main Menu"],
        ["Back to Game"],
    ]
    assert tail_rows[1][0].callback_data == CallbackData.SUPPORT


def test_support_submenu_contains_kofi_url_and_all_stars_options() -> None:
    buttons = [button for row in support_keyboard().inline_keyboard for button in row]

    assert [button.url for button in buttons if button.url] == [
        "https://ko-fi.com/mrblooomberg"
    ]
    assert {
        button.callback_data
        for button in buttons
        if button.callback_data
        and button.callback_data.startswith(CallbackData.SUPPORT_STARS_PREFIX)
    } == {
        f"{CallbackData.SUPPORT_STARS_PREFIX}{amount}"
        for amount in SUPPORT_STAR_AMOUNTS
    }
    assert SUPPORT_STAR_AMOUNTS == (50, 100, 250)


@pytest.mark.asyncio
async def test_support_callback_opens_support_submenu() -> None:
    session_service = SimpleNamespace(set_active_game_message=AsyncMock())
    dispatcher = _dispatcher_with_handlers(session_service)
    handler = _registered_handlers(dispatcher, "callback_query")["support_callback"]
    message = SimpleNamespace(
        edit_text=AsyncMock(),
        photo=None,
        chat=SimpleNamespace(id=2002),
        message_id=3003,
    )
    callback = SimpleNamespace(
        answer=AsyncMock(),
        message=message,
        from_user=SimpleNamespace(id=1001),
    )

    await handler(callback)

    callback.answer.assert_awaited_once_with()
    message.edit_text.assert_awaited_once()
    text = message.edit_text.await_args.args[0]
    markup = message.edit_text.await_args.kwargs["reply_markup"]
    assert text == SUPPORT_TEXT
    assert markup == support_keyboard()


@pytest.mark.asyncio
@pytest.mark.parametrize("amount", SUPPORT_STAR_AMOUNTS)
async def test_stars_callback_sends_exact_xtr_invoice(amount: int) -> None:
    dispatcher = _dispatcher_with_handlers()
    handler = _registered_handlers(dispatcher, "callback_query")["support_stars_callback"]
    message = SimpleNamespace(answer_invoice=AsyncMock())
    callback = SimpleNamespace(
        data=f"{CallbackData.SUPPORT_STARS_PREFIX}{amount}",
        answer=AsyncMock(),
        message=message,
    )

    await handler(callback)

    message.answer_invoice.assert_awaited_once()
    invoice = message.answer_invoice.await_args.kwargs
    assert invoice["currency"] == "XTR"
    assert invoice["provider_token"] == ""
    assert invoice["payload"] == f"tglarn-support:{amount}"
    assert [(price.label, price.amount) for price in invoice["prices"]] == [
        ("Support TGLarn", amount)
    ]


@pytest.mark.parametrize("amount", SUPPORT_STAR_AMOUNTS)
def test_support_invoice_payload_matches_selected_stars_amount(amount: int) -> None:
    payload = support_invoice_payload(amount)

    assert payload == f"tglarn-support:{amount}"
    assert parse_support_invoice_payload(payload) == amount


@pytest.mark.parametrize(
    ("payload", "currency", "total_amount", "expected"),
    [
        ("tglarn-support:100", "XTR", 100, True),
        ("tglarn-support:100", "USD", 100, False),
        ("untrusted:100", "XTR", 100, False),
        ("tglarn-support:100", "XTR", 50, False),
        ("tglarn-support:999", "XTR", 999, False),
    ],
)
def test_support_pre_checkout_validation_rejects_tampering(
    payload: str,
    currency: str,
    total_amount: int,
    expected: bool,
) -> None:
    assert is_valid_support_checkout(payload, currency, total_amount) is expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "currency", "total_amount", "expected"),
    [
        ("tglarn-support:100", "XTR", 100, True),
        ("tglarn-support:100", "USD", 100, False),
        ("untrusted:100", "XTR", 100, False),
        ("tglarn-support:100", "XTR", 50, False),
        ("tglarn-support:999", "XTR", 999, False),
    ],
)
async def test_pre_checkout_handler_accepts_only_valid_invoice(
    payload: str,
    currency: str,
    total_amount: int,
    expected: bool,
) -> None:
    dispatcher = _dispatcher_with_handlers()
    handler = _registered_handlers(dispatcher, "pre_checkout_query")[
        "support_pre_checkout_query"
    ]
    query = SimpleNamespace(
        invoice_payload=payload,
        currency=currency,
        total_amount=total_amount,
        answer=AsyncMock(),
    )

    await handler(query)

    answer = query.answer.await_args.kwargs
    assert answer["ok"] is expected
    if expected:
        assert answer["error_message"] is None
    else:
        assert answer["error_message"]


@pytest.mark.asyncio
async def test_successful_payment_sends_thanks_and_records_payment() -> None:
    session_service = SimpleNamespace(record_support_payment=AsyncMock())
    dispatcher = _dispatcher_with_handlers(session_service)
    handler = _registered_handlers(dispatcher, "message")["successful_support_payment"]
    payment = SimpleNamespace(
        invoice_payload="tglarn-support:100",
        currency="XTR",
        total_amount=100,
        telegram_payment_charge_id="telegram-charge",
        provider_payment_charge_id="",
    )
    message = SimpleNamespace(
        successful_payment=payment,
        from_user=SimpleNamespace(id=1001),
        answer=AsyncMock(),
    )

    await handler(message)

    session_service.record_support_payment.assert_awaited_once_with(
        telegram_user_id=1001,
        invoice_payload="tglarn-support:100",
        currency="XTR",
        total_amount=100,
        telegram_payment_charge_id="telegram-charge",
        provider_payment_charge_id="",
    )
    message.answer.assert_awaited_once()
    assert "Thank you" in message.answer.await_args.args[0]
    assert "100 Telegram Stars" in message.answer.await_args.args[0]


def test_payment_support_and_terms_commands_are_registered() -> None:
    dispatcher = _dispatcher_with_handlers()
    router = dispatcher.sub_routers[0]
    registered_commands = {
        handler.callback.__name__: tuple(handler.filters[0].callback.commands)
        for handler in router.observers["message"].handlers
        if getattr(handler.filters[0].callback, "commands", None)
    }

    assert registered_commands["pay_support_command"] == ("paysupport",)
    assert registered_commands["terms_command"] == ("terms",)
