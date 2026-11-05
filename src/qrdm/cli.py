# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT
"""Command-line interface for QRDM."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from qrdm import __version__
from qrdm.exceptions import QRDMError, QRDecodeError, QREncodeError
from qrdm.models import VerifyResult
from qrdm.qr.decode import decode_qr_pdf, verify_qr_pdf
from qrdm.qr.encode import encode_qr_pdf, get_file_content


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qrdm",
        description="QR Data Manager (QRDM) — encode, decode, and verify documents as QR codes in PDFs.",
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # encode
    encode_parser = subparsers.add_parser("encode", help="Encode a text document into a QR PDF.")
    encode_parser.add_argument("input_file", type=Path, help="Path to input text/csv/tsv document.")
    encode_parser.add_argument(
        "-o", "--output", type=Path, default=None, help="Output PDF file path (default: <input>_qr.pdf)."
    )
    encode_parser.add_argument(
        "--header", default="", help="Optional header text printed at top and bottom of each page."
    )
    encode_parser.add_argument(
        "--include-text", action="store_true", help="Print plaintext source document below QR codes (default: opt-in, disabled)."
    )
    encode_parser.add_argument(
        "--minimal", action="store_true", help="Minimal-page mode: print only filename, hash, and page numbers."
    )
    encode_parser.add_argument(
        "--no-timestamp", action="store_true", help="Omit render timestamp for deterministic output."
    )
    encode_parser.add_argument(
        "--no-ecc", action="store_true", help="Disable Reed-Solomon error correction codes."
    )
    encode_parser.add_argument(
        "--preset",
        choices=["default", "photo", "flatbed"],
        default="default",
        help="Layout preset: 'photo' (larger codes for cameras), 'flatbed' (dense grid for scanners), or 'default'.",
    )
    encode_parser.add_argument(
        "--strict", action="store_true", help="Enable strict validation (disallow binary/ZIP/Office/NUL bytes)."
    )

    # decode
    decode_parser = subparsers.add_parser("decode", help="Decode a QR PDF back to the original source document.")
    decode_parser.add_argument("input_pdf", type=Path, help="Path to QRDM PDF file.")
    decode_parser.add_argument(
        "-o", "--output", type=Path, default=None, help="Output file path (default: print content to stdout)."
    )
    decode_parser.add_argument(
        "--reject-unexpected", action="store_true", help="Reject non-QRDM barcodes found on pages."
    )

    # verify
    verify_parser = subparsers.add_parser("verify", help="Verify a QR PDF without extracting content to disk.")
    verify_parser.add_argument("input_pdf", type=Path, help="Path to QRDM PDF file.")
    verify_parser.add_argument(
        "--reject-unexpected", action="store_true", help="Fail verification if non-QRDM barcodes are found."
    )

    return parser


def main(args: Optional[list[str]] = None) -> int:
    parser = build_parser()
    parsed_args = parser.parse_args(args)

    if parsed_args.command == "encode":
        in_path: Path = parsed_args.input_file
        if not in_path.is_file():
            sys.stderr.write(f"Error: Input file '{in_path}' does not exist.\n")
            return 1

        out_path: Path = parsed_args.output or in_path.with_name(f"{in_path.stem}_qr.pdf")

        try:
            file_data = in_path.read_bytes()
            content = get_file_content(file_data, strict=parsed_args.strict)
            encode_qr_pdf(
                document_content=content,
                path=out_path,
                header_text=parsed_args.header,
                document_name=in_path.name,
                encode_ec_codes=not parsed_args.no_ecc,
                include_text=parsed_args.include_text,
                include_timestamp=not parsed_args.no_timestamp,
                minimal_mode=parsed_args.minimal,
                preset=parsed_args.preset,
                strict=parsed_args.strict,
            )
            sys.stdout.write(f"Encoded {in_path.name} -> {out_path}\n")
            return 0
        except QRDMError as e:
            sys.stderr.write(f"Encode error: {e}\n")
            return 2

    elif parsed_args.command == "decode":
        pdf_path: Path = parsed_args.input_pdf
        if not pdf_path.is_file():
            sys.stderr.write(f"Error: Input PDF '{pdf_path}' does not exist.\n")
            return 1

        try:
            doc = decode_qr_pdf(
                pdf_path,
                reject_unexpected_codes=parsed_args.reject_unexpected,
            )
            if parsed_args.output:
                parsed_args.output.write_text(doc.content, encoding="utf-8")
                sys.stdout.write(f"Decoded {pdf_path.name} -> {parsed_args.output}\n")
            else:
                sys.stdout.write(doc.content)
            return 0
        except QRDecodeError as e:
            sys.stderr.write(f"Decode error: {e}\n")
            if e.missing_codes:
                sys.stderr.write(f"Missing sequence numbers: {e.missing_codes}\n")
            return 2

    elif parsed_args.command == "verify":
        pdf_path: Path = parsed_args.input_pdf
        if not pdf_path.is_file():
            sys.stderr.write(f"Error: Input PDF '{pdf_path}' does not exist.\n")
            return 1

        result: VerifyResult = verify_qr_pdf(
            pdf_path,
            reject_unexpected_codes=parsed_args.reject_unexpected,
        )

        status_symbol = "✓" if result.overall else "✗"
        sys.stdout.write(f"[{status_symbol}] Verification: {result.status.upper()} (Overall: {'PASS' if result.overall else 'FAIL'})\n")
        sys.stdout.write(f"  • Payload valid:        {result.payload_valid}\n")
        sys.stdout.write(f"  • SHA-256 matches:      {result.hash_matches}\n")
        if result.sha256:
            sys.stdout.write(f"  • SHA-256 digest:       {result.sha256}\n")
        sys.stdout.write(f"  • Code count correct:   {result.code_count_correct} ({result.decoded_codes}/{result.expected_codes} codes)\n")
        sys.stdout.write(f"  • No unexpected codes:  {result.no_unexpected_codes}\n")
        if result.missing_codes:
            sys.stdout.write(f"  • Missing sequences:    {result.missing_codes}\n")
        if result.unexpected_codes > 0:
            sys.stdout.write(f"  • Foreign barcodes:     {result.unexpected_codes}\n")
        if result.errors:
            sys.stdout.write(f"  • Errors:\n")
            for err in result.errors:
                sys.stderr.write(f"      - {err}\n")

        return 0 if result.overall else 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
