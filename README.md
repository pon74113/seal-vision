# Seal Vision

Windows foreground helper for Seal through a maximized AnyDesk window.

## Updates
Use **ตรวจหาอัปเดต** then **อัปเดตเลย** in version 1.3 or later. Updates preserve local settings and use the existing launcher. Release ZIP files contain only the two runtime modules and a checksum manifest.

This release updates an existing configured installation. It is not a complete fresh installer: OCR runtime and the reference asset must already be installed locally. AnyDesk must remain visible in the foreground. Background input and automatic reconnection are not implemented in this release.

## Release process
Package seal_app.py and vision_tracker.py with version.json (product SealVision, version, launcher_min 1, sha256 for both files). Attach SealVision-update-VERSION.zip to a matching vVERSION GitHub release. The updater verifies GitHub asset SHA-256 and the package manifest before staging installation.

No credentials, connection identifiers, screenshots or play logs are included.
