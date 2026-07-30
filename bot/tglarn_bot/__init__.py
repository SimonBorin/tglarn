"""Telegram bot package for TGLarn."""

import os

__all__ = ["__version__"]

__version__ = os.getenv("TGLARN_VERSION", "0.1.0")
