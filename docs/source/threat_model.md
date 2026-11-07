# QRDM Threat Model and Security Guarantees

This document outlines the security properties, guarantees, and explicit non-guarantees of the QR Data Manager (QRDM).

---

## What QRDM Guarantees

1. **Integrity and Corruption Detection**
   - QRDM calculates a full **SHA-256 cryptographic digest** of the canonical source document and embeds it into every QR code's metadata header.
   - The SHA-256 hash is printed in cleartext on the page header so inspectors can visually compare it against out-of-band hashes.
   - Decoders verify the full 256-bit hash upon reconstruction. If even a single byte differs or an uncorrectable corruption occurs, reconstruction is rejected.

2. **Resilience to Physical Degradation and Scan Loss**
   - QRDM employs **Reed-Solomon erasure coding** (~20% redundancy by default). If up to 20% of QR codes are completely obscured, stained, cut off, or fail to scan, the document is mathematically reconstructed without data loss.
   - Each QR code also leverages standard QR-level Reed-Solomon error correction (Medium / Quartile) against surface scratches.

3. **Opt-In Privacy Defaults**
   - By default (`include_text=False`), cleartext source content is **never** printed under QR codes.
   - Minimal-page mode (`minimal_mode=True`) strips timestamps, source metadata, and verbose captions, printing only the filename, truncated SHA-256 hash, and page numbers.

4. **Structured Verification (`qrdm verify`)**
   - The verification subsystem provides non-destructive inspection without writing recovered payloads to disk.
   - Named validation reports indicate whether payloads decoded cleanly, hashes match, sequence counts are complete, and whether unexpected or foreign barcodes appear on the page.

5. **Strict Mode Enforcement**
   - When strict mode is enabled, QRDM rejects payloads containing NUL bytes (`0x00`), payloads exceeding maximum byte limits, and documents matching binary signatures (such as ZIP, DOCX/XLSX/PPTX, OLE2, ELF, or Windows PE executables).

6. **Optional Payload Encryption at Rest (AES-256-GCM)**
   - QRDM provides built-in authenticated encryption for sensitive payloads via the `--passphrase` parameter in CLI, Python API, and HTTP REST endpoints.
   - Keys are derived using PBKDF2-HMAC-SHA256 (100,000 iterations) with a 16-byte cryptographically secure random salt and a 12-byte random nonce per document.
   - Payloads are authenticated with AES-256-GCM tags. Attempted tampering or incorrect passphrases immediately abort decoding.

7. **Decompression Bomb Protection & Hard Input Ceilings**
   - Compressed payloads are inspected using a hard streaming ceiling (`max_uncompressed_size`, 50 MB default).
   - Any inflated stream exceeding the limit is aborted before large buffers can be allocated in memory, preventing zip-bomb Denial-of-Service attacks.
   - HTTP endpoints enforce a configurable upload size ceiling (`QRDM_MAX_UPLOAD_SIZE`, 50 MB default) returning HTTP 413.

8. **Path Traversal & Filename Sanitization**
   - Input and decoded filenames are normalized and sanitized via `sanitize_filename`.
   - Relative directory traversal sequences (`..`), forward/backslashes, null bytes (`\x00`), and restricted filesystem characters are stripped or neutralized.

---

## What QRDM Does NOT Guarantee

> [!NOTE]
> **Encryption is Opt-In:**
> Unless the `--passphrase` option is explicitly supplied, QRDM compresses data using `zlib` and serializes it using Protocol Buffers and Base85. Unencrypted QRDM documents can be decoded by any compliant reader.
> 
> When confidentiality is required on physical media, always provide a strong passphrase or pre-encrypt documents.

1. **No Cryptographic Authenticity or Non-Repudiation**
   - QRDM verifies that the document matches the hash recorded in the QR metadata. However, standard QRDM does not digitally sign documents with an asymmetric private PKI key.
   - An adversary with access to the source file can generate a new, valid QRDM PDF for a modified document with a valid corresponding SHA-256 hash. If tamper-evident provenance or non-repudiation is needed, sign the payload cryptographically before encoding or sign the resulting PDF.

2. **Downstream Payload Safety**
   - QRDM reconstructs text documents faithfully. It does not sanitize content against application-level vulnerabilities such as CSV formula injection (`=cmd|...`), SQL injection, or shell script injection.
   - Downstream consumers must apply standard defensive parsing to decoded content.

3. **Extreme Degradation Boundaries**
   - While Reed-Solomon can recover from lost codes, decoding requires at least `total_codes - num_ecc` codes to be successfully read by the underlying scanner. Severe physical destruction beyond the configured error-correction budget will prevent document recovery.

