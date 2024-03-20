# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT
# ruff: noqa: E402
import json
from typing import Any

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from qrdm.backend import app

client = TestClient(app)
payload = """
    Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor
    incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud
    exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.  Duis aute
    irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla
    pariatur.  Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia
    deserunt mollit anim id est laborum.
    😎🎃🐋
    Zażółć gęślą jaźń
    Съешь же ещё этих мягких французских булок, да выпей чаю
    以呂波耳本部止 千利奴流乎和加 餘多連曽津祢那 良牟有為能於久 耶万計不己衣天 阿佐伎喩女美之 恵比毛勢須
    """


def test_qr_encode():
    response = client.post(
        "/encode", files={"document": ("payload.txt", payload.encode("utf-8"))}
    )
    assert response.is_success


@pytest.mark.parametrize(
    "metadata",
    [None, "Test data", {"author": "MIT Lincoln Laboratory"}],
    ids=["no_meta", "str_meta", "dict_meta"],
)
def test_qr_encode_and_decode(metadata):
    encoding_data: dict[str, Any] = {}
    if metadata is not None:
        encoding_data["metadata"] = json.dumps(metadata)

    encode_response = client.post(
        "/encode",
        files={"document": ("payload.txt", payload.encode("utf-8"))},
        data=encoding_data,
    )
    assert encode_response.is_success

    decode_response = client.post(
        "/decode", files={"document": ("payload.pdf", encode_response.content)}
    )
    assert decode_response.is_success
    response_data = decode_response.json()
    assert response_data["content"] == payload
    if metadata is not None:
        assert response_data["metadata"] == metadata
    else:
        assert "metadata" not in response_data
