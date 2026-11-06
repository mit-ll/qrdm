# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT
"""Generate QRDM PDFs from source documents."""

from __future__ import annotations

import hashlib
import io
import logging
import shutil
import warnings
from collections.abc import Iterator
from math import ceil
from pathlib import Path
from typing import overload

import qrcode.image.svg as qr_svg
import reedsolo
import structlog
from charset_normalizer import from_bytes
from pydantic import JsonValue
from qrcode.main import QRCode
from structlog import contextvars

import qrdm.qr._const as qr_const
from qrdm.exceptions import QREncodeError
from qrdm.models import DocumentPayload, ECSettingValues, QRContent, QRMeta
from qrdm.qr.pdf_writer import generate_pdf_pages
from qrdm.qr.protobuf import PROTOBUF_RESERVED_LEN

__all__ = ["encode_qr_pdf"]
logger = logging.getLogger(__name__)

# Sequence number recorded as 32-bit uint
N_MAX_QRS = 2**32

PathLike = str | Path


@overload
def encode_qr_pdf(
    document_content: str,
    *,
    path: None = ...,
    header_text: str = ...,
    metadata: JsonValue | None = ...,
    document_name: str | None = ...,
    encode_ec_codes: bool = ...,
    error_tolerance: str | ECSettingValues | None = ...,
    include_text: bool = ...,
    include_timestamp: bool = ...,
    minimal_mode: bool = ...,
    preset: str | None = ...,
    strict: bool = ...,
    max_payload_size: int = ...,
    passphrase: str | None = ...,
) -> bytes: ...


@overload
def encode_qr_pdf(
    document_content: str,
    *,
    path: PathLike | io.BufferedIOBase = ...,
    header_text: str = ...,
    metadata: JsonValue | None = ...,
    document_name: str | None = ...,
    encode_ec_codes: bool = ...,
    error_tolerance: str | ECSettingValues | None = ...,
    include_text: bool = ...,
    include_timestamp: bool = ...,
    minimal_mode: bool = ...,
    preset: str | None = ...,
    strict: bool = ...,
    max_payload_size: int = ...,
    passphrase: str | None = ...,
) -> None: ...


PRESETS = {
    "default": {
        "box_size": qr_const.BOX_SIZE,
        "qr_size": qr_const.QR_SIZE,
        "error_tolerance": ECSettingValues.M,
        "ec_proportion": qr_const.EC_CODE_PROPORTION,
    },
    "photo": {
        "box_size": 8,
        "qr_size": 20,
        "error_tolerance": ECSettingValues.Q,
        "ec_proportion": 0.25,
    },
    "flatbed": {
        "box_size": 5,
        "qr_size": 24,
        "error_tolerance": ECSettingValues.M,
        "ec_proportion": 0.15,
    },
}


