"""Shared service and persistence exceptions."""


class SessionConflictError(RuntimeError):
    """Raised when optimistic session state locking rejects a stale write."""

