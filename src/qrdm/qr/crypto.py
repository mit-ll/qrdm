# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT
"""Cryptographic helpers for optional payload encryption at rest using AES-256-GCM."""

from __future__ import annotations

import hashlib
import os
import struct

try:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    InvalidTag = Exception  # type: ignore[assignment, misc]

from qrdm.exceptions import QRDecodeError, QREncodeError

MAGIC_ENCRYPTED: bytes = b"QRE1"
SALT_SIZE: int = 16
NONCE_SIZE: int = 12
HEADER_SIZE: int = (
    4 + SALT_SIZE + NONCE_SIZE + 4
)  # Magic (4) + Salt (16) + Nonce (12) + Length (4)
PBKDF2_ITERATIONS: int = 100_000


def is_encrypted(data: bytes) -> bool:
    """Return True if data starts with the QRDM encrypted payload header."""
    return data.startswith(MAGIC_ENCRYPTED) and len(data) >= HEADER_SIZE + 16


def encrypt_payload(data: bytes, passphrase: str) -> bytes:
    """Encrypt payload bytes using AES-256-GCM and PBKDF2-HMAC-SHA256."""
    if not HAS_CRYPTO:
        raise QREncodeError(
            "Encryption requires the 'cryptography' package. Please install it with 'pip install cryptography'."
        )
    if not passphrase:
        raise QREncodeError("Passphrase must not be empty.")

    salt = os.urandom(SALT_SIZE)
    key = hashlib.pbkdf2_hmac(
        "sha256", passphrase.encode("utf-8"), salt, PBKDF2_ITERATIONS, dklen=32
    )
    nonce = os.urandom(NONCE_SIZE)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, data, None)
    ct_len = struct.pack(">I", len(ciphertext))
    return MAGIC_ENCRYPTED + salt + nonce + ct_len + ciphertext


def decrypt_payload(encrypted_data: bytes, passphrase: str) -> bytes:
    """Decrypt AES-256-GCM payload using PBKDF2-HMAC-SHA256."""
    if not HAS_CRYPTO:
        raise QRDecodeError(
            "Decryption requires the 'cryptography' package. Please install it with 'pip install cryptography'."
        )
    if not is_encrypted(encrypted_data):
        raise QRDecodeError("Payload is not encrypted with QRDM format.")
    if not passphrase:
        raise QRDecodeError("Payload is encrypted: passphrase required to decode.")

    salt = encrypted_data[4 : 4 + SALT_SIZE]
    nonce = encrypted_data[4 + SALT_SIZE : 4 + SALT_SIZE + NONCE_SIZE]
    len_offset = 4 + SALT_SIZE + NONCE_SIZE
    ct_len = struct.unpack(">I", encrypted_data[len_offset : len_offset + 4])[0]
    ciphertext = encrypted_data[len_offset + 4 : len_offset + 4 + ct_len]

    key = hashlib.pbkdf2_hmac(
        "sha256", passphrase.encode("utf-8"), salt, PBKDF2_ITERATIONS, dklen=32
    )
    aesgcm = AESGCM(key)
    try:
        decrypted = aesgcm.decrypt(nonce, ciphertext, None)
    except InvalidTag as e:
        raise QRDecodeError(
            "Decryption failed: invalid passphrase or corrupted payload."
        ) from e
    return decrypted