def encode_qr_pdf(
    document_content: str,
    *,
    path: PathLike | io.BufferedIOBase | None = None,
    header_text: str = "",
    metadata: JsonValue | None = None,
    document_name: str | None = None,
    encode_ec_codes: bool = True,
    error_tolerance: str | ECSettingValues | None = None,
    include_text: bool = False,
    include_timestamp: bool = True,
    minimal_mode: bool = False,
    preset: str | None = None,
    strict: bool = False,
    max_payload_size: int = 5 * 1024 * 1024,
    passphrase: str | None = None,
) -> bytes | None:
    """Convert a plaintext document to a PDF containing the document encoded as QR codes.

    Parameters
    ----------
    document_content: str
        Document to be QR-encoded, as a python string.
    path: str, path object, file-like object, or `None`, optional
        String, path object (implementing os.PathLike[str]), or file-like object
        implementing a binary write() function. If None, the result is returned as
        bytes. Defaults to `None`.
    header_text: str, optional
        Text to include as header & footer of QR PDF. Defaults to `""`.
    metadata: JsonValue, optional
        JSON-encodable data that is encoded alongside the document contents in the QR
        PDF. (I.e. may be a JSON-scalar `[str|bool|int|float]` or a `dict[str,
        JsonValue]`)
    document_name: str, optional
        Name of the original file or document, to label output PDF.
    encode_ec_codes: bool, optional
        Whether to include additional error-correcting QR codes. These are useful when
        individual QR codes fail to scan.
    error_tolerance: One of `"LOW", "MEDIUM", "QUARTILE", "HIGH"`, optional
        Error correction level of the individual QR codes. Defaults to `"MEDIUM"`.
    include_text: bool, optional
        Whether to print the plaintext document content underneath the QR codes.
        Defaults to `False` (opt-in) to preserve privacy.
    include_timestamp: bool, optional
        Whether to include the UTC render timestamp in the page footer. Set to
        `False` for deterministic PDF output. Defaults to `True`.
    minimal_mode: bool, optional
        When `True`, print only filename, hash, and page numbers — no footer text
        or caption. Forces `include_text=False` and `include_timestamp=False`.
        Defaults to `False`.

    Returns
    -------
    File data as bytes if the `path` argument is not provided, otherwise `None`.

    Examples
    --------
    >>> file_data = qrdm.encode_qr_pdf("This returns bytes directly", path=None)
    >>> qrdm.encode_qr_pdf("This is being written directly to a file", path="qr.pdf")
    >>> with open("stream.pdf", "wb") as f:
    ...     qrdm.encode_qr_pdf("This is being written to a file-like stream", path=f)

    """
    buf: io.BufferedIOBase
    if path is None or isinstance(path, (str, Path)):
        buf = io.BytesIO()
    else:
        buf = path

    cfg = PRESETS.get(preset or "default", PRESETS["default"])
    if preset and preset not in PRESETS:
        raise ValueError(
            f"Unknown preset '{preset}'. Valid presets: {list(PRESETS.keys())}"
        )

    if error_tolerance is not None:
        if isinstance(error_tolerance, str):
            error_tolerance = ECSettingValues(error_tolerance)
    else:
        error_tolerance = cfg["error_tolerance"]

    box_size = cfg["box_size"]
    qr_size = cfg["qr_size"]
    ec_proportion = cfg["ec_proportion"]

    if strict:
        _validate_strict(document_content, max_size=max_payload_size)

    document_payload = DocumentPayload(content=document_content, metadata=metadata)
    qr_payloads = generate_qr_payloads(
        document_payload,
        encode_ec_codes=encode_ec_codes,
        error_tolerance=error_tolerance,
        qr_size=qr_size,
        ec_proportion=ec_proportion,
        passphrase=passphrase,
    )
    qr_codes = generate_qr_codes(
        qr_payloads, error_tolerance=error_tolerance, box_size=box_size
    )

    generate_pdf_pages(
        qr_codes,
        buf=buf,
        header_text=header_text,
        qr_text=(
            document_payload.content if (include_text and not minimal_mode) else None
        ),
        filename=document_name,
        doc_hash=document_payload.sha256,
        include_timestamp=include_timestamp,
        minimal_mode=minimal_mode,
    )
    if path is None or isinstance(path, (str, Path)):
        buf.seek(0)
        if isinstance(path, (str, Path)):
            with open(path, "wb") as f:
                shutil.copyfileobj(buf, f)
        else:
            return buf.read()


def _validate_strict_bytes(file_data: bytes, max_size: int = 5 * 1024 * 1024) -> None:
    """Validate raw binary input against strict policy."""
    if len(file_data) > max_size:
        raise QREncodeError(
            f"Strict mode violation: file size ({len(file_data)} bytes) exceeds limit ({max_size} bytes)"
        )
    if b"\x00" in file_data:
        raise QREncodeError(
            "Strict mode violation: NUL byte (0x00) detected in input data"
        )

    disallowed_signatures = [
        (b"PK\x03\x04", "ZIP / Office OpenXML"),
        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "MS Office Compound Document (OLE2)"),
        (b"%PDF", "PDF document"),
        (b"MZ", "DOS/PE executable"),
        (b"\x7fELF", "ELF binary executable"),
    ]
    for sig, name in disallowed_signatures:
        if file_data.startswith(sig):
            raise QREncodeError(
                f"Strict mode violation: disallowed binary signature detected ({name})"
            )


