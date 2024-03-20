# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT
"""FastAPI application router for QR encode & decode functions."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Annotated, Optional

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Json, JsonValue

from qrdm.backend.config import BackendSettings, get_backend_settings
from qrdm.exceptions import QRDecodeError, QREncodeError
from qrdm.models import DocumentPayload
from qrdm.qr.decode import decode_qr_pdf
from qrdm.qr.encode import encode_qr_pdf, get_file_content

__all__ = ["router"]
logger = structlog.get_logger()

router = APIRouter(tags=["QR Encoding & Decoding"])


class EncodeData(BaseModel):
    """`/encode` endpoint request data."""

    header_text: str = ""
    encode_ec_codes: Optional[bool] = None
    metadata: JsonValue = None
    encoding: Optional[str] = None

    @classmethod
    def as_form_data(
        cls,
        header_text: Annotated[str, Form()] = "",
        metadata: Annotated[Json, Form()] = None,
        encoding: Annotated[Optional[str], Form()] = None,
    ) -> EncodeData:
        """Wrap the`EncodeData` constructor to accept HTTP Form data."""
        return cls(header_text=header_text, metadata=metadata, encoding=encoding)


@router.post("/encode", summary="Encode a plaintext document as a PDF of QR codes")
def encode_qr_endpoint(
    document: Annotated[UploadFile, File()],
    settings: Annotated[BackendSettings, Depends(get_backend_settings)],
    body: EncodeData = Depends(EncodeData.as_form_data),
) -> Response:
    # FastAPI uses Markdown formatting for docstring rendering in Swagger, etc.
    """Convert a plaintext document to a PDF containing the document encoded as QR codes.

    Required Form Data
    ------------------
    - **document** (binary): File to be QR-encoded
    - **header_text** (string, optional): Text to include as header & footer of QR PDF
    - **metadata** (string, optional): Text in this field will be treated as JSON, and
      encoded alongside the document contents in the QR PDF.
    - **encoding** (str, optional): Encoding used to decode the document file data into
      a string. If not provided, defaults to automatic detection via the
      `charset_normalizer` package. Valid encodings can be found in the Python
      documentation: https://docs.python.org/3.9/library/codecs.html#standard-encodings
    """
    # upload_file = body.upload_file
    file_data = document.file.read()
    if document.filename is not None:
        upload_filename = Path(document.filename)
    else:
        upload_filename = Path("document")
    structlog.contextvars.bind_contextvars(
        action="QR Encode", input_file={"filename": str(upload_filename)}
    )

    try:
        file_content = get_file_content(file_data, encoding=body.encoding)
        logger.debug("Extracted file content: %r", file_content)
        output_file_data = encode_qr_pdf(
            document_content=file_content,
            header_text=body.header_text,
            metadata=body.metadata,
            document_name=upload_filename.name,
            encode_ec_codes=settings.QRDM_ENCODE_EC_CODES,
            error_tolerance=settings.QRDM_ERROR_TOLERANCE,
        )
    except Exception as e:
        logger.exception(e, success=False)
        if isinstance(e, QREncodeError):
            msg = str(e)
        else:
            msg = "ERROR: Unable to convert file to QR PDF"
        headers = {"QRErrorType": e.__class__.__name__}
        raise HTTPException(status_code=500, detail=msg, headers=headers)

    output_filename = upload_filename.stem + "_qr.pdf"
    logger.info(
        f"Completed QR Conversion of {upload_filename!s}",
        output_file={"filename": output_filename},
    )
    return Response(
        content=output_file_data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{output_filename}"'},
    )


@router.post(
    "/decode",
    response_model_exclude_none=True,
    summary="Reconstruct a source document from a QRDM PDF",
)
def decode_qr_endpoint(document: Annotated[UploadFile, File()]) -> DocumentPayload:
    # FastAPI uses Markdown formatting for docstring rendering in Swagger, etc.
    """Reconstruct a source document from a QRDM PDF.

    Required Form Data
    ------------------
    - **document** (binary): QRDM PDF file to be decoded

    Returns
    -------
    JSON with fields:
    - **content** (string): Original document contents
    - **metadata** (optional): JSON representation of data provided to the `metadata`
      field of the `/encode` endpoint.

    """
    file_data = io.BytesIO(document.file.read())
    structlog.contextvars.bind_contextvars(
        action="QR Decode", input_file={"filename": str(document.filename)}
    )

    try:
        decoded_content = decode_qr_pdf(file_data)
        if decoded_content is None:
            raise QRDecodeError("Could not locate any QR codes in document.")
    except Exception as e:
        logger.exception(e, success=False)
        if isinstance(e, QRDecodeError):
            msg = str(e)
        else:
            msg = "ERROR: Unable to decode QR File"
        headers = {"QRErrorType": e.__class__.__name__}
        raise HTTPException(status_code=500, detail=msg, headers=headers)
    logger.info(f"Completed QR Decode of {document.filename!s}")
    return decoded_content
