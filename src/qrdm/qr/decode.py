# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT
"""Recover source documents from QRDM PDFs."""

from __future__ import annotations

import concurrent.futures
import ctypes.util
import hashlib
import io
import logging
import multiprocessing
import platform
import sys
import time
from itertools import chain
from pathlib import Path

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf

if platform.system() == "Darwin":
    # On macOS, ctypes.util.find_library("zbar") often fails to locate libraries
    # in standard Homebrew, Conda, or MacPorts locations.
    _orig_find_library = ctypes.util.find_library

    def _mac_find_library(name: str) -> str | None:
        res = _orig_find_library(name)
        if res:
            return res
        if name == "zbar":
            candidates = [
                "/opt/homebrew/lib/libzbar.dylib",
                "/usr/local/lib/libzbar.dylib",
                "/opt/miniconda3/lib/libzbar.dylib",
                "/opt/local/lib/libzbar.dylib",
                str(Path(sys.prefix) / "lib" / "libzbar.dylib"),
            ]
            for candidate in candidates:
                if Path(candidate).is_file():
                    return candidate
        return None

    ctypes.util.find_library = _mac_find_library

import reedsolo
import structlog.contextvars
from PIL import Image, ImageFilter
from pyzbar.pyzbar import Decoded, ZBarSymbol, decode

from qrdm.exceptions import QRDecodeError
from qrdm.models import DocumentPayload, QRContent, VerifyResult

__all__ = ["decode_qr_pdf", "verify_qr_pdf"]
logger = logging.getLogger(__name__)


def _open_pdf_document(input_file: str | Path | bytes | io.BytesIO) -> pymupdf.Document:
    """Open a PDF document from a path, raw bytes, or stream with safe rewinding."""
    if isinstance(input_file, (str, Path)):
        return pymupdf.open(input_file, filetype="pdf")
    if isinstance(input_file, bytes):
        return pymupdf.open(stream=io.BytesIO(input_file), filetype="pdf")
    if hasattr(input_file, "seek"):
        input_file.seek(0)
    return pymupdf.open(stream=input_file, filetype="pdf")