def _validate_strict(content: str, max_size: int = 5 * 1024 * 1024) -> None:
    """Validate document content against strict payload policy."""
    raw_bytes = content.encode("utf-8")
    _validate_strict_bytes(raw_bytes, max_size=max_size)

    # Check control characters
    for ch in content:
        code = ord(ch)
        if code < 32 and ch not in ("\n", "\r", "\t"):
            raise QREncodeError(
                f"Strict mode violation: disallowed control character (code {code}) in text"
            )


def get_file_content(
    file_data: bytes,
    encoding: str | None = None,
    *,
    strict: bool = False,
    max_size: int = 5 * 1024 * 1024,
) -> str:
    """Extract text file contents from binary file data, with optional encoding detection.

    Parameters
    ----------
    file_data: bytes
        Binary file data
    encoding: str or `None`, optional
        Encoding used to decode the document file data into a string. If not provided,
        defaults to automatic detection via the `charset_normalizer` package. Valid
        encodings can be found in the Python documentation:
        https://docs.python.org/3.9/library/codecs.html#standard-encodings
    strict: bool, optional
        If True, rejects binary signatures, NUL bytes, size limits, and invalid UTF-8.
    max_size: int, optional
        Maximum allowed byte size in strict mode.

    Returns
    -------
    file_content: str
        Decoded file contents

    """
    if strict:
        _validate_strict_bytes(file_data, max_size=max_size)
        if encoding is None:
            try:
                file_content = file_data.decode("utf-8")
                encoding = "utf-8"
            except UnicodeDecodeError as e:
                raise QREncodeError(
                    f"Strict mode violation: invalid UTF-8 content: {e}"
                ) from e
            _validate_strict(file_content, max_size=max_size)
            return file_content

    input_file_info = structlog.contextvars.get_contextvars().get("input_file", {})
    input_file_info["autodetect_encoding"] = encoding is None
    if encoding is None:
        decoded_content = from_bytes(file_data).best()
        if decoded_content is None:
            raise QREncodeError("Could not determine valid encoding for file contents")
        encoding = decoded_content.encoding
        file_content = str(decoded_content)
    else:
        try:
            file_content = file_data.decode(encoding)
        except ValueError as e:
            raise QREncodeError(
                f"Could not decode file with encoding: {encoding}"
            ) from e
    logger.debug("Decoded file contents with: %s", encoding)
    input_file_info["encoding"] = encoding
    structlog.contextvars.bind_contextvars(input_file=input_file_info)
    if strict:
        _validate_strict(file_content, max_size=max_size)
    return file_content


