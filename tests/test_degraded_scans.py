# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT
"""Regression tests for degraded scan recovery (rotation, blur, JPEG compression)."""

from __future__ import annotations

import io

try:
    import pymupdf as fitz
except ImportError:
    import fitz

from PIL import Image, ImageFilter

from qrdm import decode_qr_pdf, encode_qr_pdf, verify_qr_pdf


def _simulate_scan_degradation(
    pdf_bytes: bytes,
    *,
    dpi: int = 200,
    rotate_deg: float = 1.0,
    blur_radius: float = 0.8,
    jpeg_quality: int = 60,
) -> bytes:
    """Simulate physical scan degradation: resolution scaling, skew, blur, and JPEG loss."""
    src_doc = fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf")
    degraded_doc = fitz.open()

    for page in src_doc:
        pix = page.get_pixmap(dpi=dpi)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        if rotate_deg != 0:
            img = img.rotate(rotate_deg, expand=False, fillcolor="white")
        if blur_radius > 0:
            img = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))

        jbuf = io.BytesIO()
        img.save(jbuf, format="JPEG", quality=jpeg_quality)
        jpeg_data = jbuf.getvalue()

        img_doc = fitz.open(stream=jpeg_data, filetype="jpeg")
        rect = img_doc[0].rect
        pdf_page = degraded_doc.new_page(width=rect.width, height=rect.height)
        pdf_page.insert_image(rect, stream=jpeg_data)

    return degraded_doc.tobytes()


def test_mild_degradation_recovery():
    """Simulate mild degradation: 200 dpi, 1° rotation, blur 0.8, JPEG 60."""
    content = (
        "Sample document for degraded scan test.\nColumn1,Column2,Column3\nval1,val2,val3\n"
        * 4
    )
    pdf_bytes = encode_qr_pdf(content, encode_ec_codes=True)

    degraded_pdf = _simulate_scan_degradation(
        pdf_bytes, dpi=200, rotate_deg=1.0, blur_radius=0.8, jpeg_quality=60
    )

    result = verify_qr_pdf(degraded_pdf)
    assert result.overall is True
    assert result.status == "recovered"

    recovered = decode_qr_pdf(degraded_pdf)
    assert recovered.content == content


def test_harsh_degradation_recovery():
    """Simulate harsh degradation: 150 dpi, 1.5° rotation, blur 1.0, JPEG 45."""
    content = "Harsh scan degradation recovery verification with Reed-Solomon.\n" * 6
    pdf_bytes = encode_qr_pdf(content, encode_ec_codes=True)

    degraded_pdf = _simulate_scan_degradation(
        pdf_bytes, dpi=150, rotate_deg=1.5, blur_radius=1.0, jpeg_quality=45
    )

    recovered = decode_qr_pdf(degraded_pdf)
    assert recovered.content == content
