# Changelog

All notable changes to this project will be documented in this file.

## [2.1.0](https://github.com/mit-ll/qrdm/tree/v2.1.0) - 2024-05-08

### Enhancements

- Better handling of error-correction codes for large input documents.

### Documentation

- Added more detailed endpoint description to Sphinx documentation.

## [2.0.2](https://github.com/mit-ll/qrdm/tree/v2.0.2) - 2024-04-18

### Fixed

- Fixed an error when calculating the integrity hash of a compressed `DocumentPayload` with trailing null bytes.

## [2.0.1](https://github.com/mit-ll/qrdm/tree/v2.0.1) - 2024-03-22

### Fixed

- Fixed an error when `decode_qr_pdf` does not detect any QR codes in the provided file.

## [2.0.0](https://github.com/mit-ll/qrdm/tree/v2.0.0) - 2024-03-20

Initial release.
