# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT
"""Protobuf definitions and classes for serialization of QRDM documents and QR codes."""
from qrdm.qr.protobuf.qrdm_pb2 import DocumentPayload, QRContent

__all__ = ["QRContent", "DocumentPayload", "PROTOBUF_RESERVED_LEN"]

MaxLenQrMeta = QRContent.QRMeta(
    document_hash=2**64 - 1,
    sequence_number=2**32 - 1,
    total_qr_codes=2**32 - 1,
    num_ecc=2**32 - 1,
)

MAX_VARINT_LEN = 10
MAX_QRMETA_LEN = MaxLenQrMeta.ByteSize()
# Each length-delimited field (i.e. the QRMeta submessage and the bytes-type payload)
# field of the message includes a "tag" and "length", each as a varint
PROTOBUF_RESERVED_LEN = MAX_QRMETA_LEN + 4 * MAX_VARINT_LEN
