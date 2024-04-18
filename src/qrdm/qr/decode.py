# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT
"""Recover source documents from QRDM PDFs."""
from __future__ import annotations

import concurrent.futures
import hashlib
import io
import logging
import multiprocessing
import time
import warnings
from itertools import chain
from pathlib import Path
from typing import Optional, Union

import fitz
import reedsolo
import structlog.contextvars
from PIL import Image, ImageFilter
from pyzbar.pyzbar import Decoded, ZBarSymbol, decode

from qrdm.exceptions import QRDecodeError
from qrdm.models import DocumentPayload, QRContent

__all__ = ["decode_qr_pdf"]
logger = logging.getLogger(__name__)


def decode_qr_pdf(
    input_file: Union[str, Path, bytes, io.BytesIO]
) -> Optional[DocumentPayload]:
    """Decode a QRDM PDF into the original document content and metadata.

    Parameters
    ----------
    input_file: Path-like, bytes, or io.BytesIO
        Path to PDF file, binary stream, or bytes containing the file contents of the QR
        PDF. (e.g. as returned by `encode_qr_pdf`) Passed as input to the `fitz.open`
        function provided by PyMuPDF.

    Returns
    -------
    decoded_document: DocumentPayload or `None`
        If no QR codes are detected in the PDF by pyzbar, `None` is returned. Otherwise,
        returns a Pydantic model containing the encoded document & metadata, with
        attributes:

            - content: str - Source document contents
            - metadata: JsonValue, optional - Document metadata, as provided to the
              `metadata` argument of the encoding.

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
    if isinstance(input_file, (str, Path)):
        doc = fitz.open(input_file, filetype="pdf")
    else:
        if isinstance(input_file, bytes):
            stream = io.BytesIO(input_file)
        else:
            stream = input_file
        doc = fitz.open(stream=stream, filetype="pdf")

    extracted_images = _extract_page_images(doc)
    extracted_contents = _extract_qr_contents_from_images(extracted_images)
    logger.debug(f"Number of extracted payloads: {len(extracted_contents)}")

    if len(extracted_contents) == 0:
        warnings.warn("Failed to extract any QR data from input document")
        return None

    try:
        logger.debug("Reconstructing QR Data")
        decoded_document = _reconstruct_document_payload(
            extracted_contents=extracted_contents
        )
    except Exception as e:
        msg = f"ERROR: Failed to decode PDF, found {len(extracted_contents)} QR codes"
        logger.error(msg)
        raise e

    return decoded_document


def _extract_page_images(doc: fitz.Document) -> list[Image.Image]:
    """Render PDF pages as a sequence of PNG images."""
    logger.debug("Rendering PDF pages")
    extracted_images = []
    for page in doc:
        page_pixmap: fitz.Pixmap = page.get_pixmap(dpi=300)
        extracted_image = Image.open(io.BytesIO(page_pixmap.tobytes("png")))
        extracted_images.append(extracted_image)
    logger.debug("Rendered %d images from PDF Document", len(extracted_images))
    return extracted_images


def _extract_qr_contents_from_images(images: list[Image.Image]) -> dict[int, QRContent]:
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
    extracted_contents = _batch_decode_qr_imgs(images, max_workers=max_workers)
    total_time = time.time() - start_time
    logger.debug(f"Decoded {len(extracted_contents)} codes in {total_time:0.4f}s")

    # Check if enough qrs were found for document decoding
    if not _sufficient_decodes(extracted_contents):
        logger.debug("Not enough QRs decoded, attempting image enhancement")
        new_contents = _batch_filter_and_decode_qr_imgs(
            images, existing_contents=extracted_contents, max_workers=max_workers
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
    extracted_contents: dict[int, QRContent]
) -> DocumentPayload:
    """Reconstruct a DocumentPayload from a sequence of individual QR payloads."""
    first_content = next(iter(extracted_contents.values()))
    total_qr_codes = first_content.meta.total_qr_codes
    num_ecc = first_content.meta.num_ecc
    min_qrs_needed = total_qr_codes - num_ecc

    if len(extracted_contents) < min_qrs_needed:
        msg = (
            "Insufficient QR payloads for recovery. "
            + f"Need {min_qrs_needed}, got {len(extracted_contents)}"
        )
        raise QRDecodeError(msg)

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
        fixed_symbols = [
            decoding_codec.decode(x, erase_pos=dropped_code_inds, only_erasures=True)[0]
            for x in received_symbols
        ]
        sorted_payloads = [bytes(x) for x in zip(*fixed_symbols)]
        logger.debug("Post-EC payloads: %r", [p.hex(" ", 4) for p in sorted_payloads])

    total_payload_bytes = b"".join(sorted_payloads)
    logger.debug("Concatenated total payload: %s", total_payload_bytes.hex(" ", 4))

    h = hashlib.shake_256(total_payload_bytes.strip(b"\0"))
    hash_bytes_check = h.digest(8)
    document_hash_check = int.from_bytes(hash_bytes_check, "big")
    logger.debug("Recovered document hash: %s", hash_bytes_check.hex(" ", 4))
    if document_hash_check != first_content.meta.document_hash:
        logger.error(
            "Recovered document does not match verification hash: "
            f"{document_hash_check} vs. {first_content.meta.document_hash}"
        )
        raise QRDecodeError("Recovered document does not match checksum")

    output = DocumentPayload.model_validate_compressed_bytes(total_payload_bytes)

    logger.debug("Recomposed document (complete): %r", output)

    return output


def _batch_decode_qr_imgs(
    images: list[Image.Image],
    max_workers: Optional[int] = None,
    threaded_executor: Optional[concurrent.futures.ThreadPoolExecutor] = None,
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
    qr_contents = _parse_qr_contents(flattened_decodes)

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


def _parse_qr_contents(decodes: list[Decoded]) -> dict[int, QRContent]:
    """Parse a list of pyzbar decodes into ordered set of QRContents."""
    extracted_contents = {}
    for ii, qr in enumerate(decodes):
        logger.debug(f"Parsing decode {ii+1} of {len(decodes)}")
        try:
            content = QRContent.model_validate_b85_bytes(qr.data)
        except Exception as e:
            raise QRDecodeError("Could not read QR payload") from e
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
    existing_contents: Optional[dict[int, QRContent]] = None,
    max_workers: Optional[int] = None,
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
                blurred_imgs, threaded_executor=executor
            )
            extracted_contents.update(new_contents)
            # check if sufficient decodes
            if _sufficient_decodes(extracted_contents):
                break

            # double blur all images
            db_blurred_imgs = [_box_blur(img, blur_radius) for img in blurred_imgs]
            # run zbar
            new_contents = _batch_decode_qr_imgs(
                db_blurred_imgs, threaded_executor=executor
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
