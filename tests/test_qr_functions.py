# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT
import io
import random
import shutil

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from qrdm.exceptions import QRDecodeError, QREncodeError
from qrdm.models import DocumentPayload, QRContent
from qrdm.qr import decode, encode, pdf_writer

try:
    import pymupdf as fitz
except ImportError:
    import fitz

payload = """
    Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor
    incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud
    exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.  Duis aute
    irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla
    pariatur.  Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia
    deserunt mollit anim id est laborum.
    😎🎃🐋
    Zażółć gęślą jaźń
    Съешь же ещё этих мягких французских булок, да выпей чаю
    以呂波耳本部止 千利奴流乎和加 餘多連曽津祢那 良牟有為能於久 耶万計不己衣天 阿佐伎喩女美之 恵比毛勢須
    """
payload_cyrillic = "Съешь же ещё этих мягких французских булок, да выпей чаю"


def test_encoding_detection():
    file_data = payload_cyrillic.encode("cp1251")
    decoded = encode.get_file_content(file_data=file_data, encoding=None)
    assert decoded == payload_cyrillic


def test_encoding_param():
    file_data = payload_cyrillic.encode("cp1251")
    decoded = encode.get_file_content(file_data=file_data, encoding="cp1251")
    assert decoded == payload_cyrillic
    with pytest.raises(QREncodeError):
        encode.get_file_content(file_data=file_data, encoding="ascii")


@pytest.mark.parametrize("encode_ec_codes", [True, False], ids=["no_ecc", "ecc"])
def test_encode_and_decode_bytes(encode_ec_codes: bool):
    pdf_file_data = encode.encode_qr_pdf(
        document_content=payload, encode_ec_codes=encode_ec_codes
    )
    recomposed_document_payload = decode.decode_qr_pdf(input_file=pdf_file_data)
    assert recomposed_document_payload is not None
    assert recomposed_document_payload.content == payload


def test_encode_and_decode_file_path(tmp_path):
    path_as_obj = tmp_path / "as_path_obj.pdf"
    encode.encode_qr_pdf(document_content=payload, path=path_as_obj)
    recomposed_document_payload_obj = decode.decode_qr_pdf(path_as_obj)
    assert recomposed_document_payload_obj is not None
    assert recomposed_document_payload_obj.content == payload

    path_as_str = str(tmp_path / "as_string.pdf")
    encode.encode_qr_pdf(document_content=payload, path=path_as_str)
    recomposed_document_payload_str = decode.decode_qr_pdf(path_as_str)
    assert recomposed_document_payload_str is not None
    assert recomposed_document_payload_str.content == payload


def test_encode_and_decode_file_stream(tmp_path):
    path_as_stream = tmp_path / "as_stream.pdf"
    with open(path_as_stream, "wb") as write_stream:
        encode.encode_qr_pdf(document_content=payload, path=write_stream)
    with open(path_as_stream, "rb") as read_stream:
        # PyMuPDF doesn't accept the `BufferedReader` returned by `open`, so let's copy
        # it into a `BytesIO`
        buf = io.BytesIO()
        shutil.copyfileobj(read_stream, buf)
        recomposed_document_payload_obj = decode.decode_qr_pdf(buf)
    assert recomposed_document_payload_obj is not None
    assert recomposed_document_payload_obj.content == payload


def test_ecc_recovery():
    document_payload = DocumentPayload(content=payload)
    qr_payloads = encode.generate_qr_payloads(document_payload, encode_ec_codes=True)
    qr_codes = encode.generate_qr_codes(qr_payloads)
    # Drop one image to test ECC recovery
    qr_codes = random.sample(qr_codes, len(qr_codes) - 1)
    pdf_file_stream = io.BytesIO()
    pdf_writer.generate_pdf_pages(qr_codes=qr_codes, buf=pdf_file_stream)
    recomposed_document_payload = decode.decode_qr_pdf(input_file=pdf_file_stream)
    assert recomposed_document_payload is not None
    assert recomposed_document_payload == document_payload


def test_empty_file(tmp_path):
    file_path = tmp_path / "empty.pdf"
    with open(file_path, "wb") as f:
        c = canvas.Canvas(f, pagesize=letter)
        c.drawCentredString(4.25 * inch, 0.25 * inch, "DUMMY FILE")
        c.save()
    with pytest.raises(QRDecodeError) as exc_info:
        decode.decode_qr_pdf(file_path)
    assert "Failed to extract any QR data" in str(exc_info.value)


def test_missing_codes_reported():
    large_payload = payload * 5
    document_payload = DocumentPayload(content=large_payload)
    qr_payloads = encode.generate_qr_payloads(document_payload, encode_ec_codes=True)
    qr_codes = encode.generate_qr_codes(qr_payloads)
    assert len(qr_codes) > 2

    dropped_indices = [0, 1]
    kept_codes = []
    dropped_seqs = []
    for code, qr_pl in zip(qr_codes, qr_payloads):
        content = QRContent.model_validate_b85_bytes(qr_pl)
        if content.meta.sequence_number in dropped_indices:
            dropped_seqs.append(content.meta.sequence_number)
        else:
            kept_codes.append(code)

    pdf_file_stream = io.BytesIO()
    pdf_writer.generate_pdf_pages(qr_codes=kept_codes, buf=pdf_file_stream)

    with pytest.raises(QRDecodeError) as exc_info:
        decode.decode_qr_pdf(input_file=pdf_file_stream)

    assert exc_info.value.missing_codes is not None
    for dropped_seq in dropped_seqs:
        assert dropped_seq in exc_info.value.missing_codes
    assert "Missing sequence numbers:" in str(exc_info.value)


def test_include_text_opt_in():
    secret_text = "CONFIDENTIAL_PATIENT_RECORD_XYZ123"

    # Default: include_text=False (opt-in)
    pdf_no_text = encode.encode_qr_pdf(document_content=secret_text, include_text=False)
    doc_no_text = fitz.open(stream=io.BytesIO(pdf_no_text), filetype="pdf")
    all_text_no_text = "".join(page.get_text() for page in doc_no_text)
    assert secret_text not in all_text_no_text
    decoded = decode.decode_qr_pdf(pdf_no_text)
    assert decoded.content == secret_text

    # Opt-in: include_text=True
    pdf_with_text = encode.encode_qr_pdf(document_content=secret_text, include_text=True)
    doc_with_text = fitz.open(stream=io.BytesIO(pdf_with_text), filetype="pdf")
    all_text_with_text = "".join(page.get_text() for page in doc_with_text)
    assert secret_text in all_text_with_text
    decoded_opt = decode.decode_qr_pdf(pdf_with_text)
    assert decoded_opt.content == secret_text


def test_deterministic_output():
    text = "Deterministic output test content."
    pdf1 = encode.encode_qr_pdf(document_content=text, include_timestamp=False)
    pdf2 = encode.encode_qr_pdf(document_content=text, include_timestamp=False)
    assert pdf1 == pdf2


def test_trailing_null_payload():
    null_payload = "\0" * 244
    document_payload = DocumentPayload(content=null_payload)
    assert document_payload.model_dump_compressed_bytes()[-1] == 0
    pdf_file_data = encode.encode_qr_pdf(document_content=null_payload)
    recomposed_document_payload = decode.decode_qr_pdf(input_file=pdf_file_data)
    assert recomposed_document_payload is not None
    assert recomposed_document_payload.content == null_payload
