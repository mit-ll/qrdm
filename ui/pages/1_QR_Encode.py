# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT
"""QRDM Streamlit QR-Encoding Page."""
from pathlib import Path

import streamlit as st
from streamlit.logger import get_logger

from qrdm import __version__ as version
from qrdm.exceptions import QREncodeError
from qrdm.qr.encode import encode_qr_pdf, get_file_content

logger = get_logger(__name__)
logger.info("Loading Encode page")

st.set_page_config(page_title="QR Encoder")
st.title("QR Encoder")
st.sidebar.write(f"QRDM v{version}")

header_text = st.text_input(
    "Document Header & Footer Text (optional)", placeholder="Test"
)
col1, col2 = st.columns(2)
with col1:
    preset = st.selectbox(
        "Layout Preset",
        ["default", "flatbed", "photo"],
        help="flatbed: dense 12 codes/page for scanners; photo: large 4 codes/page for phone cameras; default: 6 codes/page",
    )
with col2:
    minimal_mode = st.checkbox(
        "Minimal Mode (filename + hash + page only)", value=False
    )

include_text = st.checkbox(
    "Print document text under QR codes (opt-in)", value=False, disabled=minimal_mode
)

upload_files = st.file_uploader(
    "Choose file(s) to QR encode", accept_multiple_files=True
)
if upload_files is not None:
    for upload_file in upload_files:
        file_data = upload_file.getvalue()
        filename = Path(upload_file.name)
        try:
            file_content = get_file_content(file_data)
            logger.debug("Extracted file content: %r", file_content)
            output_file_data = encode_qr_pdf(
                file_content,
                header_text=header_text,
                document_name=upload_file.name,
                include_text=include_text,
                minimal_mode=minimal_mode,
                preset=preset,
            )
            output_filename = filename.stem + "_qr.pdf"
            st.download_button(
                f"Download {output_filename}",
                output_file_data,
                file_name=output_filename,
            )
        except Exception as e:
            logger.exception(e)
            if isinstance(e, QREncodeError):
                msg = f"{filename}: ERROR - {e}"
            else:
                msg = f"{filename}: ERROR - Unable to convert to QR PDF"
            st.write(msg)
