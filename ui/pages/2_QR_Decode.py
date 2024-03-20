# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT
"""QRDM Streamlit QR-Encoding Page."""
import io
from pathlib import Path

import streamlit as st
from streamlit.logger import get_logger

from qrdm import __version__ as version
from qrdm.exceptions import QRDecodeError
from qrdm.qr.decode import decode_qr_pdf

logger = get_logger(__name__)
logger.info("Loading Decode page")

st.set_page_config(page_title="QR Decoder")
st.title("QR Decoder")
st.sidebar.write(f"QRDM v{version}")

file_count = 0
upload_files = st.file_uploader("Choose file(s) to decode", accept_multiple_files=True)
if upload_files is not None:
    for upload_file in upload_files:
        file_data = io.BytesIO(upload_file.getvalue())
        filename = Path(upload_file.name)
        try:
            decoded_content = decode_qr_pdf(file_data)
            if decoded_content is None:
                raise QRDecodeError("Could not locate any QR codes in document.")
            output_name = filename.with_suffix(".txt").name
            output_file = decoded_content.content.encode()
            st.download_button(
                f"Download {output_name}",
                output_file,
                file_name=output_name,
                key=file_count,
            )
            file_count += 1
        except Exception as e:
            logger.exception(e)
            if isinstance(e, QRDecodeError):
                msg = f"{filename}: ERROR - {e}"
            else:
                msg = f"{filename}: ERROR - Unable to decode PDF"
            st.write(msg)
