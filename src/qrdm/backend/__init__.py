# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT
"""FastAPI Application providing QR encoding and decoding endpoint functions."""

from qrdm.backend.config import configure_app_logging

configure_app_logging()

try:
    from qrdm.backend.main import app
except ImportError as e:
    raise ImportError(
        f"Could not import backend dependency {e.name}. "
        "You can fix this by running `pip install qrdm[backend]`."
    ) from e

__all__ = ["app"]
