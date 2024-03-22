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

## Dependencies

The core dependencies of `qrdm` are:

- `python` version 3.9 or later
- `charset-normalizer` version 3.2 or later
- `Pillow` version 10.1 or later
- `protobuf` version 4.22 or later
- `pydantic` version 2.2 or later
- `pydantic-settings`
- `PyMuPDF` version 1.22 or later
- `pyzbar` version 0.1.8 or later
- `qrcode` version 7.3 or later
- `reedsolo` version 1.7.0 or later
- `reportlab` version 4.0 or later
- `structlog` version 23.0 or later
- `svglib` version 1.5 or later

The Web UI functionality depends on:

- `streamlit` version 1.28 or later

The REST API application functionality depends on:
- `fastapi` version 0.109
- `python-multipart` version 0.0.6 or later
- `starlette[full]`
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
