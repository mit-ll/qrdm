# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT
"""Render QRDM PDFs from a set of QR codes, via `reportlab`."""
from __future__ import annotations

import io
import logging
import time
from importlib import resources
from pathlib import Path
from typing import Optional

from qrcode.main import QRCode
from reportlab.graphics import renderPDF
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from svglib.svglib import Drawing, svg2rlg

from qrdm import __version__ as QRDM_VERSION

__all__ = ["generate_pdf_pages"]
logger = logging.getLogger(__name__)

# Document Constants
AUTHOR_NAME = f"QRDM v{QRDM_VERSION}"
LOGO_PATH = resources.files("qrdm.qr.data").joinpath("qrdm_logo_red.png")

# Layout Parameters
# Upper left corner of QR region
START_X_PX: float = 0.25 * inch
START_Y_PX: float = 10.25 * inch
# Maximum pixels from the left side of a standard 8.5 inch page
# Make it horizontally symmetric
MAX_X_PX: float = (8.5 * inch) - START_X_PX
# Lower boundary of the QR area, under which the plaintext caption resides
MIN_Y_PX: float = 4.75 * inch
# Spacing of QR codes
QR_MARGIN_PX: float = 0.25 * inch
# Text caption under QR code area
CAPTION_CHAR_WIDTH: int = 192
MAX_CHAR_LIMIT: int = 45 * 192  # num_lines * CAPTION_CHAR_WIDTH


def generate_pdf_pages(
    qr_codes: list[QRCode],
    *,
    buf: io.BufferedIOBase,
    header_text: str = "",
    qr_text: Optional[str] = None,
    filename: Optional[str] = None,
) -> None:
    """Write a QRDM PDF from a list of QRCodes to a binary stream.

    Parameters
    ----------
    qr_codes: list[QRCode]
        List of `qrcode.QRCode` objects, configured to use the `SvgPathImage` image
        factory.
    buf: Writeable binary stream object
        Stream that PDF file will be written to.
    header_text: str, optional
        Text to include as header & footer of QR PDF. Defaults to `""`.
    qr_text: str, optional
        If not `None`, will be used to provide a caption split across the lower portions
        of the generated pages. Defaults to `None`.
    filename: str
        The name of source file that was QR encoded, used to caption the page footer if
        not `None`. Defaults to `None`.

    """
    # Render QR codes as images, and convert to reportlab-compatible Drawings
    qr_imgs = _generate_qr_code_svgs(qr_codes=qr_codes)
    reportlab_qrs = _format_reportlab_img(imgs=qr_imgs)

    # Calculate positions of QR codes based on their dimensions, and whether space
    # is reserved for text content
    include_text = qr_text is not None
    page_qrs, page_qr_positions = _get_qr_positions_per_page(
        reportlab_qrs=reportlab_qrs, include_text=include_text
    )
    # Split up text across number of pages
    if include_text:
        page_qr_text = _split_text_across_pages(qr_text)
    else:
        page_qr_text = []

    logger.debug("QRS_PER_PAGE: %r", page_qrs)
    logger.debug("QRS_POSITIONS: %r", page_qr_positions)

    # Add Sourcing Information
    render_time = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    if filename is not None:
        file_path = Path(filename)
        printable_filename = file_path.name
        if len(printable_filename) > 40:
            printable_filename = "".join(
                [file_path.stem[:30], " ... .", file_path.suffix]
            )
        doc_title = f"QR Encoding of {filename}"
        footer_text = f"Content from {printable_filename} at {render_time}"
    else:
        printable_filename = None
        doc_title = "QR Encoded Document"
        footer_text = f"Encoded at {render_time}"

    c = canvas.Canvas(buf, pagesize=letter)
    c.setAuthor(AUTHOR_NAME)
    c.setTitle(doc_title)

    for page_index, qr_range in enumerate(page_qrs, start=1):
        logger.debug(f"Redering PDF page {page_index} of {len(page_qrs)}")
        page_footer_text = footer_text + f", Page {page_index} of {len(page_qrs)}"
        _draw_header_footer(c, header_text=header_text, footer_text=page_footer_text)

        for j in range(qr_range[0], qr_range[1]):
            _draw_qr_on_canvas(
                c, rendered_qr=reportlab_qrs[j], pos=page_qr_positions[j]
            )

        if include_text and page_index <= (len(page_qr_text)):
            # Check if we're on the last page, and there's more text chunks than pages
            if (page_index == len(page_qrs)) and (len(page_qr_text) > len(page_qrs)):
                remaining_chars = sum(len(text) for text in page_qr_text[page_index:])
                _add_overflow_notice(c, remaining_chars=remaining_chars)
            _add_page_caption(c, text=page_qr_text[page_index - 1])

        # Cycle to next page
        c.showPage()
    c.save()


