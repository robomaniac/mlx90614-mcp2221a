# Version index, provenance and checksums

> **Migration update — 2026-10-09:** The fetched `https://jeromedemers.com/mlx.html` exactly matched historical revision 07, and the user reports it works. Active `08_Software/mlx90614-webhid/mlx.html` now blocks automatic USB reset and retains read-error/attempt evidence. Hardware validation of these edits is pending. See [current review](PROJECT_REVIEW.md) and [validation](../05_Data/VALIDATION.md). Earlier sections describe the original development history.

The archive exists to permit real A/B testing rather than hand-waving about which revision changed I2C startup.

**Important:** File names describe the development sequence. The user did **not** explicitly confirm every version works. `03` is only the nearest surviving snapshot to the high-rate user log; it may not exactly match the deployed website file. `07` matched the original handoff and fetched hosted site. The active source has migrated diagnostic/reset changes and is no longer identical; its hardware validation is pending.

| Source file | Bytes | SHA-256 (first 16 chars) | Context |
| --- | ---: | --- | --- |
| `99_Archive/webhid-history/01-first-singlefile.html` | 36,908 | `13e493d9e2f8ad80` | First WebHID single-file iteration; proof of concept and early working behavior. |
| `99_Archive/webhid-history/02-samples-tooltip.html` | 44,872 | `af76787bf4334a25` | Sample history increase, sample-rate choices and mouse hover. |
| `99_Archive/webhid-history/03-dropdown-last-reading-baseline.html` | 50,997 | `463e33449d486cde` | Closest available archived version preceding user logs of successful 10 Hz readings; custom dropdown. |
| `99_Archive/webhid-history/04-logging-and-retry.html` | 53,838 | `78709a20a4feb707` | Log line-break/cap and read retry changes. Subsequent startup behavior not verified. |
| `99_Archive/webhid-history/05-speed-set-retry.html` | 54,951 | `db8e9d4b00e51797` | Retry/cancel changes for speed set 0x21; user still reported busy. |
| `99_Archive/webhid-history/06-skip-initial-cancel.html` | 64,072 | `87095b9b0922ba92` | Skip cancel for apparently fresh state; user still got 0x21 and 0x94 busy. |
| `99_Archive/webhid-history/07-latest-soft-reset-recovery.html` | 68,661 | `2b252a1eb651d16f` | Experimental soft reset and reconnect path; unverified on hardware. |
| `08_Software/mlx90614-webhid/mlx.html` | See current manifest | See current manifest | Active migration revision: reset blocked; failed-read evidence and pair counters corrected. |

## Provenance

Before migration, root `mlx.html` was an exact copy of the uploaded last snapshot and matched the `mlx90614_webhid_singlefile_busyfix.zip` latest path. The unchanged original is now historical revision 07 and also retained in the local full backup. Active HTML has the small changes described in `PROJECT_REVIEW.md`. All `99_Archive/webhid-history/*.html` files were **extracted unchanged** from assistant-generated ZIPs that were preserved in the session. The Python app was extracted unchanged from `mlx90614_bundle_updated.zip`. Copies of those original ZIP releases are in `99_Archive/original-releases/` for preservation.

Available preceding release names were `mlx90614_webhid_singlefile.zip`, `..._fixed.zip`, `..._ui_match.zip`, `..._logfix.zip`, `..._speedfix.zip`, `..._uninitialized_fix.zip`, and `..._busyfix.zip`. The files are unpacked for direct VS Code diffs.

## How to compare in VS Code

1. Right-click `99_Archive/webhid-history/03-dropdown-last-reading-baseline.html` and choose **Select for Compare**.
2. Right-click `08_Software/mlx90614-webhid/mlx.html` and choose **Compare with Selected**.
3. Search the diff for `cancelI2cTransfer`, `setI2CSpeed`, `prepareI2cEngineWithRecovery`, `getStatus`, `rawExchangeWithMode`, `softResetAndReconnectDevice`, and the `connect` startup sequence.

## Byte-level checks

For full SHA-256, run `node 08_Software/mlx90614-webhid/tools/check_html.mjs` (if Node.js is installed) or PowerShell `Get-FileHash .\08_Software/mlx90614-webhid/mlx.html -Algorithm SHA256`. Hashes reflect **file content**, not an authenticated timestamp or a deployed-site match.
