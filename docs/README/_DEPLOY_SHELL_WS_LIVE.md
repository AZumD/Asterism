# _DEPLOY_SHELL_WS_LIVE

Script: `test/_deploy_shell_ws_live.sh`

## Purpose

Live-deploy **only** `asterism_shell.js` + `systemui.html` contenthash bump.
Does **not** modify the Valve chunk.

## Safety

- Backup as steamos user under `~/.local/share/asterism/backups/`
- Verify bridged chunk hash (v1) or recognize v2
- Interactive `sudo` only — never reads third-party `.env` for passwords
- `steamos-readonly disable` → verify writable → install → `enable` → verify
- Trap re-enables readonly on failure
- Failures abort (no silent `|| true` on readonly ops)

## Usage (Frame)

```bash
bash test/_deploy_shell_ws_live.sh
```
