# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT
"""QRDM provides tools for encoding and decoding documents as a series of QR codes."""

__version__ = "2.2.0"

from qrdm.models import VerifyResult
from qrdm.qr.decode import decode_qr_pdf, verify_qr_pdf
from qrdm.qr.encode import encode_qr_pdf

__all__ = ["VerifyResult", "decode_qr_pdf", "encode_qr_pdf", "verify_qr_pdf"]
