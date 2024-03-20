# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT
"""Data structures for representing and serializing QR & document payload data."""
from __future__ import annotations

import base64
import json
import zlib
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from qrdm.qr import protobuf

__all__ = ["ECSettingValues", "QRMeta", "QRContent", "DocumentPayload"]


class ECSettingValues(str, Enum):
    """Valid settings for QR error correction levels."""

    L = "LOW"
    M = "MEDIUM"
    Q = "QUARTILE"
    H = "HIGH"


class QRMeta(BaseModel):
    """Metadata of individual QRDM QR codes, used for document reconstruction."""

    document_hash: int = Field(ge=0)
    sequence_number: int = Field(ge=0)
    total_qr_codes: int = Field(gt=0)
    num_ecc: int = Field(ge=0)
    model_config = ConfigDict(frozen=True)

    @classmethod
    def _from_proto(cls, pb: protobuf.QRContent.QRMeta) -> QRMeta:
        return cls(
            document_hash=pb.document_hash,
            sequence_number=pb.sequence_number,
            total_qr_codes=pb.total_qr_codes,
            num_ecc=pb.num_ecc,
        )

    def _to_proto(self) -> protobuf.QRContent.QRMeta:
        return protobuf.QRContent.QRMeta(**self.model_dump())


class QRContent(BaseModel):
    """Data content of individual QRDM QR codes."""

    meta: QRMeta
    doc_fragment: bytes = b""

    @classmethod
    def model_validate_protobuf_bytes(cls, b: bytes) -> QRContent:
        """Parse serialized binary data into a `QRContent`."""
        pb = protobuf.QRContent()
        pb.ParseFromString(b)
        meta = QRMeta._from_proto(pb.meta)
        return cls(meta=meta, doc_fragment=pb.doc_fragment)

    @classmethod
    def model_validate_b85_bytes(cls, b: bytes) -> QRContent:
        """Parse b85-encodeded & serialized binary data into a `QRContent`."""
        decoded_bytes = base64.b85decode(b)
        return cls.model_validate_protobuf_bytes(decoded_bytes)

    def _to_proto(self) -> protobuf.QRContent:
        meta_pb = self.meta._to_proto()
        return protobuf.QRContent(meta=meta_pb, doc_fragment=self.doc_fragment)

    def model_dump_protobuf_bytes(self) -> bytes:
        """Serialize this object into binary data."""
        pb = self._to_proto()
        return pb.SerializeToString()

    def model_dump_b85_bytes(self) -> bytes:
        """Serialize this object into b85-encoded binary data."""
        raw_bytes = self.model_dump_protobuf_bytes()
        return base64.b85encode(raw_bytes)


class DocumentPayload(BaseModel):
    """Represents and serializes QRDM source documents."""

    content: str = ""
    metadata: JsonValue = None
    model_config = ConfigDict(frozen=True)

    @classmethod
    def model_validate_protobuf_bytes(cls, b: bytes) -> DocumentPayload:
        """Parse serialized binary data into a `DocumentPayload`."""
        pb = protobuf.DocumentPayload()
        pb.ParseFromString(b)
        meta_json = None
        if len(pb.metadata) > 0:
            meta_json = json.loads(pb.metadata)
        if pb.data_type != protobuf.DocumentPayload.DataType.UTF8_STRING:
            raise ValueError("Unknown data type")
        return cls(content=pb.content.decode("utf-8"), metadata=meta_json)

    @classmethod
    def model_validate_compressed_bytes(cls, b: bytes) -> DocumentPayload:
        """Parse serialized and compressed binary data into a `DocumentPayload`."""
        inflated_bytes = zlib.decompress(b)
        return cls.model_validate_protobuf_bytes(inflated_bytes)

    def _to_proto(self) -> protobuf.DocumentPayload:
        meta_str = None
        if self.metadata is not None:
            meta_str = json.dumps(self.metadata)
        return protobuf.DocumentPayload(
            content=self.content.encode("utf-8"),
            metadata=meta_str,
            data_type=protobuf.DocumentPayload.DataType.UTF8_STRING,
        )

    def model_dump_protobuf_bytes(self) -> bytes:
        """Serialize this object into binary data."""
        pb = self._to_proto()
        return pb.SerializeToString()

    def model_dump_compressed_bytes(self) -> bytes:
        """Serialize this object into compressed binary data."""
        raw_bytes = self.model_dump_protobuf_bytes()
        return zlib.compress(raw_bytes, level=zlib.Z_BEST_COMPRESSION)