def decode_qr_pdf(
    input_file: str | Path | bytes | io.BytesIO,
    *,
    reject_unexpected_codes: bool = False,
    strict: bool = False,
    max_payload_size: int = 5 * 1024 * 1024,
    dpi: int | None = None,
    passphrase: str | None = None,
) -> DocumentPayload:
    """Decode a QRDM PDF into the original document content and metadata.

    Parameters
    ----------
    input_file: Path-like, bytes, or io.BytesIO
        Path to PDF file, binary stream, or bytes containing the file contents of the QR
        PDF. (e.g. as returned by `encode_qr_pdf`) Passed as input to `pymupdf.open`
        function provided by PyMuPDF.
    reject_unexpected_codes: bool, optional
        Reject non-QRDM barcodes on pages. Defaults to False.
    strict: bool, optional
        Enforce strict payload validation policy. Defaults to False.
    max_payload_size: int, optional
        Maximum allowed decoded payload size in bytes. Defaults to 5 MB.
    dpi: int, optional
        Explicit rendering resolution in DPI. If None (default), uses adaptive
        two-tier resolution: fast 150 DPI pass first, falling back to 300 DPI
        if degraded or partial codes require higher resolution.

    Returns
    -------
    decoded_document: DocumentPayload
        A Pydantic model containing the encoded document & metadata, with
        attributes:

            - content: str - Source document contents
            - metadata: JsonValue, optional - Document metadata, as provided to the
              `metadata` argument of the encoding.

    Raises
    ------
    QRDecodeError
        If no QR codes are detected in the PDF, if insufficient QR codes are
        recovered, or if checksum verification fails.

    Examples
    --------
    >>> qrdm.encode_qr_pdf(
    ...     "Lorem ipsum dolor sit amet. 😎",
    ...     metadata={"example": True},
    ...     path="example_qr_pdf.pdf",
    ... )
    >>> qrdm.decode_qr_pdf("example_qr_pdf.pdf")
    DocumentPayload(content='Lorem ipsum dolor sit amet. 😎', metadata={'example': True})

    """

    def _attempt_decode(target_dpi: int) -> tuple[DocumentPayload | None, int]:
        with _open_pdf_document(input_file) as doc:
            extracted_images = _extract_page_images(doc, dpi=target_dpi)
        extracted_contents = _extract_qr_contents_from_images(
            extracted_images, reject_unexpected_codes=reject_unexpected_codes
        )
        if len(extracted_contents) == 0:
            return None, 0
        if not _sufficient_decodes(extracted_contents):
            return None, len(extracted_contents)
        try:
            doc_payload = _reconstruct_document_payload(
                extracted_contents=extracted_contents, passphrase=passphrase
            )
            if strict:
                _validate_strict_payload(doc_payload.content, max_size=max_payload_size)
            return doc_payload, len(extracted_contents)
        except Exception:  # noqa: BLE001
            return None, len(extracted_contents)

    # Adaptive DPI: if dpi is not specified, attempt 150 DPI first for ~3x speedup.
    # If 150 DPI does not recover all necessary codes, fall back to 300 DPI.
    if dpi is None:
        fast_doc, count = _attempt_decode(150)
        if fast_doc is not None:
            return fast_doc
        logger.debug(
            "Adaptive DPI: 150 DPI pass incomplete (%d codes found), falling back to 300 DPI",
            count,
        )
        target_dpi = 300
    else:
        target_dpi = dpi

    with _open_pdf_document(input_file) as doc:
        extracted_images = _extract_page_images(doc, dpi=target_dpi)
    extracted_contents = _extract_qr_contents_from_images(
        extracted_images, reject_unexpected_codes=reject_unexpected_codes
    )
    logger.debug(f"Number of extracted payloads: {len(extracted_contents)}")

    if len(extracted_contents) == 0:
        raise QRDecodeError("Failed to extract any QR data from input document")

    try:
        logger.debug("Reconstructing QR Data")
        decoded_document = _reconstruct_document_payload(
            extracted_contents=extracted_contents, passphrase=passphrase
        )
    except Exception:
        msg = f"ERROR: Failed to decode PDF, found {len(extracted_contents)} QR codes"
        logger.error(msg)
        raise

    if strict:
        _validate_strict_payload(decoded_document.content, max_size=max_payload_size)

    return decoded_document


def _validate_strict_payload(content: str, max_size: int = 5 * 1024 * 1024) -> None:
    """Validate decoded payload against strict policy."""
    raw_bytes = content.encode("utf-8")
    if len(raw_bytes) > max_size:
        raise QRDecodeError(
            f"Strict mode violation: payload size ({len(raw_bytes)} bytes) exceeds limit ({max_size} bytes)"
        )
    if "\x00" in content:
        raise QRDecodeError(
            "Strict mode violation: NUL byte (0x00) detected in decoded payload"
        )

    disallowed_signatures = [
        (b"PK\x03\x04", "ZIP / Office OpenXML"),
        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "MS Office Compound Document (OLE2)"),
        (b"%PDF", "PDF document"),
        (b"MZ", "DOS/PE executable"),
        (b"\x7fELF", "ELF binary executable"),
    ]
    for sig, name in disallowed_signatures:
        if raw_bytes.startswith(sig):
            raise QRDecodeError(
                f"Strict mode violation: disallowed binary signature detected ({name})"
            )


