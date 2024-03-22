# Docker Configuration

Files for configuring `qrdm` to run in a Dockerized environment are included in the
source code repository, which can be obtained via:
```sh
git clone https://github.com/mit-ll/qrdm
```

This configuration uses docker compose (via the "docker compose plugin", vs the
docker-compose executable) to build and run a small docker ecosystem of the services,
including an nginx reverse proxy.

TLS is setup by default using Self-Signed Certificates, which are included but may also
be easily replaced with real certificates.

## Building

### Build
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

### Pushing to a Docker Registry
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

## Running
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

### Running with bundled docker-compose.yml
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

### Endpoints
* `https://example.com/qrdm-ui` - simple UI to upload/encode/download QR files
* `https://example.com/qrdm-api` - REST API for performing QRDM operations
* `https://example.com/qrdm-api/docs` - OpenAPI/Swagger docs for REST API


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
* Copy the server certificate in PEM/CRT form into `conf/nginx/private/server-cert.pem`
  * This PEM should include the server certificate as the first entry, and the
    chain of trust from the server to the root CA PEMs concatenated into the file.
    This is usually one of the standard formats provided by Certificate Authorities.
* Copy the server key in PEM/CRT format into `conf/nginx/private/server-key.pem`
