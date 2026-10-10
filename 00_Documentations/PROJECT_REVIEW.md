# Project review and migration decisions

Reviewed on **2026-10-09**. This is a personal hardware experiment migrated from a ChatGPT handoff into a conventional VS Code/GitHub project.

## Source and preserved evidence

- The original handoff contained **42 files**, including nine original ZIPs. All **40** original manifest entries matched their recorded byte size and SHA-256. The complete 42-file handoff was copied and hash-verified into the local-only `99_Archive/original-handoff/` before reorganization.
- All seven historical HTML snapshots were relocated with byte-for-byte verification and remain unchanged. Original ZIPs and older alternatives are retained locally and ignored by Git.
- The user reports `https://jeromedemers.com/mlx.html` works. The fetched HTTP 200 response matched original `mlx.html` and historical revision 07 exactly: **68,661 bytes**, SHA-256 `2b252a1eb651d16f144040758d6844ecb7548aabc9196ea3ce6319c24d6c2787`. This resolves the former uncertainty about the fetched deployed revision. It does not establish long-run reliability or accuracy.
- Revision 03 remains an earlier comparison candidate, **50,997 bytes**, SHA-256 `463e33449d486cde680637a82cac7b535fd9ccadccbbca20f82e700ad1e1728e`.

## Structure and skills

The numbered categories follow the user's existing Nextcloud project convention: documentation in `00_Documentations`, media in `04_Media`, evidence in `05_Data`, host software in `08_Software`, and provenance in `99_Archive`. Empty electrical/firmware/mechanical/admin categories were not added. The root project number/name is retained.

Existing local folder-creation and GitHub workflow guidance was used; no skills were installed, replaced or created. The Product Design `audit` skill concerns screenshot-backed UX/design/accessibility review. It does not define a repository folder convention. The relevant repository guidance was found among the user's existing Cursor/shared skills and archived GitHub workflow references. Private documentation-service defaults were excluded from this public project.

## Active source changes

The single-file interface and I2C transaction sequence are preserved. Changes are limited to the app title, USB reset prevention and diagnostic behavior:

1. `softResetAndReconnectDevice()` throws `SOFT_RESET_DISABLED` before sending any USB command. Recovery call sites report that reset is disabled. Historical revision 07 retains its original reset code unchanged.
2. Every failed register read attempt is logged, including failures that a retry recovers. Failed cancellation attempts are retained too. Successful periodic read logs remain throttled.
3. Attempted object/ambient pairs and successful validated pairs are shown separately; a partial pair is not plotted. The displayed failed-poll count and recovered-register count provide additional context.
4. A transient failed poll displays **Retrying**, waiting for the next valid pair. It no longer claims recovery immediately after a failure.
5. Development checks and simulated tests cover these changes without contacting USB hardware. They reuse Node or VS Code's runtime. Pages deploys the same HTML bytes as `index.html`; no browser dependency was introduced.

## Findings and limits

- Startup `0x21`, busy `0x94`, sensor error flags and HID timeout causes remain unproven. Reorganization and diagnostics do not fix or validate their hardware causes.
- The original code's startup recovery heuristics remain experimental. A divider of zero is a diagnostic value, not proof of power-on state. The reset path now stops with an explicit failure instead of resetting a shared bridge.
- Disconnect does not fully await an in-flight sample before closing the HID handle. That may produce a final failure log or race during quick reconnects. It is a review finding, not a proven cause of the reported startup issue; no transport refactor was introduced during migration.
- Closing the bridge's other clients and using identical wiring/rates are essential controls for A/B hardware tests. No MCP2221A hardware session was available during this review.
- The sensor marking identifies MLX90614BAA; actual breakout model, regulator, VIN and fitted pull-ups remain unconfirmed. The root BOM separates chip facts from board assumptions and links primary manufacturer sources.
- Privacy review covers public candidates and the original text/archive contents. No credential/private-key patterns or confidential content were found. A scan cannot guarantee absence of every possible secret; future logs and staged changes need review.

See [completed validation](../05_Data/VALIDATION.md), [exact operation and A/B commands](../08_Software/mlx90614-webhid/README.md), and [remaining hardware tests](KNOWN_ISSUES_AND_TEST_PLAN.md).
