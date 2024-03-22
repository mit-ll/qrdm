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

from qrdm.exceptions import QREncodeError
from qrdm.models import DocumentPayload
from qrdm.qr import decode, encode, pdf_writer

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
    result = decode.decode_qr_pdf(file_path)
    assert result is None
