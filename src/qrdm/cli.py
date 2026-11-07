# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT
"""Command-line interface for QRDM."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from qrdm import __version__
from qrdm.exceptions import QRDecodeError, QRDMError
from qrdm.models import VerifyResult, sanitize_filename
from qrdm.qr.decode import decode_qr_pdf, verify_qr_pdf
from qrdm.qr.encode import encode_qr_pdf, get_file_content


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the QRDM CLI."""
    parser = argparse.ArgumentParser(
        prog="qrdm",
        description="QR Data Manager (QRDM) — encode, decode, and verify documents as QR codes in PDFs.",
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # encode
    encode_parser = subparsers.add_parser(
        "encode", help="Encode a text document into a QR PDF."
    )
    encode_parser.add_argument(
        "input_file",
        type=str,
        help="Path to input text/csv/tsv document, or '-' to read from stdin.",
    )
    encode_parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output PDF file path (default: <input>_qr.pdf), or '-' for stdout.",
    )
    encode_parser.add_argument(
        "--header",
        default="",
        help="Optional header text printed at top and bottom of each page.",
    )
    encode_parser.add_argument(
        "--include-text",
        action="store_true",
        help="Print plaintext source document below QR codes (default: opt-in, disabled).",
    )
    encode_parser.add_argument(
        "--minimal",
        action="store_true",
        help="Minimal-page mode: print only filename, hash, and page numbers.",
    )
    encode_parser.add_argument(
        "--no-timestamp",
        action="store_true",
        help="Omit render timestamp for deterministic output.",
    )
    encode_parser.add_argument(
        "--no-ecc",
        action="store_true",
        help="Disable Reed-Solomon error correction codes.",
    )
    encode_parser.add_argument(
        "--preset",
        choices=["default", "photo", "flatbed"],
        default="default",
        help="Layout preset: 'flatbed' (dense grid for document scanners), 'photo' (larger codes with high ECC), or 'default'.",
    )
    encode_parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict validation (disallow binary/ZIP/Office/NUL bytes).",
    )
    encode_parser.add_argument(
        "--passphrase",
        type=str,
        default=None,
        help="Optional passphrase to encrypt QR payload using AES-256-GCM.",
    )

    # decode
    decode_parser = subparsers.add_parser(
        "decode", help="Decode a QR PDF back to the original source document."
    )
    decode_parser.add_argument(
        "input_pdf", type=str, help="Path to QRDM PDF file, or '-' to read from stdin."
    )
    decode_parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output file path (default: print content to stdout).",
    )
    decode_parser.add_argument(
        "--reject-unexpected",
        action="store_true",
        help="Reject non-QRDM barcodes found on pages.",
    )
    decode_parser.add_argument(
        "--passphrase",
        type=str,
        default=None,
        help="Optional passphrase to decrypt AES-256-GCM encrypted QR payload.",
    )

    # verify
    verify_parser = subparsers.add_parser(
        "verify", help="Verify a QR PDF without extracting content to disk."
    )
    verify_parser.add_argument(
        "input_pdf",
        type=str,
        nargs="+",
        help="Path(s) to QRDM PDF file(s), or '-' to read from stdin.",
    )
    verify_parser.add_argument(
        "--reject-unexpected",
        action="store_true",
        help="Fail verification if non-QRDM barcodes are found.",
    )
    verify_parser.add_argument(
        "--json",
        action="store_true",
        help="Output verification result as machine-readable JSON.",
    )
    verify_parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict validation policy during verification.",
    )
    verify_parser.add_argument(
        "--passphrase",
        type=str,
        default=None,
        help="Optional passphrase required to decrypt and verify encrypted QR payload.",
    )

    return parser


