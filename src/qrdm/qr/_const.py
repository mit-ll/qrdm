# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT
import csv
from enum import IntEnum
from importlib import resources

from qrcode import constants as qrconstants

__all__ = [
    "BOX_SIZE",
    "EC_CODE_PROPORTION",
    "ErrorCorrectionLevel",
    "QR_CAPACITIES",
    "QR_SIZE",
]

# Fits a grid of codes cleanly into US Letter PDF dimensions with pixel size 6
QR_SIZE: int = 22
BOX_SIZE: int = 6
# How many error-correction QR codes to generate per QR code of document content
# Applied as ceil(num_qr * EC_CODE_PROPORTION)
EC_CODE_PROPORTION: float = 0.2


class ErrorCorrectionLevel(IntEnum):
    L = qrconstants.ERROR_CORRECT_L
    M = qrconstants.ERROR_CORRECT_M
    Q = qrconstants.ERROR_CORRECT_Q
    H = qrconstants.ERROR_CORRECT_H


QR_CAPACITIES: dict[int, dict[str, int]] = {}
qr_capacity_file_path = resources.files("qrdm.qr.data").joinpath("qr_capacity.csv")
with qr_capacity_file_path.open() as f:
    reader = csv.DictReader(f)
    for ii, row in enumerate(reader, start=1):
        QR_CAPACITIES[ii] = {
            level.name: int(row[level.name]) for level in ErrorCorrectionLevel
        }
