# _DEPLOY_SHELL_WS_LIVE

Script: `test/_deploy_shell_ws_live.sh`

## Purpose

Live-deploy **only** `asterism_shell.js` + `systemui.html` contenthash bump.
Does **not** modify the Valve chunk.

## Safety

- Backup as steamos user under `~/.local/share/asterism/backups/`
- Exact chunk SHA allowlist (v1, or known-broken v2 for recovery only)
- Interactive `sudo` only — never reads third-party `.env` for passwords
- Trap installed **before** `steamos-readonly disable`
- Writability probe uses `sudo touch` (not ordinary-user dir perms)
- Re-enable readonly in trap; never `|| true` on readonly ops

## Usage (Frame)

```bash
bash test/_deploy_shell_ws_live.sh
```