def verify_qr_pdf(
    input_file: str | Path | bytes | io.BytesIO,
    *,
    reject_unexpected_codes: bool = False,
    strict: bool = False,
    max_payload_size: int = 5 * 1024 * 1024,
    dpi: int | None = None,
    passphrase: str | None = None,
) -> VerifyResult:
    """Verify a QRDM PDF document and return a detailed report without writing files.

    Performs named checks:
      - payload_valid: whether QR payloads and Reed-Solomon symbols decode cleanly
      - hash_matches: whether the reconstructed payload matches the document SHA-256
      - code_count_correct: whether all expected sequence numbers were decoded
      - no_unexpected_codes: whether any non-QRDM or malformed barcodes were detected

    Parameters
    ----------
    input_file: Path-like, bytes, or io.BytesIO
        Path or stream to the QRDM PDF.
    reject_unexpected_codes: bool, optional
        If True, marks verification as failed if non-QRDM barcodes are found.
    strict: bool, optional
        Enforce strict payload validation policy. Defaults to False.
    max_payload_size: int, optional
        Maximum allowed decoded payload size in bytes. Defaults to 5 MB.
    dpi: int, optional
        Explicit rendering resolution in DPI. If None (default), uses adaptive
        two-tier resolution: fast 150 DPI pass first, falling back to 300 DPI
        if degraded or partial codes require higher resolution.

    Returns
    -------
    VerifyResult
        Structured verification report containing status, check flags, and metadata.
    """

    def _run_verify_at_dpi(target_dpi: int) -> VerifyResult:
        errors: list[str] = []
        non_qrdm = [0]
        try:
            with _open_pdf_document(input_file) as doc:
                extracted_images = _extract_page_images(doc, dpi=target_dpi)
        except Exception as e:  # noqa: BLE001
            return VerifyResult(
                overall=False,
                status="failed",
                payload_valid=False,
                hash_matches=False,
                code_count_correct=False,
                errors=[f"Could not open or parse PDF: {e}"],
            )

        try:
            extracted_contents = _extract_qr_contents_from_images(
                extracted_images, reject_unexpected_codes=False, non_qrdm_count=non_qrdm
            )
        except Exception as e:  # noqa: BLE001
            return VerifyResult(
                overall=False,
                status="failed",
                payload_valid=False,
                hash_matches=False,
                code_count_correct=False,
                unexpected_codes=non_qrdm[0],
                no_unexpected_codes=(non_qrdm[0] == 0),
                errors=[f"Failed to extract images or codes: {e}"],
            )

        if not extracted_contents:
            return VerifyResult(
                overall=False,
                status="failed",
                payload_valid=False,
                hash_matches=False,
                code_count_correct=False,
                unexpected_codes=non_qrdm[0],
                no_unexpected_codes=(non_qrdm[0] == 0),
                errors=["Failed to extract any QR data from input document"],
            )

        first_content = next(iter(extracted_contents.values()))
        expected_codes = first_content.meta.total_qr_codes
        missing_codes = [
            ii for ii in range(expected_codes) if ii not in extracted_contents
        ]
        code_count_correct = len(missing_codes) == 0
        no_unexpected_codes = non_qrdm[0] == 0

        try:
            decoded_doc = _reconstruct_document_payload(
                extracted_contents, passphrase=passphrase
            )
            if strict:
                _validate_strict_payload(decoded_doc.content, max_size=max_payload_size)
            payload_valid = True
            hash_matches = True
            sha256 = decoded_doc.sha256
            status = "recovered"
        except QRDecodeError as e:
            payload_valid = False
            hash_matches = False
            sha256 = ""
            status = "partial" if extracted_contents else "failed"
            errors.append(str(e))
            if e.missing_codes:
                missing_codes = e.missing_codes
        except Exception as e:  # noqa: BLE001
            payload_valid = False
            hash_matches = False
            sha256 = ""
            status = "failed"
            errors.append(str(e))

        overall = payload_valid and hash_matches
        if reject_unexpected_codes and not no_unexpected_codes:
            overall = False
            errors.append(f"Found {non_qrdm[0]} non-QRDM barcode(s) on page")

        return VerifyResult(
            overall=overall,
            status=status,
            payload_valid=payload_valid,
            hash_matches=hash_matches,
            code_count_correct=code_count_correct,
            no_unexpected_codes=no_unexpected_codes,
            missing_codes=missing_codes,
            decoded_codes=len(extracted_contents),
            expected_codes=expected_codes,
            unexpected_codes=non_qrdm[0],
            sha256=sha256,
            errors=errors,
        )

    if dpi is not None:
        return _run_verify_at_dpi(dpi)

    res_150 = _run_verify_at_dpi(150)
    if res_150.overall:
        return res_150

    logger.debug("Adaptive DPI: 150 DPI verification incomplete, retrying at 300 DPI")
    return _run_verify_at_dpi(300)


