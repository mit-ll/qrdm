# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT
"""QRDM-specific exception classes."""

from __future__ import annotations

from typing import Optional

__all__ = ["QRDMError", "QRDecodeError", "QREncodeError"]


class QRDMError(Exception):
    """Base exception for all QRDM operations."""

    pass


class QRDecodeError(QRDMError):
    """Unable to reconstruct a source document from an input file."""

    def __init__(
        self,
        message: str,
        *,
        missing_codes: Optional[list[int]] = None,
    ) -> None:
        super().__init__(message)
        self.missing_codes = missing_codes


class QREncodeError(QRDMError):
    """Unable to construct a QR PDF from an input source document."""

    pass
