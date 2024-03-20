# QR Data Manager (QRDM)
QRDM provides a python package, network API endpoints, and web interfaces for encoding
and decoding documents as a series of QR codes.

![Diagram depicting a file becoming "encoded" into a set of QR codes, then "decoded"
back into the original document.](../docs/source/_static/qr-sketch.png)

## Setup and Execution

The `qrdm` package is written in pure Python; the ease of installation is dependent on
availability of its dependencies.

The simplest method of installing the `qrdm` package is via `pip`.
```sh
pip install qrdm
```

If `pip` is able to reach a suitable package index, `qrdm` will install along with its
core Python dependencies.

> [!IMPORTANT]
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

### Development environment

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

## Docker Support
This configuration uses docker compose (via the "docker compose plugin", vs the
docker-compose executable) to build and run a small docker ecosystem of the services,
including an nginx reverse proxy.

TLS is setup by default using Self-Signed Certificates, which are included but may also
be easily replaced with real certificates.

### Building

#### Build
`DOCKER_PUBLISH_REGISTRY` needs to be defined for the build.  If you don't have one, use
`docker.io`, otherwise substitute your organization's docker registry hostname.

If your organization uses a proxy firewall, define the `http_proxy`, `https_proxy`, and
`no_proxy` build arguments.

Note that if no `IMAGE_TAG` is specified when building/pushing, `latest` will be used.

See the following variations on invoking the build:
```sh
# Build with default docker registry, no proxy settings, tag image as "1.0.0"
DOCKER_PUBLISH_REGISTRY=docker.io \
    IMAGE_TAG=1.0.0 \
    DOCKER_ORG=myorg \
    docker compose build

# Build with default docker registry, inherit proxy settings from environment variables, tag image as "1.0.0"
DOCKER_PUBLISH_REGISTRY=docker.io \
    DOCKER_ORG=myorg \
    IMAGE_TAG=1.0.0 \
    docker compose build \
    --build-arg http_proxy \
    --build-arg https_proxy \
    --build-arg no_proxy


# Build with custom docker registry, use explicit proxy settings, tag image as "1.0.0"
DOCKER_PUBLISH_REGISTRY=registry.example.com \
    DOCKER_ORG=myorg \
    IMAGE_TAG=1.0.0 \
    docker compose build \
    --build-arg http_proxy="http://proxy.example.com:8080" \
    --build-arg https_proxy="http://proxy.example.com:8080" \
    --build-arg no_proxy="localhost,127.0.0.1,.example.com,.localdomain"
```

#### Pushing to a Docker Registry
* Make sure you are authenticated to your registry-of-choice using `docker login` or
  similar.
* Specify the registry to upload to in the `DOCKER_PUBLISH_REGISTRY` variable and use
  the `docker compose push` command.
* Use `docker.io` for the default dockerhub registry.
* Adjust the desired version tags in the docker-compose.yml

```sh
DOCKER_PUBLISH_REGISTRY=registry.example.com \
    IMAGE_TAG=1.0.0 \
    docker compose push
```

Pushing is optional - you can build and run without ever pushing the resulting images to
a docker registry.

### Running
The ecosystem injects the name of the running host into the runtime.  The example here
assumes `hostname -f` will produce a fully-qualified domain name of the public facing
name of the host.  If that is not the case, update the method used to set
`DOCKER_HOST_FQDN`.

* `DOCKER_HOST_FQDN`: Fully qualified domain name that clients/browsers will use to
  access the runtime.
* `DOCKER_PUBLISH_REGISTRY`: registry name used to build and/or host the built docker
  images.  Use docker.io if you do not have a custom/private registry.
* `DOCKER_ORG`: Name of the Organization path where the image will be hosted on
  dockerhub or your private docker registry

```sh
DOCKER_PUBLISH_REGISTRY=docker.io \
    DOCKER_HOST_FQDN=$(hostname -f) \
    DOCKER_ORG=mycompany \
    IMAGE_TAG=1.0.0 \
    docker compose up
```

#### Running with bundled docker-compose.yml
If all you have is one of the QRDM docker images, it is possible to run the ecosystem by
extracting the bundled docker-compose.yml configuration and running in a single command.

To run out of docker hub, use values such as
* `QRDM-IMAGE: qrdm-ui`
* `DOCKER_PUBLISH_REGISTRY: docker.io`
* `DOCKER_ORG: mitll`

Images pulled onto your local system from some other registry, or built locally, may
need different values.

```sh
docker run --rm -it --entrypoint cat <QRDM-IMAGE> /app/docker-compose.yml  > /tmp/docker-compose.yml \
    && DOCKER_HOST_FQDN=$(hostname -f) \
        DOCKER_PUBLISH_REGISTRY=<registry-ie-docker.io> \
        DOCKER_ORG=mycompany \
        docker compose -f /tmp/docker-compose.yml up
```

#### Endpoints
* https://example.com/qrdm-ui - simple UI to upload/encode/download QR files
* https://example.com/qrdm-api - REST API for performing QRDM operations
* https://example.com/qrdm-api/docs - OpenAPI/Swagger docs for REST API


### Generate new Diffie-Hellman Parameters
Do this for any new installation/deployment.  It will take several minutes to complete.
For development or test, this can be skipped and the default parameter file can be left
as-is.
```sh
cd conf/nginx/conf.d
openssl dhparam -out dhparam.pem 4096
```

### Generate new self-signed certificate for SSL/TLS
To generate a new self-signed certificate, use or adapt the following:
```sh
cd conf/nginx/private
openssl req -x509 -newkey rsa:4096 -keyout server-key.pem -out server-cert.pem -sha256 \
    -days 3650 -nodes -subj "/CN=qrdm"
```

### Install real server certificate
To install a real server certificate which has been issued by a trusted Certificate
Authority,
* Copy the server certificate in PEM/CRT form into conf/nginx/private/server-cert.pem
  * This PEM should include the server certificate as the first entry, and the
    chain of trust from the server to the root CA PEMs concatenated into the file.
    This is usually one of the standard formats provided by Certificate Authorities.
* Copy the server key in PEM/CRT format into conf/nginx/private/server-key.pem

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
