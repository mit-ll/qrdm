# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT
"""Tests for security features: AES-256-GCM encryption, decompression bombs, and path traversal."""

from __future__ import annotations

import zlib
from pathlib import Path

import pytest

from qrdm.cli import main
from qrdm.exceptions import QRDecodeError, QREncodeError
from qrdm.models import DocumentPayload, sanitize_filename
from qrdm.qr import crypto
from qrdm.qr.decode import decode_qr_pdf, verify_qr_pdf
from qrdm.qr.encode import encode_qr_pdf


def test_sanitize_filename():
    assert sanitize_filename("safe_doc.txt") == "safe_doc.txt"
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename(r"..\..\Windows\System32\cmd.exe") == "cmd.exe"
    assert sanitize_filename("nested/dir/report.pdf") == "report.pdf"
    assert sanitize_filename("bad:name*with?chars<.txt") == "bad_name_with_chars_.txt"
    assert sanitize_filename("null\x00byte.txt") == "nullbyte.txt"
    assert sanitize_filename("...hidden") == "hidden"
    assert sanitize_filename("") == "document"
    assert sanitize_filename(None) == "document"


def test_crypto_roundtrip():
    payload = b"Top secret scientific observations and findings."
    passphrase = "correct-horse-battery-staple-2026!"

    encrypted = crypto.encrypt_payload(payload, passphrase)
    assert crypto.is_encrypted(encrypted)
    assert encrypted.startswith(b"QRE1")
    assert payload not in encrypted

    decrypted = crypto.decrypt_payload(encrypted, passphrase)
    assert decrypted == payload


def test_crypto_wrong_passphrase():
    payload = b"Classified research data."
    passphrase = "password123"
    wrong_passphrase = "wrongpassword"

    encrypted = crypto.encrypt_payload(payload, passphrase)
    with pytest.raises(QRDecodeError, match="Decryption failed"):
        crypto.decrypt_payload(encrypted, wrong_passphrase)


def test_crypto_empty_passphrase():
    payload = b"Sample text"
    with pytest.raises(QREncodeError, match="Passphrase must not be empty"):
        crypto.encrypt_payload(payload, "")


def test_decompression_bomb_protection():
    # Construct a high-ratio compressed stream (e.g. 50 MB of zeros)
    huge_data = b"\x00" * (10 * 1024 * 1024)
    compressed = zlib.compress(huge_data)

    # Set threshold lower than inflated size
    with pytest.raises(QRDecodeError, match="Decompression bomb rejected"):
        DocumentPayload.model_validate_compressed_bytes(
            compressed, max_uncompressed_size=1 * 1024 * 1024
        )


def test_encrypted_qr_pdf_roundtrip(tmp_path: Path):
    doc_text = "Sensitive data intended solely for authenticated recipient."
    passphrase = "secure-password-456"

    pdf_bytes = encode_qr_pdf(
        document_content=doc_text,
        document_name="secret.txt",
        passphrase=passphrase,
        minimal_mode=True,
    )

    # Verification with passphrase
    verify_res = verify_qr_pdf(pdf_bytes, passphrase=passphrase)
    assert verify_res.overall is True
    assert verify_res.payload_valid is True

    # Verification without passphrase fails payload validation
    verify_unauth = verify_qr_pdf(pdf_bytes, passphrase=None)
    assert verify_unauth.payload_valid is False
    assert any("passphrase required" in err for err in verify_unauth.errors)

    # Decode with passphrase
    decoded = decode_qr_pdf(pdf_bytes, passphrase=passphrase)
    assert decoded.content == doc_text

    # Decode without passphrase raises
    with pytest.raises(QRDecodeError, match="passphrase required"):
        decode_qr_pdf(pdf_bytes, passphrase=None)

    # Decode with incorrect passphrase raises
    with pytest.raises(QRDecodeError, match="Decryption failed"):
        decode_qr_pdf(pdf_bytes, passphrase="wrong-passphrase")


def test_cli_passphrase_encode_decode(tmp_path: Path, capsys):
    secret_file = tmp_path / "confidential.txt"
    secret_text = "Highly confidential ledger data."
    secret_file.write_text(secret_text, encoding="utf-8")

    pdf_out = tmp_path / "confidential_qr.pdf"
    passphrase = "my-secret-vault-key"

    # Encode with passphrase
    rc = main(
        [
            "encode",
            str(secret_file),
            "-o",
            str(pdf_out),
            "--passphrase",
            passphrase,
            "--minimal",
        ]
    )
    assert rc == 0
    assert pdf_out.is_file()

    # Verify with passphrase
    rc = main(["verify", str(pdf_out), "--passphrase", passphrase, "--json"])
    assert rc == 0
    captured = capsys.readouterr()
    assert '"overall": true' in captured.out

    # Decode with wrong passphrase fails
    rc = main(["decode", str(pdf_out), "--passphrase", "wrong-key"])
    assert rc == 2
    err_out = capsys.readouterr()
    assert "Decryption failed" in err_out.err

    # Decode with correct passphrase succeeds
    out_file = tmp_path / "recovered.txt"
    rc = main(["decode", str(pdf_out), "-o", str(out_file), "--passphrase", passphrase])
    assert rc == 0
    assert out_file.read_text(encoding="utf-8") == secret_text
