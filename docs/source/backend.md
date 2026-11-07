# REST API

To run the backend FastAPI app via uvicorn, use `uvicorn` directly. For example:
```sh
python -m pip install qrdm[backend]
uvicorn qrdm.backend:app --host localhost --port 8182
```

This will result in the app being hosted at `http://localhost:8182`. Swagger
documentation will be hosted at `http://localhost:8182/docs` if an internet connection
is available.  Further options are available via `uvicorn` command-line configuration.

:::{image} _static/swagger-api-docs.png
:alt: A browser window showing Swagger API documentation of the QRDM FastAPI application
:::

## Endpoints

### `POST /encode`

Convert a plaintext document to a PDF containing the document encoded as QR codes.

Request body schema:

- **`document`** `string <binary>`, required
  : File to be QR-encoded

- **`header_text`** `string`, optional
  : Text to include as header & footer of QR PDF. Defaults to `""`.

- **`metadata`** `application/json`, optional
  : Text in this field will be treated as JSON, and encoded alongside the document
    contents in the QR PDF. Defaults to `null`.

- **`encoding`** `string`, optional
  : Encoding used to decode the document file data into a string. If not provided,
    defaults to automatic detection via the `charset_normalizer` package. Valid
    encodings can be found in the [Python standard library
    documentation](https://docs.python.org/3.10/library/codecs.html#standard-encodings).

- **`include_text`** `boolean`, optional
  : Whether to print plaintext document text underneath QR codes. Defaults to `false`
    (opt-in for privacy).

- **`minimal_mode`** `boolean`, optional
  : When `true`, produces minimal pages containing only filename, SHA-256 hash, and page
    numbers. Defaults to `false`.

- **`preset`** `string`, optional
  : Layout preset: `'default'` (6 codes/page), `'flatbed'` (12 codes/page for dense scanner grids),
    or `'photo'` (4 large codes/page with higher error correction).

- **`passphrase`** `string`, optional
  : Optional passphrase to encrypt the QR payload at rest using AES-256-GCM and PBKDF2-HMAC-SHA256 key derivation.

Response:

**`200`** `application/pdf`
: PDF file containing the QR-encoded document.

### `GET /health`

Application health check for container liveness and readiness probes.

Response:

**`200`** `application/json`
: `{"status": "ok", "version": "<app_version>"}`

### `POST /verify`

Verify a QRDM PDF document without extracting or writing files to disk.

Request body schema:

- **`document`** `string <binary>`, required
  : QRDM PDF file to be verified

- **`reject_unexpected_codes`** `boolean`, optional
  : Whether to fail verification if non-QRDM or foreign barcodes appear on pages.
    Defaults to `false`.

- **`passphrase`** `string`, optional
  : Passphrase required to decrypt and verify the document payload if encrypted.

Response:

**`200`** `application/json`

- **`overall`** `boolean`
  : Overall verification pass/fail status
- **`status`** `string`
  : Detailed recovery status: `"recovered"`, `"partial"`, or `"failed"`
- **`payload_valid`** `boolean`
  : Whether QR payloads and Reed-Solomon symbols decode cleanly
- **`hash_matches`** `boolean`
  : Whether the reconstructed payload matches the document SHA-256
- **`code_count_correct`** `boolean`
  : Whether all expected sequence numbers were decoded
- **`no_unexpected_codes`** `boolean`
  : Whether any non-QRDM or malformed barcodes were detected
- **`missing_codes`** `list[integer]`
  : List of missing sequence indices, if any
- **`decoded_codes`** `integer`
  : Number of QR codes successfully decoded
- **`expected_codes`** `integer`
  : Total expected QR codes
- **`sha256`** `string`
  : Verified SHA-256 hex digest of the document
- **`errors`** `list[string]`
  : Error descriptions if verification failed

### `POST /decode`

Reconstruct a source document from a QRDM PDF.

Request body schema:

- **`document`** `string <binary>`, required
  : QRDM PDF file to be decoded

- **`passphrase`** `string`, optional
  : Passphrase required to decrypt the payload if the document was encrypted.

Response:

**`200`** `application/json`

- **`content`** `string`
  : Original document contents

- **`metadata`** `application/json`
  : JSON representation of data provided to the `metadata` field of the `/encode`
  endpoint.


## Configuration

Configuration of the application is performed via environment variables, as follows:

**`QRDM_ERROR_TOLERANCE`**
: One of `LOW`, `MEDIUM`, `QUARTILE`, `HIGH`

  Error correction level of the individual QR codes. Defaults to `MEDIUM`.

**`QRDM_ENCODE_EC_CODES`**
: `true` or `false`

  Whether to include additional error-correcting QR codes. These are useful when
  individual QR codes fail to scan. Defaults to `true`.

**`QRDM_INCLUDE_TEXT`**
: `true` or `false`

  Whether to print plaintext document text underneath QR codes. Defaults to `false`.

**`QRDM_MAX_UPLOAD_SIZE`**
: integer (bytes)

  Maximum allowed upload file size in bytes. Files larger than this will be rejected
  with HTTP 413 Payload Too Large. Defaults to `52428800` (50 MB).

**`QRDM_LOG_LEVEL`**
: One of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

  Restricts output logs to the specified level and higher. Defaults to `INFO`, which
  includes log events for each encode & decode event, as well as general network request
  events.

**`QRDM_JSON_LOGS`**
: `true` or `false`

  When `false`, logs are output to the console via stderr, with the human-centric
  output formatting provided by [`structlog`](https://www.structlog.org).

  When `true`, logs are output to stdout with a single line of JSON-formatted text per
  log event, which can be aggregated via the applications execution environment.
  Structured event data is populated for each QR encode & decode event, in addition to
  HTTP metadata for each network request.

  Defaults to `false`.
