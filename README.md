# Seal Vision

Download **SealVision.exe** from the latest GitHub release. Windows x64; no separate Python installation required. The executable includes OCR dependencies and a reference bag image. AnyDesk itself must already be installed or downloaded from its official site.

## Controls
- Connect AnyDesk: sends a normal session request to the locally saved address. Remote acceptance is still required where configured.
- Start F8: foreground image recognition, Tab targeting, keys 1/2 skills, key 3 when AP is below 50%, Space for red bags.
- Stop F9: stops gameplay and automatic dialog handling.
- Check for updates: downloads a release ZIP, verifies GitHub SHA-256 and the package manifest, then restarts the same launcher.

## Automatic dialog handling (1.6)
After Connect or Start, a foreground AnyDesk window is checked for the supplied Session Closed dialog and the Global Settings title bar. The program can press Retry (30-second cooldown) or minimize Global Settings (5-second cooldown), after two matching observations. Gameplay pauses while these dialogs are present and waits for confirmed AP readings to resume. Other windows are not minimized. This does not change authentication, security settings, permissions or licensing.

This is a foreground helper. Keep the reference AnyDesk layout visible. Background operation is not supported. Recognition has been checked on supplied fixtures at multiple scales; live behavior depends on the displayed layout.

## Release packaging
The stable launcher loads locally installed runtime modules. A runtime update ZIP contains seal_app.py, vision_tracker.py and version.json (product SealVision, version, launcher_min 1, sha256 for both modules). A matching vVERSION release contains SealVision-update-VERSION.zip and optionally the complete EXE. User settings, connection addresses, screen captures and play logs are excluded from this repository.
