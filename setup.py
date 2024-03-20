# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT

# This file is just a thin wrapper to enable things like `python setup.py --version`.
# All meaningful setup configuration is contained in pyproject.toml
"""Shim for `setup.py` invocations."""

import setuptools

setuptools.setup()
