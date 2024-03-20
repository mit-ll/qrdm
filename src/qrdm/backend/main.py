# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT
"""Construct QRDM FastAPI Application."""

import uuid

import structlog
from fastapi import FastAPI, Request, Response
from uvicorn.protocols.utils import get_path_with_query_string

from qrdm import __version__ as VERSION
from qrdm.backend.routers import qr

__all__ = ["app"]
access_logger = structlog.stdlib.get_logger("qrdm.access")

app = FastAPI(title="QRDM", description="QR Data Manager", version=VERSION)


# Adapted from https://gist.github.com/nymous/f138c7f06062b7c43c060bf03759c29e
# MIT License - Copyright (c) 2023 Thomas GAUDIN
@app.middleware("http")
async def logging_middleware(request: Request, call_next) -> Response:
    """Middleware function for logging all incoming network requests."""
    structlog.contextvars.clear_contextvars()
    request_id = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(request_id=request_id)
    url = get_path_with_query_string(request.scope)
    if request.client is not None:
        client_host = request.client.host
        client_port = request.client.port
    else:
        client_host, client_port = None, None
    http_method = request.method
    http_version = request.scope["http_version"]

    # Pass request through to destination
    response = await call_next(request)

    # Recreate the Uvicorn access log format
    status_code = response.status_code
    request_log_str = f"{http_method} {url} HTTP/{http_version} - {status_code}"
    if request.client is not None:
        request_log_str = " - ".join([f"{client_host}:{client_port}", request_log_str])
    access_logger.info(
        request_log_str,
        http={
            "url": str(request.url),
            "status_code": status_code,
            "method": http_method,
            "version": http_version,
        },
        network={"client": {"ip": client_host, "port": client_port}},
    )
    return response


@app.get("/version", tags=["Application"], summary="Application version")
def get_version():
    """Return the version of the running QRDM application."""
    resp = {"version": app.version}
    return resp


app.include_router(qr.router)
