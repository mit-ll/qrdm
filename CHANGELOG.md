# Changelog

All notable changes to this project will be documented in this file.

## [2.3.0](https://github.com/mit-ll/qrdm/tree/v2.3.0) - 2026-11-06

### Added
- **Direct Vector QR Drawing (13.7x Speedup)**: Bypassed `svglib` XML parsing by constructing ReportLab `Drawing` and `Rect` vector shapes directly from the QR matrix, improving encode throughput by up to 13.7x.
- **Adaptive Two-Tier Resolution**: Decoding now uses a fast 150 DPI rendering pass by default, seamlessly falling back to 300 DPI only when scan degradation or high-density codes require higher resolution.
- **Parallel Multi-Page Decoding**: Concurrently renders and extracts PDF pages across multi-core systems using `ThreadPoolExecutor`.
- **Standard I/O Unix Piping**: Full support for standard input and output streaming via `-` across `qrdm encode`, `qrdm decode`, and `qrdm verify`.
- **Machine-Readable CLI Verification**: Added `--json` flag to `qrdm verify` for automated CI/CD and pipeline integration.
- **Batch PDF Verification**: `qrdm verify` accepts multiple PDF paths, generating structured individual and summary audit reports.
- **Top-Level Convenience API**: Exported `qrdm.encode`, `qrdm.decode`, and `qrdm.verify` directly on the root `qrdm` module namespace.
- **Container Health Probe**: Added `GET /health` endpoint to FastAPI backend for Kubernetes and Docker container liveness/readiness probes.
- **Configurable Upload Ceilings**: Added `QRDM_MAX_UPLOAD_SIZE` setting to FastAPI backend, returning HTTP 413 (Payload Too Large) on oversized uploads.
- **Authenticated Payload Encryption (AES-256-GCM)**: Optional payload encryption at rest using AES-256-GCM and PBKDF2-HMAC-SHA256 (100,000 iterations) via `--passphrase`.
- **Decompression Bomb Defense**: Enforced streaming decompression limit (`max_uncompressed_size`) to reject zip-bomb denial-of-service attacks before large buffers are allocated.
- **Path Traversal & Filename Sanitization**: Added `sanitize_filename` utility to neutralize directory traversal (`..`), forward/backslashes, and unsafe filesystem characters.

### Changed
- Refactored PyMuPDF document lifecycle management using context managers to prevent memory leaks during multi-page batch processing.
- Cached vector logo assets across multi-page document generation.

## [2.2.0](https://github.com/mit-ll/qrdm/tree/v2.2.0) - 2026-11-05

### Added
- **Full SHA-256 integrity hash**: Replaced 64-bit truncated SHAKE-256 with standard 32-byte cryptographic SHA-256 in Protobuf wire format and models.
- **Header Hash Display**: Printed SHA-256 hash in PDF page header for human eye inspection and out-of-band comparison.
- **Verification Mode (`verify_qr_pdf` / `/verify` / `qrdm verify`)**: Non-destructive document verification reporting named check flags (`payload_valid`, `hash_matches`, `code_count_correct`, `no_unexpected_codes`, `missing_codes`).
- **Command-Line Interface (`qrdm`)**: Zero-dependency CLI entrypoint with `encode`, `decode`, and `verify` subcommands.
- **Minimal-Page Mode (`minimal_mode`)**: Suppresses verbose captions, body text, and footers, rendering only filename, truncated SHA-256, and page numbers.
- **Strict Validation Mode**: Optional enforcement rejecting NUL bytes (`0x00`), payload size overages, and binary executable/archive signatures (ZIP, DOCX/XLSX/PPTX, OLE2, ELF, PE, PDF).
- **Foreign Barcode Detection**: Ability to detect and optionally reject non-QRDM barcodes on pages (`reject_unexpected_codes`).
- **Missing Sequence Reporting**: `QRDecodeError` now tracks and reports exact missing sequence indices via `missing_codes`.
- **Deterministic PDF Output**: Set `include_timestamp=False` to omit UTC timestamp and produce bit-identical deterministic PDFs.
- **Degraded-Scan Test Suite**: Added automated regression tests simulating skew, blur, JPEG compression loss, and low DPI.
- **Security Threat Model**: Published comprehensive threat model documentation in `docs/source/threat_model.md`.
- **Self-signed TLS generator**: Added `conf/nginx/generate_certs.sh` and removed committed sample private keys from repository.
- **Offline Install Bundle**: Added `scripts/create_offline_bundle.sh` for air-gapped environments.

### Changed
- **Privacy Default**: Made printing plaintext document text opt-in (`include_text=False` by default).
- Upgraded `fitz` import to `pymupdf` to silence deprecation warnings.
- Added automatic fallback search paths for `libzbar` on macOS (`/opt/homebrew`, `/opt/miniconda3`, etc.).

### Security
- Removed committed private key (`server-key.pem`) and certificate from git history.
- Upgraded wire-format checksum from truncated 64-bit hash to SHA-256.

## [2.1.0](https://github.com/mit-ll/qrdm/tree/v2.1.0) - 2024-05-08

### Enhancements

- Better handling of error-correction codes for large input documents.

### Documentation

- Added more detailed endpoint description to Sphinx documentation.

## [2.0.2](https://github.com/mit-ll/qrdm/tree/v2.0.2) - 2024-04-18

### Fixed

- Fixed an error when calculating the integrity hash of a compressed `DocumentPayload` with trailing null bytes.

## [2.0.1](https://github.com/mit-ll/qrdm/tree/v2.0.1) - 2024-03-22

### Fixed

- Fixed an error when `decode_qr_pdf` does not detect any QR codes in the provided file.

## [2.0.0](https://github.com/mit-ll/qrdm/tree/v2.0.0) - 2024-03-20

Initial release.
