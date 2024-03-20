# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT
"""QRDM Streamlit Landing Page."""

import streamlit as st
from streamlit.logger import get_logger

import qrdm

# We need to invoke the qrdm logger once with streamlit's custom `get_logger` to let it
# pass through to stderr when running `streamlit run`
qrdm_logger = get_logger(qrdm.__name__)

st.set_page_config(page_title="Home")
st.title("QRDM Home")
st.sidebar.write(f"QRDM v{qrdm.__version__}")

st.markdown(
    """
    ## Overview
    The QR Data Manager (QRDM) assists users in storing and/or transferring text data
    via printed pages that can be printed and scanned. The system works by taking in
    files, extracting the textual data, and creating PDFs of QR codes. Those PDFs can be
    printed and then later scanned onto a computer where the PDF can be decoded, and the
    original information recovered as a text file.

    Links to pages where encoding and decoding can be performed can be found in the
    sidebar of this page.
    """
)