def _extract_page_images(
    doc: pymupdf.Document, dpi: int = 300, max_workers: int | None = None
) -> list[Image.Image]:
    """Render PDF pages as a sequence of PIL images in parallel."""
    logger.debug("Rendering PDF pages at %d DPI", dpi)
    num_pages = len(doc)
    if num_pages == 0:
        return []
    if num_pages == 1:
        page_pixmap: pymupdf.Pixmap = doc[0].get_pixmap(dpi=dpi)
        mode = "RGBA" if page_pixmap.alpha else "RGB"
        return [
            Image.frombytes(
                mode, [page_pixmap.width, page_pixmap.height], page_pixmap.samples
            )
        ]

    try:
        cpu_count = multiprocessing.cpu_count()
    except NotImplementedError:
        cpu_count = 4

    workers = min(max_workers or cpu_count, num_pages, 8)

    def _render_page(pno: int) -> tuple[int, Image.Image]:
        page = doc[pno]
        page_pixmap = page.get_pixmap(dpi=dpi)
        mode = "RGBA" if page_pixmap.alpha else "RGB"
        img = Image.frombytes(
            mode, [page_pixmap.width, page_pixmap.height], page_pixmap.samples
        )
        return pno, img

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        rendered = list(executor.map(_render_page, range(num_pages)))

    rendered.sort(key=lambda t: t[0])
    extracted_images = [img for _, img in rendered]
    logger.debug("Rendered %d images from PDF Document", len(extracted_images))
    return extracted_images


def _extract_qr_contents_from_images(
    images: list[Image.Image],
    *,
    reject_unexpected_codes: bool = False,
    non_qrdm_count: list[int] | None = None,
) -> dict[int, QRContent]:
    """Decode QRDM QR code payloads contained in a sequence of images.

    Includes attempts at image enhancement if the expected number of QR codes are not
    successfully decoded.
    """
    try:
        max_workers = multiprocessing.cpu_count()
    except NotImplementedError as e:
        logger.warning(f"Failed to get cpu count for multithreading with error: {e}")
        logger.debug("Defaulting to 10 worker threads")
        max_workers = min(10, len(images))

    extracted_contents = {}
    logger.debug(f"Decoding QRs from {len(images)} input images")
    start_time = time.time()
    extracted_contents = _batch_decode_qr_imgs(
        images,
        max_workers=max_workers,
        reject_unexpected_codes=reject_unexpected_codes,
        non_qrdm_count=non_qrdm_count,
    )
    total_time = time.time() - start_time
    logger.debug(f"Decoded {len(extracted_contents)} codes in {total_time:0.4f}s")

    # Check if enough qrs were found for document decoding
    if not _sufficient_decodes(extracted_contents):
        logger.debug("Not enough QRs decoded, attempting image enhancement")
        new_contents = _batch_filter_and_decode_qr_imgs(
            images,
            existing_contents=extracted_contents,
            max_workers=max_workers,
            reject_unexpected_codes=reject_unexpected_codes,
            non_qrdm_count=non_qrdm_count,
        )
        extracted_contents.update(new_contents)
        logger.debug(
            "Total QR codes decoded after image enhancement: %d",
            len(extracted_contents),
        )

    qr_info = structlog.contextvars.get_contextvars().get("qr_info", {})
    qr_info.update(
        {
            "extracted_qrs": list(extracted_contents.keys()),
            "num_extracted_qrs": len(extracted_contents),
        }
    )
    structlog.contextvars.bind_contextvars(qr_info=qr_info)

    return extracted_contents


