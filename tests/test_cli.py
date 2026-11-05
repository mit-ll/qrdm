# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT
"""Tests for QRDM CLI entrypoint."""
from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

import pytest

from qrdm import __version__
from qrdm.cli import main


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert __version__ in captured.out


def test_cli_encode_decode_verify(tmp_path: Path, capsys):
    test_file = tmp_path / "hello.txt"
    test_content = "Hello, QRDM command line interface!"
    test_file.write_text(test_content, encoding="utf-8")

    pdf_out = tmp_path / "hello_qr.pdf"

    # Encode
    rc = main(["encode", str(test_file), "-o", str(pdf_out), "--minimal"])
    assert rc == 0
    assert pdf_out.is_file()

    # Verify
    rc = main(["verify", str(pdf_out)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Verification: RECOVERED" in captured.out
    assert "SHA-256 matches:      True" in captured.out

    # Decode to file
    decoded_file = tmp_path / "recovered.txt"
    rc = main(["decode", str(pdf_out), "-o", str(decoded_file)])
    assert rc == 0
    assert decoded_file.read_text(encoding="utf-8") == test_content

    # Decode to stdout
    rc = main(["decode", str(pdf_out)])
    assert rc == 0
    captured = capsys.readouterr()
    assert test_content in captured.out


def test_cli_strict_rejection(tmp_path: Path):
    bad_file = tmp_path / "bad.zip"
    bad_file.write_bytes(b"PK\x03\x04fake zip content")

    pdf_out = tmp_path / "bad.pdf"
    rc = main(["encode", str(bad_file), "-o", str(pdf_out), "--strict"])
    assert rc == 2