def generate_qr_payloads(
    document_content: DocumentPayload,
    *,
    encode_ec_codes: bool,
    error_tolerance: ECSettingValues = ECSettingValues.M,
    qr_size: int = qr_const.QR_SIZE,
    ec_proportion: float = qr_const.EC_CODE_PROPORTION,
    passphrase: str | None = None,
) -> list[bytes]:
    """Construct b85-encoded payloads from a document for QR code construction."""
    logger.debug("Generating QR code payloads")
    total_payload_bytes = document_content.model_dump_compressed_bytes()
    if passphrase:
        from qrdm.qr.crypto import encrypt_payload

        total_payload_bytes = encrypt_payload(total_payload_bytes, passphrase)
    logger.debug("Compressed document: %s", total_payload_bytes.hex(" ", 4))

    hash_bytes = hashlib.sha256(total_payload_bytes.strip(b"\0")).digest()
    logger.debug("Document hash (SHA-256): %s", hash_bytes.hex(" ", 4))
    document_hash = hash_bytes  # 32-byte SHA-256 digest stored as bytes

    max_qr_bytes = qr_const.QR_CAPACITIES[qr_size][error_tolerance.name]
    single_qr_payload_size = max_qr_bytes - PROTOBUF_RESERVED_LEN
    # Reduce payload size to account for b85 inflation
    single_qr_payload_size = (single_qr_payload_size // 5) * 4

    # If document is small enough to fit in a single code, skip `_split_file_content` to
    # avoid the null-byte padding
    if len(total_payload_bytes) <= single_qr_payload_size:
        payload_fragments = [total_payload_bytes]
    else:
        payload_fragments = list(
            _split_file_content(
                total_payload_bytes, maximum_length=single_qr_payload_size
            )
        )

    n_raw_fragments = len(payload_fragments)
    if encode_ec_codes:
        # Reed-Solomon encoder chunks at ~256, so we just want this fraction _per 256_
        # at most
        e = ec_proportion
        max_ecc = ceil(256 * e / (1 + e))
        num_ecc = min(max_ecc, ceil(n_raw_fragments * e))
        n_qr_expected = n_raw_fragments + (
            1 + (n_raw_fragments // (256 - num_ecc)) * num_ecc
        )
        if n_raw_fragments * (1 + e) >= 256:
            warnings.warn(
                f"Input data requires {n_qr_expected} QR codes to encode. "
                "Error-correction requires significantly longer processing above 256 codes."
            )
    else:
        num_ecc = 0
        n_qr_expected = n_raw_fragments

    if n_qr_expected >= N_MAX_QRS:
        msg = (
            f"The provided input requires {n_qr_expected} QR codes to encode, which "
            f"exceeds the maximum of {N_MAX_QRS}, consider breaking the file into smaller pieces."
        )
        raise QREncodeError(msg)

    if num_ecc > 0:
        payload_fragments = _generate_ec_fragments(payload_fragments, num_ecc=num_ecc)

    total_qr_codes = len(payload_fragments)

    qr_contents: list[bytes] = []
    for sequence_number, fragment in enumerate(payload_fragments):
        qr_meta = QRMeta(
            document_hash=document_hash,
            sequence_number=sequence_number,
            total_qr_codes=total_qr_codes,
            num_ecc=num_ecc,
        )
        logger.debug(
            "Constructing QR #%d payload with metadata: {%s}",
            sequence_number,
            dict(qr_meta),
        )
        logger.debug(
            "Constructing QR #%d payload with content: %s",
            sequence_number,
            fragment.hex(" ", -4),
        )
        qr_content = QRContent(meta=qr_meta, doc_fragment=fragment)
        qr_b64_content = qr_content.model_dump_b85_bytes()
        logger.debug("QR b85-encoded size: %d", len(qr_b64_content))
        qr_contents.append(qr_b64_content)

        contextvars.bind_contextvars(
            qr_info={
                "encode_ec_codes": encode_ec_codes,
                "qr_meta": qr_meta.model_dump(exclude={"sequence_number"}),
            }
        )

    return qr_contents


def _split_file_content(content: bytes, *, maximum_length: int) -> Iterator[bytes]:
    """Split an array of bytes into chunks of *equal* length n, null padding when required.

    Equal-length chunks are required for generating error-correction QR codes.
    """
    while len(content) > maximum_length:
        yield content[:maximum_length]
        content = content[maximum_length:]
    yield content + b"\0" * (maximum_length - len(content))


def _generate_ec_fragments(
    payload_fragments: list[bytes], *, num_ecc: int
) -> list[bytes]:
    """Construct arrays of error-correction data from a list of QR payloads."""
    logger.debug("Constructing %d error correction QR codes", num_ecc)
    groups = [bytes(x) for x in zip(*payload_fragments)]
    try:
        encoding_rs_codec = reedsolo.RSCodec(num_ecc)
        output_fragments = [
            bytes(x)
            for x in zip(*(encoding_rs_codec.encode(group) for group in groups))
        ]
    except ValueError as e:
        raise QREncodeError("Error: Could not construct error-correction codes.") from e
    return output_fragments


def generate_qr_codes(
    qr_contents: list[bytes],
    error_tolerance: ECSettingValues = ECSettingValues.M,
    box_size: int = qr_const.BOX_SIZE,
) -> list[QRCode]:
    """Generate a sequence of QRCodes from ASCII payloads."""
    logger.debug("Generating QR codes")
    image_factory = qr_svg.SvgPathImage
    qr_codes = []
    for code_content in qr_contents:
        code = QRCode(
            version=None,
            error_correction=qr_const.ErrorCorrectionLevel[error_tolerance.name],
            box_size=box_size,
            image_factory=image_factory,
            border=0,
        )
        logger.debug("Constructing QR with payload: " f"{code_content[:32]!r}...")
        code.add_data(code_content, optimize=0)
        code.make(fit=True)
        logger.debug(f"Code size: {code.version}")
        qr_codes.append(code)
    return qr_codes
