# MANIFEST

File: `compatibility/manifest.json`

## Purpose

Records SteamVR build id, SteamOS build id, and SHA256 of Valve UI files Asterism may patch in Phase C. Install and future patching refuse drift.

## Notes

- Phase B does not modify listed files; hashes are still verified at install time.
- Update deliberately after SteamVR updates — never fuzzy-patch.
