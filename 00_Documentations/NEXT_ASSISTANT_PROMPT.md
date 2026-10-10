# Prompt to paste into your VS Code coding assistant

> **Migration update — 2026-10-09:** The fetched `https://jeromedemers.com/mlx.html` exactly matched historical revision 07, and the user reports it works. Active `08_Software/mlx90614-webhid/mlx.html` now blocks automatic USB reset and retains read-error/attempt evidence. Hardware validation of these edits is pending. See [current review](PROJECT_REVIEW.md) and [validation](../05_Data/VALIDATION.md). Earlier sections describe the original development history.

Copy the following message as your first request in the extracted project folder:

> Read `AGENTS.md`, `README.md`, `00_Documentations/PROJECT_HISTORY.md`, `00_Documentations/HARDWARE_AND_PROTOCOL.md`, `00_Documentations/KNOWN_ISSUES_AND_TEST_PLAN.md`, `05_Data/SELECTED_LOGS.md`, and `00_Documentations/VERSION_INDEX.md`. This project is a self-contained Chrome WebHID single-file app (`08_Software/mlx90614-webhid/mlx.html`) that reads an MLX90614 via an MCP2221A. The page successfully produced real temperature samples, including at 10 Hz with intermittent errors, but later revisions introduced or encountered a startup issue where the bridge rejects setting I2C speed with `status byte3=0x21`, and an attempted `0x94` write returned busy. The fetched hosted site matched revision 07 and is user-reported working. The active `08_Software/mlx90614-webhid/mlx.html` disables automatic USB reset, retains failed read attempts, and distinguishes valid pairs from attempts; edited hardware behavior is unverified; `99_Archive/webhid-history/03-dropdown-last-reading-baseline.html` is the best comparison candidate. **Do not rewrite the app immediately.** First examine the diffs and analyze the most likely *code-level* causes, clearly separate observations from hypotheses, identify the single best A/B hardware test, and propose only the smallest reversible change. Preserve the current one-file format, modern UI, sample-rate dropdown, chart hover, log formatting and device permission behavior. Be explicit about what can and cannot be tested without the USB hardware.

Suggested follow-up after that initial review:

> I will connect the hardware now. Tell me exactly which version to open, how to ensure no other browser tab/application is using the MCP2221A, which sample rate to select, which log lines to save, and the pass/fail criteria. Do not make new speculative recovery changes until the A/B result is known.

For work on **other sensors** later:

> Keep the MCP2221A WebHID and modern graph UI. Create a sensor-specific driver within the same single HTML file. Do not apply the MLX90614 raw conversion to another device. Use the new sensor's datasheet to define its protocol and timing, and explain any hardware/voltage differences before testing.
