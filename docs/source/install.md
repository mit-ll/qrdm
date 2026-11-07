# Getting Started

## Installation
The `qrdm` package is written in pure Python; the ease of installation is dependent on
availability of its dependencies.

The simplest method of installing the `qrdm` package is via `pip`.
```sh
pip install qrdm
```

If `pip` is able to reach a suitable package index, `qrdm` will install along with the
core Python dependencies listed below.

:::{important}
The QR decoding functionality depends on the [`pyzbar`][pyzbar] python package, which in
turn depends on the `zbar` shared library. This may require you to install the `zbar`
package via your system's package manager.
See the [`pyzbar` installation instructions][pyzbar-install] for more details.
:::

[pyzbar]: https://github.com/NaturalHistoryMuseum/pyzbar
[pyzbar-install]: https://github.com/NaturalHistoryMuseum/pyzbar?tab=readme-ov-file#installation

Two main "package extras" are available for `qrdm` that provide REST API application
("backend") and Web application ("frontend") services for the QR encoding & decoding
functions. These can be included by specifying `qrdm[backend]` or
`qrdm[frontend]` to the installation command above, respectively.

## Command-Line Interface (CLI)

QRDM provides a standalone command-line executable `qrdm` for encoding, decoding, and verifying documents without a server:

```sh
# Encode a text/CSV document to a QR PDF (minimal mode)
qrdm encode document.csv -o document_qr.pdf --minimal

# Optionally encrypt the payload at rest using AES-256-GCM
qrdm encode document.csv -o secret_qr.pdf --passphrase "vault-passphrase"

# Verify a QR PDF without writing extracted files to disk
qrdm verify document_qr.pdf

# Output machine-readable verification JSON
qrdm verify document_qr.pdf --json

# Batch verification across multiple files
qrdm verify doc1_qr.pdf doc2_qr.pdf doc3_qr.pdf

# Decode a QR PDF back to the original text
qrdm decode document_qr.pdf -o recovered.csv

# Unix piping support via standard I/O ('-')
cat data.txt | qrdm encode - | qrdm decode -
```

## Dependencies

The core dependencies of `qrdm` are:

- `python` version 3.10 or later
- `charset-normalizer` version 3.2 or later
- `cryptography` version 42.0 or later
- `Pillow` version 10.1 or later
- `protobuf` version 4.22 or later
- `pydantic` version 2.2 or later
- `pydantic-settings`
- `PyMuPDF` version 1.23 or later
- `pyzbar` version 0.1.8 or later
- `qrcode` version 7.3 or later
- `reedsolo` version 1.7.0 or later
- `reportlab` version 4.0 or later
- `structlog` version 23.0 or later
- `svglib` version 1.5 or later

The Web UI functionality depends on:

- `streamlit` version 1.28 or later

The REST API application functionality depends on:
- `fastapi` version 0.115 or later
- `python-multipart` version 0.0.9 or later
- `starlette` version 0.40 or later
- `uvicorn[standard]`


## Development environment

Alternatively, a development environment may be set up via:
```sh
git clone https://github.com/mit-ll/qrdm
cd qrdm
python -m pip install -e .[dev]
```
to create an "editable" install that will respond to local file changes, and contains
both the `frontend` and `backend` dependencies in addition to all of the
requirements for local development and testing.

The package's tests can then be run directly in the development environment via:
```sh
pytest ./tests
```

Alternatively, the package is also configured to use [`tox`](https://tox.wiki) to
perform tests across multiple python versions via:
```sh
tox
```
See the configuration in `tox.ini` in the repository root for details on the test stage
configuration and outputs.