def _generate_qr_code_svgs(qr_codes: list[QRCode]) -> list[io.BytesIO]:
    # Sort QR codes by size, so layout algorithm can safely assume that rows won't
    # grow in height
    qr_sizes = [code.version for code in qr_codes]
    # This is just a python list version of `np.argsort`
    code_size_order = sorted(
        range(len(qr_sizes)), key=qr_sizes.__getitem__, reverse=True
    )
    sorted_qr_codes = [qr_codes[ii] for ii in code_size_order]
    imgs = []
    for code in sorted_qr_codes:
        img = code.make_image()
        img_byte_stream = io.BytesIO(initial_bytes=img.to_string())
        imgs.append(img_byte_stream)
    return imgs


def _draw_qr_on_canvas(
    c: canvas.Canvas, *, rendered_qr: Drawing, pos: tuple[int, int]
) -> None:
    # Load the image into reportlab image class, scale and draw
    renderPDF.draw(rendered_qr, c, pos[0], pos[1] - rendered_qr.height)


def _format_reportlab_img(imgs: list[io.BytesIO]) -> list[Drawing]:
    reportlab_qrs = []
    for img in imgs:
        reportlab_qrs.append(svg2rlg(img))
    return reportlab_qrs


def _get_qr_positions_per_page(
    *, reportlab_qrs: list[Drawing], include_text: bool = True
):
    logger.debug("Calculating QR page positions")
    page_qr_positions = []
    page_qrs = []

    if include_text:
        min_y_px = MIN_Y_PX
    else:
        # Maximum pixels from the top of a standard 11 inch page, it
        # includes a .5 inch bottom margin, but no space for text.
        # It does not include .5 top margin, that's included e
        min_y_px = 0.75 * inch

    cur_x_px = START_X_PX
    cur_y_px = START_Y_PX
    last_h_px = 0
    qr_counter = 0

    for ii, rendered_qr in enumerate(reportlab_qrs):
        qr_h_px = rendered_qr.height
        qr_w_px = rendered_qr.width

        enough_horizontal_space = cur_x_px + qr_w_px <= MAX_X_PX
        if not enough_horizontal_space:
            # Start new row, typewriter style
            cur_x_px = START_X_PX
            cur_y_px -= last_h_px + QR_MARGIN_PX
            enough_vertical_space = cur_y_px - qr_h_px >= min_y_px
            if not enough_vertical_space:
                # Start new page
                cur_y_px = START_Y_PX
                page_qrs.append((qr_counter, ii))
                qr_counter = ii

        # Recalculate, as our reference point may have moved
        enough_horizontal_space = cur_x_px + qr_w_px <= MAX_X_PX
        enough_vertical_space = cur_y_px - qr_h_px >= min_y_px
        if enough_horizontal_space and enough_vertical_space:
            # Record the position, and move reference point for next code
            page_qr_positions.append((cur_x_px, cur_y_px))
            cur_x_px += qr_w_px + QR_MARGIN_PX
            last_h_px = qr_h_px
        else:
            raise RuntimeError("Unable to fit QR code on page!")

    page_qrs.append((qr_counter, len(reportlab_qrs)))
    return page_qrs, page_qr_positions


def _split_text_across_pages(text: str) -> list[str]:
    # Make escape characters printable with `repr`
    # Slice [1:] to remove opening quote char, trailing quote handled by the -1 in
    # `breakpoints` below
    caption_text = repr(text)[1:]
    # Chunk text into substings of length MAX_CHAR_LIMIT
    breakpoints = [*list(range(0, len(caption_text), MAX_CHAR_LIMIT)), -1]
    page_text = [
        caption_text[breakpoints[ii] : breakpoints[ii + 1]]
        for ii in range(len(breakpoints) - 1)
    ]
    return page_text


def _draw_header_footer(
    c: canvas.Canvas, *, header_text: str, footer_text: str
) -> None:
    c.drawCentredString(4.25 * inch, 0.25 * inch, header_text)
    c.drawCentredString(4.25 * inch, 10.5 * inch, header_text)
    c.drawCentredString(4.25 * inch, 0.5 * inch, footer_text)
    # Draw QRDM logo
    with LOGO_PATH.open("rb") as imgfile:
        logo_img = ImageReader(imgfile)
        c.drawImage(
            logo_img,
            x=START_X_PX,
            y=START_Y_PX + inch / 4,
            width=inch / 4,
            preserveAspectRatio=True,
            mask="auto",
            anchor="sw",
        )


def _add_page_caption(c: canvas.Canvas, text: str) -> None:
    textobject = c.beginText()
    textobject.setFont("Courier", size=5)
    textobject.setTextOrigin(0.25 * inch, MIN_Y_PX)
    char_line_width = CAPTION_CHAR_WIDTH
    for ii in range(0, len(text), char_line_width):
        textobject.textLine(text[ii : ii + char_line_width])
    c.drawText(textobject)


def _add_overflow_notice(c: canvas.Canvas, *, remaining_chars: int) -> None:
    text = (
        "NOTICE: Remaining source content text omitted due to length. "
        f" ({remaining_chars} characters)"
    )
    c.drawCentredString(4.25 * inch, 0.75 * inch, text)
