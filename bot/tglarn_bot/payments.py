"""Telegram Stars support-payment helpers."""

SUPPORT_STAR_AMOUNTS = (50, 100, 250)
_SUPPORT_PAYLOAD_PREFIX = "tglarn-support:"


def support_invoice_payload(amount: int) -> str:
    """Build a payment payload for one of the supported Star amounts."""
    if amount not in SUPPORT_STAR_AMOUNTS:
        raise ValueError("Unsupported Telegram Stars amount")
    return f"{_SUPPORT_PAYLOAD_PREFIX}{amount}"


def parse_support_invoice_payload(payload: str) -> int | None:
    """Return the Star amount encoded in a valid support payload."""
    if not payload.startswith(_SUPPORT_PAYLOAD_PREFIX):
        return None
    raw_amount = payload.removeprefix(_SUPPORT_PAYLOAD_PREFIX)
    if not raw_amount.isdecimal():
        return None
    amount = int(raw_amount)
    return amount if amount in SUPPORT_STAR_AMOUNTS else None


def is_valid_support_checkout(payload: str, currency: str, total_amount: int) -> bool:
    """Validate the immutable fields Telegram returns before checkout."""
    amount = parse_support_invoice_payload(payload)
    return currency == "XTR" and amount is not None and total_amount == amount