def main(args: list[str] | None = None) -> int:
    """Execute the QRDM CLI with command-line arguments."""
    parser = build_parser()
    parsed_args = parser.parse_args(args)

    if parsed_args.command == "encode":
        in_arg = str(parsed_args.input_file)
        is_stdin = in_arg == "-"
        if not is_stdin:
            in_path = Path(in_arg)
            if not in_path.is_file():
                sys.stderr.write(f"Error: Input file '{in_path}' does not exist.\n")
                return 1
            file_data = in_path.read_bytes()
            doc_name = sanitize_filename(in_path.name)
        else:
            file_data = sys.stdin.buffer.read()
            doc_name = "stdin"

        out_arg = str(parsed_args.output) if parsed_args.output else None
        is_stdout = out_arg == "-" or (is_stdin and out_arg is None)

        try:
            content = get_file_content(file_data, strict=parsed_args.strict)
            pdf_bytes = encode_qr_pdf(
                document_content=content,
                header_text=parsed_args.header,
                document_name=doc_name,
                encode_ec_codes=not parsed_args.no_ecc,
                include_text=parsed_args.include_text,
                include_timestamp=not parsed_args.no_timestamp,
                minimal_mode=parsed_args.minimal,
                preset=parsed_args.preset,
                strict=parsed_args.strict,
                passphrase=parsed_args.passphrase,
            )
            if is_stdout:
                sys.stdout.buffer.write(pdf_bytes)
                sys.stdout.buffer.flush()
            else:
                out_path = (
                    Path(out_arg)
                    if out_arg
                    else in_path.with_name(f"{in_path.stem}_qr.pdf")
                )
                out_path.write_bytes(pdf_bytes)
                sys.stdout.write(f"Encoded {doc_name} -> {out_path}\n")
            return 0
        except QRDMError as e:
            sys.stderr.write(f"Encode error: {e}\n")
            return 2

    elif parsed_args.command == "decode":
        pdf_arg = str(parsed_args.input_pdf)
        if pdf_arg == "-":
            pdf_input: str | Path | bytes = sys.stdin.buffer.read()
            pdf_name = "stdin"
        else:
            pdf_path = Path(pdf_arg)
            if not pdf_path.is_file():
                sys.stderr.write(f"Error: Input PDF '{pdf_path}' does not exist.\n")
                return 1
            pdf_input = pdf_path
            pdf_name = pdf_path.name

        try:
            doc = decode_qr_pdf(
                pdf_input,
                reject_unexpected_codes=parsed_args.reject_unexpected,
                passphrase=parsed_args.passphrase,
            )
            if parsed_args.output and str(parsed_args.output) != "-":
                out_p = Path(parsed_args.output)
                out_p.write_text(doc.content, encoding="utf-8")
                sys.stdout.write(f"Decoded {pdf_name} -> {out_p}\n")
            else:
                sys.stdout.write(doc.content)
            return 0
        except QRDecodeError as e:
            sys.stderr.write(f"Decode error: {e}\n")
            if e.missing_codes:
                sys.stderr.write(f"Missing sequence numbers: {e.missing_codes}\n")
            return 2

    elif parsed_args.command == "verify":
        inputs = parsed_args.input_pdf
        if len(inputs) == 1:
            pdf_arg = str(inputs[0])
            if pdf_arg == "-":
                pdf_input = sys.stdin.buffer.read()
            else:
                pdf_path = Path(pdf_arg)
                if not pdf_path.is_file():
                    sys.stderr.write(f"Error: Input PDF '{pdf_path}' does not exist.\n")
                    return 1
                pdf_input = pdf_path

            result: VerifyResult = verify_qr_pdf(
                pdf_input,
                reject_unexpected_codes=parsed_args.reject_unexpected,
                strict=parsed_args.strict,
                passphrase=parsed_args.passphrase,
            )

            if parsed_args.json:
                sys.stdout.write(result.model_dump_json(indent=2) + "\n")
                return 0 if result.overall else 2

            status_symbol = "✓" if result.overall else "✗"
            sys.stdout.write(
                f"[{status_symbol}] Verification: {result.status.upper()} (Overall: {'PASS' if result.overall else 'FAIL'})\n"
            )
            sys.stdout.write(f"  • Payload valid:        {result.payload_valid}\n")
            sys.stdout.write(f"  • SHA-256 matches:      {result.hash_matches}\n")
            if result.sha256:
                sys.stdout.write(f"  • SHA-256 digest:       {result.sha256}\n")
            sys.stdout.write(
                f"  • Code count correct:   {result.code_count_correct} ({result.decoded_codes}/{result.expected_codes} codes)\n"
            )
            sys.stdout.write(
                f"  • No unexpected codes:  {result.no_unexpected_codes}\n"
            )
            if result.missing_codes:
                sys.stdout.write(f"  • Missing sequences:    {result.missing_codes}\n")
            if result.unexpected_codes > 0:
                sys.stdout.write(
                    f"  • Foreign barcodes:     {result.unexpected_codes}\n"
                )
            if result.errors:
                sys.stdout.write("  • Errors:\n")
                for err in result.errors:
                    sys.stderr.write(f"      - {err}\n")

            return 0 if result.overall else 2

        # Multiple files (batch verification)
        import json

        batch_results: dict[str, VerifyResult] = {}
        all_passed = True
        for pdf_arg in inputs:
            pdf_path = Path(pdf_arg)
            if not pdf_path.is_file():
                sys.stderr.write(f"Error: Input PDF '{pdf_path}' does not exist.\n")
                all_passed = False
                continue
            r = verify_qr_pdf(
                pdf_path,
                reject_unexpected_codes=parsed_args.reject_unexpected,
                strict=parsed_args.strict,
                passphrase=parsed_args.passphrase,
            )
            batch_results[str(pdf_path)] = r
            if not r.overall:
                all_passed = False

        if parsed_args.json:
            sys.stdout.write(
                json.dumps(
                    {k: v.model_dump() for k, v in batch_results.items()}, indent=2
                )
                + "\n"
            )
            return 0 if all_passed else 2

        sys.stdout.write(f"Batch Verification Report ({len(batch_results)} files):\n")
        passed_count = 0
        for name, r in batch_results.items():
            sym = "✓" if r.overall else "✗"
            if r.overall:
                passed_count += 1
                sys.stdout.write(
                    f"  [{sym}] {name}: PASS ({r.status}, {r.decoded_codes}/{r.expected_codes} codes, SHA-256: {r.sha256[:16]}…)\n"
                )
            else:
                err_str = f" - {', '.join(r.errors)}" if r.errors else ""
                sys.stdout.write(f"  [{sym}] {name}: FAIL ({r.status}{err_str})\n")

        sys.stdout.write(
            f"\nSummary: {passed_count}/{len(batch_results)} files passed verification.\n"
        )
        return 0 if all_passed else 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
