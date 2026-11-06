# QRDM Format Specification (v2.2.0)

This document specifies the canonical data pipeline, wire format, Protobuf schema, and error-correction protocol implemented by the QR Data Manager (QRDM).

---

## 1. Overview and Architecture

QRDM converts arbitrary UTF-8 text documents (and optional structured JSON metadata) into a physical, printable PDF consisting of a grid of QR codes, resilient to physical paper damage and scan distortion.

```
Source Document (UTF-8) + JSON Metadata
                  │
                  ▼
       Protobuf Serialization (`DocumentPayload`)
                  │
                  ▼
          zlib Compression (Level 9)
                  │
                  ▼
          SHA-256 Digest Calculation (32 bytes)
                  │
                  ▼
        Fixed-size Fragmentation (split by QR capacity)
                  │
                  ▼
      Reed-Solomon Erasure Coding (~20% overhead)
                  │
                  ▼
       Protobuf Encapsulation (`QRContent` + `QRMeta`)
                  │
                  ▼
             Base85 Encoding
                  │
                  ▼
           QR Code Generation (Version 1–40)
                  │
                  ▼
             ReportLab PDF Layout
```

---

## 2. Wire Format and Protobuf Schema

All metadata and payloads are serialized via Protocol Buffers.

### `qrdm.proto`

```protobuf
syntax = "proto3";

package qrdm;

message DocumentPayload {
    bytes content = 1;
    optional string metadata = 2;
    enum DataType {
        UTF8_STRING = 0;
    }
    DataType data_type = 3;
}

message QRContent {
    message QRMeta {
        bytes document_hash = 1;     // 32-byte SHA-256 digest of compressed document
        uint32 sequence_number = 2;   // 0-indexed fragment order
        uint32 total_qr_codes = 3;    // Total QR codes including Reed-Solomon codes
        uint32 num_ecc = 4;           // Number of Reed-Solomon error correction codes
    }
    QRMeta meta = 1;
    bytes doc_fragment = 2;
}
```

---

## 3. Data Pipeline Specification

### Step 1: Document Serialization
The input string and optional JSON metadata are encoded into a `DocumentPayload` protobuf object. `data_type` is set to `UTF8_STRING` (`0`).

### Step 2: Compression & Hash Calculation
1. The serialized protobuf bytes are compressed using standard `zlib` compression with compression level `Z_BEST_COMPRESSION` (level 9).
2. The integrity hash is computed over the compressed bytes with any trailing null padding stripped:
   $$\text{document\_hash} = \text{SHA-256}(\text{compressed\_bytes.strip}(\texttt{\\0}))$$
3. The resulting 32-byte binary digest is recorded in `QRMeta.document_hash` across all generated QR codes, and formatted as a 64-character lowercase hex string on the PDF header.

### Step 3: Fragmentation
The maximum payload capacity per QR code is determined by:
$$\text{single\_qr\_payload\_size} = \left\lfloor \frac{\text{raw\_capacity} - \text{PROTOBUF\_RESERVED\_LEN}}{5} \right\rfloor \times 4$$
Where:
- $\text{raw\_capacity}$ is the binary capacity of the selected QR code version and error tolerance level (e.g. Version 22 Medium = 1009 bytes).
- $\text{PROTOBUF\_RESERVED\_LEN}$ reserves space for the Protobuf field keys, lengths, and `QRMeta` structure (47 bytes for SHA-256).
- The $\times 4/5$ factor accounts for Base85 expansion.

If the document exceeds `single_qr_payload_size`, it is sliced into equal-length chunks. If the final chunk is shorter, it is right-padded with null bytes (`\x00`).

### Step 4: Reed-Solomon Erasure Coding
To protect against entire missing or unreadable QR codes on the page, QRDM applies Reed-Solomon erasure coding across the payload fragments:
- The default proportion is $e = 0.20$ (20% redundant codes).
- The number of parity codes is $\text{num\_ecc} = \min\left(\left\lceil \frac{256 \cdot e}{1 + e} \right\rceil, \lceil n_{\text{raw}} \cdot e \rceil\right)$.
- Parity symbols are generated column-wise across the aligned byte positions of the payload fragments using Galois Field $GF(2^8)$.
- Any subset of decoded QR codes of size $\ge (n_{\text{total}} - \text{num\_ecc})$ is mathematically guaranteed to recover all original fragments.

### Step 5: Base85 Encoding & QR Generation
Each fragment is wrapped in a `QRContent` message and encoded using Python's standard `base64.b85encode`. The resulting ASCII payload is embedded into an ISO/IEC 18004 QR code.

---

## 4. Presets and Layout Geometry

| Preset | Target Device | Module Box Size | QR Version | QR ECC | RS Parity ($e$) | Codes / Page |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **`default`** | Balanced | 6 (~2.5 in) | 22 | Medium (15%) | 20% | 6 |
| **`flatbed`** | Flatbed Scanners | 5 (~2.0 in) | 24 | Medium (15%) | 15% | 12 |
| **`photo`** | Smartphone Cameras | 8 (~3.3 in) | 20 | Quartile (25%) | 25% | 4 |

---

## 5. Decoding and Verification Protocol

1. **Page Extraction**: Render PDF pages at 300 DPI into uncompressed bitmaps.
2. **Barcode Scan**: Detect QR codes via `pyzbar`. If scan count $< (n_{\text{total}} - \text{num\_ecc})$, apply progressive box-blur filters to recover damaged codes.
3. **Foreign Code Filter**: When `reject_unexpected_codes=True`, reject non-QRDM barcodes.
4. **Erasure Decoding**: Fill missing sequence indices with erasure markers and decode via `reedsolo.RSCodec`.
5. **Integrity Check**: Strip trailing null bytes, compute SHA-256, and compare against `first_code.meta.document_hash`.
6. **Strict Validation**: If enabled, confirm payload does not violate size limits, contains no NUL bytes, and has no banned binary signatures.
