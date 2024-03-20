# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT
from typing import ClassVar as _ClassVar
from typing import Mapping as _Mapping
from typing import Optional as _Optional
from typing import Union as _Union

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper

DESCRIPTOR: _descriptor.FileDescriptor

class QRContent(_message.Message):
    __slots__ = ("meta", "doc_fragment")

    class QRMeta(_message.Message):
        __slots__ = ("document_hash", "sequence_number", "total_qr_codes", "num_ecc")
        DOCUMENT_HASH_FIELD_NUMBER: _ClassVar[int]
        SEQUENCE_NUMBER_FIELD_NUMBER: _ClassVar[int]
        TOTAL_QR_CODES_FIELD_NUMBER: _ClassVar[int]
        NUM_ECC_FIELD_NUMBER: _ClassVar[int]
        document_hash: int
        sequence_number: int
        total_qr_codes: int
        num_ecc: int
        def __init__(
            self,
            document_hash: _Optional[int] = ...,
            sequence_number: _Optional[int] = ...,
            total_qr_codes: _Optional[int] = ...,
            num_ecc: _Optional[int] = ...,
        ) -> None: ...

    META_FIELD_NUMBER: _ClassVar[int]
    DOC_FRAGMENT_FIELD_NUMBER: _ClassVar[int]
    meta: QRContent.QRMeta
    doc_fragment: bytes
    def __init__(
        self,
        meta: _Optional[_Union[QRContent.QRMeta, _Mapping]] = ...,
        doc_fragment: _Optional[bytes] = ...,
    ) -> None: ...

class DocumentPayload(_message.Message):
    __slots__ = ("content", "metadata", "data_type")

    class DataType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        UTF8_STRING: _ClassVar[DocumentPayload.DataType]

    UTF8_STRING: DocumentPayload.DataType
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    DATA_TYPE_FIELD_NUMBER: _ClassVar[int]
    content: bytes
    metadata: str
    data_type: DocumentPayload.DataType
    def __init__(
        self,
        content: _Optional[bytes] = ...,
        metadata: _Optional[str] = ...,
        data_type: _Optional[_Union[DocumentPayload.DataType, str]] = ...,
    ) -> None: ...