def _reconstruct_document_payload(
    extracted_contents: dict[int, QRContent], passphrase: str | None = None
) -> DocumentPayload:
    """Reconstruct a DocumentPayload from a sequence of individual QR payloads."""
    first_content = next(iter(extracted_contents.values()))
    total_qr_codes = first_content.meta.total_qr_codes
    num_ecc = first_content.meta.num_ecc
    min_qrs_needed = total_qr_codes - num_ecc

    missing_codes = [ii for ii in range(total_qr_codes) if ii not in extracted_contents]

    if len(extracted_contents) < min_qrs_needed:
        msg = (
            f"Insufficient QR payloads for recovery. "
            f"Need at least {min_qrs_needed}, but only got {len(extracted_contents)} of {total_qr_codes}. "
            f"Missing sequence numbers: {missing_codes}"
        )
        raise QRDecodeError(msg, missing_codes=missing_codes)

    doc_fragments: dict[int, bytes] = {
        seq: contents.doc_fragment for (seq, contents) in extracted_contents.items()
    }
    max_payload_len = max(len(fragment) for fragment in doc_fragments.values())

    dropped_code_inds = []
    for seq_num in range(total_qr_codes):
        if seq_num not in extracted_contents:
            logger.debug(f"Missing code: {seq_num}")
            dropped_code_inds.append(seq_num)
            doc_fragments[seq_num] = b"\0" * max_payload_len

    sorted_payload_tuples = sorted(doc_fragments.items(), key=lambda tuple: tuple[0])
    sorted_payloads = [t[1] for t in sorted_payload_tuples]
    logger.debug(
        "Directly extracted payloads: %r", [p.hex(" ", 4) for p in sorted_payloads]
    )

    if num_ecc > 0:
        logger.debug("Checking error-correction codes")
        received_symbols = list(zip(*sorted_payloads))
        decoding_codec = reedsolo.RSCodec(num_ecc)
        try:
            fixed_symbols = [
                decoding_codec.decode(
                    x, erase_pos=dropped_code_inds, only_erasures=True
                )[0]
                for x in received_symbols
            ]
        except reedsolo.ReedSolomonError as e:
            msg = (
                f"Reed-Solomon error correction failed. "
                f"Decoded {len(extracted_contents)} of {total_qr_codes} codes. "
                f"Missing sequence numbers: {dropped_code_inds}"
            )
            raise QRDecodeError(msg, missing_codes=dropped_code_inds) from e
        sorted_payloads = [bytes(x) for x in zip(*fixed_symbols)]
        logger.debug("Post-EC payloads: %r", [p.hex(" ", 4) for p in sorted_payloads])

    total_payload_bytes = b"".join(sorted_payloads)
    logger.debug("Concatenated total payload: %s", total_payload_bytes.hex(" ", 4))

    hash_bytes_check = hashlib.sha256(total_payload_bytes.strip(b"\0")).digest()
    logger.debug("Recovered document hash (SHA-256): %s", hash_bytes_check.hex(" ", 4))
    if hash_bytes_check != first_content.meta.document_hash:
        logger.error(
            "Recovered document does not match verification hash: "
            f"{hash_bytes_check.hex()} vs. {first_content.meta.document_hash.hex()}"
        )
        msg = (
            f"Recovered document does not match checksum. "
            f"Extracted {len(extracted_contents)} of {total_qr_codes} codes."
        )
        if dropped_code_inds:
            msg += f" Missing sequence numbers: {dropped_code_inds}"
        raise QRDecodeError(
            msg, missing_codes=dropped_code_inds if dropped_code_inds else None
        )

    raw_payload = total_payload_bytes.strip(b"\0")
    from qrdm.qr import crypto

    if crypto.is_encrypted(raw_payload):
        if not passphrase:
            raise QRDecodeError(
                "Encrypted payload detected: passphrase required to decode."
            )
        raw_payload = crypto.decrypt_payload(raw_payload, passphrase)
    elif passphrase:
        logger.warning("Passphrase provided but payload is not encrypted.")

    output = DocumentPayload.model_validate_compressed_bytes(raw_payload)

    logger.debug("Recomposed document (complete): %r", output)

    return output


def _batch_decode_qr_imgs(
    images: list[Image.Image],
    max_workers: int | None = None,
    threaded_executor: concurrent.futures.ThreadPoolExecutor | None = None,
    reject_unexpected_codes: bool = False,
    non_qrdm_count: list[int] | None = None,
) -> dict[int, QRContent]:
    """Decode a sequence of QR images into their corresponding data payloads."""
    # Multithreaded Mode
    if threaded_executor:
        # Use provided thread pool
        decodes = list(threaded_executor.map(_pyzbar_decode_qr_job, images))
    else:
        # Initialize threadpool for single use
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            decodes = list(executor.map(_pyzbar_decode_qr_job, images))
    # unpacking results
    flattened_decodes = []
    flattened_decodes = list(chain(*decodes))
    qr_contents = _parse_qr_contents(
        flattened_decodes,
        reject_unexpected_codes=reject_unexpected_codes,
        non_qrdm_count=non_qrdm_count,
    )

    if len(qr_contents) > 0:
        qr_info = structlog.contextvars.get_contextvars().get("qr_info", {})
        qr_info.update(
            {
                "qr_meta": next(iter(qr_contents.values())).meta.model_dump(
                    exclude={"sequence_number"}
                )
            }
        )
        structlog.contextvars.bind_contextvars(qr_info=qr_info)

    return qr_contents


