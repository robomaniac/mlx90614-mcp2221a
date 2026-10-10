# Validation record

Date: **2026-10-09**. This record separates completed software/publication checks from sensor tests requiring hardware.

| Check | Result and evidence |
| --- | --- |
| Original handoff | 42 original files backed up with matching SHA-256; all 40 original manifest entries matched before edits |
| Historical snapshots | All seven relocated HTML files retained byte for byte; revision 03 hash `463e33449d486cde680637a82cac7b535fd9ccadccbbca20f82e700ad1e1728e` |
| Working site identity | HTTP 200 fetched from user-supplied `https://jeromedemers.com/mlx.html`; 68,661 bytes, SHA-256 `2b252a1eb651d16f144040758d6844ecb7548aabc9196ea3ce6319c24d6c2787`, equal to original source and revision 07 |
| Active and baseline syntax | PASS: one embedded JavaScript block and one embedded CSS block; no external source imports |
| Simulated reset prevention | PASS: `SOFT_RESET_DISABLED` thrown before any HID send |
| Simulated read evidence | PASS: recovered retry retains its failure; all exhausted attempts remain logged; sensor error flags and bad PEC are rejected |
| Simulated pair accounting | PASS: a partial pair is not plotted; successful and attempted pair counts differ correctly |
| Simulated failure status | PASS: failed poll logged, counted and shown as waiting for a valid sample; no premature recovery claim |
| Simulated bounded log | PASS: latest 700 lines retained and rendered with real newline characters |
| Chrome local smoke | PASS: edited HTML initializes over temporary loopback HTTP; browser exit 0, expected title/Connect/five rates, secure context and `navigator.hid=true`. No Connect click/USB operation occurred. Temporary server/profile cleaned up. |
| Project links/configuration | Final Markdown, task JSON, workflow packaging and current manifest checked before initial commit |
| Privacy review | Public candidates, selected logs, cropped image, original text and ZIP contents reviewed; no credential/private-key patterns or confidential content identified. Local backups/ZIPs/older apps/helper binaries excluded by ignore rules. |
| GitHub / Pages | Prepared; initial publication and delivery verification in progress |
| Hardware after edits | **Pending**. No physical bridge/sensor session performed; no measured rate, reconnect reliability or accuracy claim. |

The historical user's live-reading logs and current report that the original hosted site works are retained as user evidence. Neither proves the modified revision works with this hardware. The actual sensor breakout supply input and pull-ups remain unconfirmed.

Repeat software checks from **PowerShell at the repository root**:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\08_Software\mlx90614-webhid\tools\Check-Html.ps1 -Diagnostics
```

Expect all `PASS`; stop before device testing on any failure. See the [complete local and baseline procedure](../08_Software/mlx90614-webhid/README.md) and [hardware test plan](../00_Documentations/KNOWN_ISSUES_AND_TEST_PLAN.md). Privacy scans provide pattern-based evidence, not a guarantee that arbitrary future content is safe to publish. The current manifest hashes curated files and excludes itself and generated/local-only material.
