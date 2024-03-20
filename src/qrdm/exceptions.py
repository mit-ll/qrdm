# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT
"""QRDM-specific exception classes."""

__all__ = ["QRDecodeError", "QREncodeError"]


class QRDecodeError(Exception):
    """Unable to reconstruct a source document from an input file."""

    pass


class QREncodeError(Exception):
    """Unable to construct a QR PDF from an input source document."""

    pass
