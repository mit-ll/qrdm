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
    documentation](https://docs.python.org/3.9/library/codecs.html#standard-encodings).

Response:

**`200`** `application/pdf`
: PDF file containing the QR-encoded document.

### `POST /decode`

Reconstruct a source document from a QRDM PDF.

Request body schema:

- **`document`** `string <binary>`, required
  : QRDM PDF file to be decoded

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