def _pyzbar_decode_qr_job(img: Image.Image) -> list[Decoded]:
    return decode(img, symbols=[ZBarSymbol.QRCODE])


def _parse_qr_contents(
    decodes: list[Decoded],
    *,
    reject_unexpected_codes: bool = False,
    non_qrdm_count: list[int] | None = None,
) -> dict[int, QRContent]:
    """Parse a list of pyzbar decodes into ordered set of QRContents."""
    extracted_contents = {}
    for ii, qr in enumerate(decodes):
        logger.debug(f"Parsing decode {ii+1} of {len(decodes)}")
        try:
            content = QRContent.model_validate_b85_bytes(qr.data)
        except Exception as e:
            if non_qrdm_count is not None:
                non_qrdm_count[0] += 1
            if reject_unexpected_codes:
                raise QRDecodeError(f"Rejected non-QRDM barcode on page: {e}") from e
            logger.debug(f"Ignoring non-QRDM barcode: {e}")
            continue
        extracted_contents[content.meta.sequence_number] = content

        logger.debug(
            "Recovered QR #%d payload with metadata: %r",
            content.meta.sequence_number,
            dict(content.meta),
        )
        logger.debug(
            "Recovered QR #%d payload with content: %s",
            content.meta.sequence_number,
            content.doc_fragment.hex(" ", 4),
        )

    return extracted_contents


def _batch_filter_and_decode_qr_imgs(
    images: list[Image.Image],
    existing_contents: dict[int, QRContent] | None = None,
    max_workers: int | None = None,
    reject_unexpected_codes: bool = False,
    non_qrdm_count: list[int] | None = None,
) -> dict[int, QRContent]:
    """Apply a image filters to page images to attempt to decode additional QR codes."""
    if existing_contents is None:
        existing_contents = {}
    extracted_contents = existing_contents.copy()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        for blur_radius in [2, 3, 4]:
            # blur all images
            blurred_imgs = [_box_blur(img, blur_radius) for img in images]
            # run zbar
            new_contents = _batch_decode_qr_imgs(
                blurred_imgs,
                threaded_executor=executor,
                reject_unexpected_codes=reject_unexpected_codes,
                non_qrdm_count=non_qrdm_count,
            )
            extracted_contents.update(new_contents)
            # check if sufficient decodes
            if _sufficient_decodes(extracted_contents):
                break

            # double blur all images
            db_blurred_imgs = [_box_blur(img, blur_radius) for img in blurred_imgs]
            # run zbar
            new_contents = _batch_decode_qr_imgs(
                db_blurred_imgs,
                threaded_executor=executor,
                reject_unexpected_codes=reject_unexpected_codes,
                non_qrdm_count=non_qrdm_count,
            )
            extracted_contents.update(new_contents)
            # check if sufficient decodes
            if _sufficient_decodes(extracted_contents):
                break
    return extracted_contents


def _box_blur(img: Image.Image, kernel_size: int) -> Image.Image:
    """Apply a box filter blur of `kernel_size` to an image."""
    blurred_img = img.filter(ImageFilter.BoxBlur(kernel_size))
    return blurred_img


def _sufficient_decodes(qr_contents: dict[int, QRContent]) -> bool:
    """Check if QR code contents are sufficient to reconstruct the source document."""
    decoded_qr_count = len(qr_contents)
    if decoded_qr_count == 0:
        return False
    one_code = next(iter(qr_contents.values()))
    required_qrs = one_code.meta.total_qr_codes - one_code.meta.num_ecc
    sufficient_decodes = decoded_qr_count >= required_qrs
    if not sufficient_decodes:
        logger.debug("Missing codes: %r", _list_missing_qr_codes(qr_contents))
    return sufficient_decodes


def _list_missing_qr_codes(qr_contents: dict[int, QRContent]) -> list[int]:
    """Determine indices of missing QR code contents."""
    one_code = next(iter(qr_contents.values()))
    total_qrs = one_code.meta.total_qr_codes
    return [ii for ii in range(total_qrs) if ii not in qr_contents]
