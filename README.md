# QR Data Manager (QRDM)
QRDM provides a python package, network API endpoints, and web interfaces for encoding
and decoding documents as a series of QR codes.

## Setup and Execution

The `qrdm` package is written in pure Python; the ease of installation is dependent on
availability of its dependencies.

The simplest method of installing the `qrdm` package is via `pip`.
```sh
pip install qrdm
```

If `pip` is able to reach a suitable package index, `qrdm` will install along with its
core Python dependencies.

**IMPORTANT**
> The QR decoding functionality depends on the [`pyzbar`][pyzbar] python package, which
> in turn depends on the `zbar` shared library. This may require you to install the
> `zbar` package via your system's package manager.
> See the [`pyzbar` installation instructions][pyzbar-install] for more details.

[pyzbar]: https://github.com/NaturalHistoryMuseum/pyzbar
[pyzbar-install]: https://github.com/NaturalHistoryMuseum/pyzbar?tab=readme-ov-file#installation

Two main "package extras" are available for `qrdm` that provide REST API application
("backend") and Web application ("frontend") services for the QR encoding & decoding
functions. These can be included by specifying `qrdm[backend]` or
`qrdm[frontend]` to the installation command above, respectively.

### Web UI via Streamlit
A [Streamlit](https://streamlit.io) "frontend" can be run via:

```sh
git clone https://github.com/mit-ll/qrdm
cd qrdm
python -m pip install .[frontend]
streamlit run ui/QRDM_Home.py --client.toolbarMode=viewer
```

This will host the app at `http://localhost:8501` by default, with pages for QR encoding
and decoding. The host and port can be controlled by passing `--server.port=XXXX` and
`--server.address=X.X.X.X`, as per the syntax of the `streamlit run` command.

### REST API via FastAPI

To run the "backend" FastAPI app via uvicorn, use `uvicorn` directly. For example:
```sh
python -m pip install qrdm[backend]
uvicorn qrdm.backend:app --host localhost --port 8182
```

This will result in the app being hosted at `http://localhost:8182`. Swagger
documentation will be hosted at `http://localhost:8182/docs`, if an internet connection
is available.  Further options are available via `uvicorn` command-line configuration.

## Disclaimer

DISTRIBUTION STATEMENT A. Approved for public release: distribution unlimited.

© 2024 Massachusetts Institute of Technology

- Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014)
- SPDX-License-Identifier: MIT

This material is based upon work supported by the Name of Sponsor under Air Force
Contract No. FA8721-05-C-0002 and/or FA8702-15-D-0001. Any opinions, findings,
conclusions or recommendations expressed in this material are those of the author(s) and
do not necessarily reflect the views of the Name of Sponsor.

Delivered to the U.S. Government with Unlimited Rights, as defined in DFARS Part
252.227-7013 or 7014 (Feb 2014). Notwithstanding any copyright notice, U.S. Government
rights in this work are defined by DFARS 252.227-7013 or DFARS 252.227-7014 as detailed
above.

The software/firmware is provided to you on an As-Is basis.
