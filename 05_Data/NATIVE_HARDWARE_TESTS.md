# Native MLX90614 hardware timing

On **2026-10-10**, the separate [Cython + HIDAPI demo](../08_Software/mlx90614-hidapi-demo/README.md) completed real MLX90614 object/ambient reads at 2, 10 and 20 requested Hz. The completed trials had **zero read errors and zero missed slots**. These results apply to the native demo; the edited browser transport was not tested against it.

## Conditions

- Windows x64, CPython 3.11.15, Cython 3.3.0, HIDAPI 0.15.0; existing compiled extension reused.
- Tested source commit: `f6c742c29b59c60126378fdf1e0d3b084e9098cf`.
- One MCP2221A bridge client; other readers stopped. Same wiring throughout the sequential tests.
- Verified **100 kHz** bus, divider **118**, sensor address **0x5A**, ambient register **0x06**, object register **0x07**; per-register budget **100 ms**.
- PEC and sensor error-bit validation enabled; a valid pair requires both temperatures to pass. No hidden sample retries, fixed inter-register pause or USB soft reset.
- Ordinary timing runs used no verbose protocol trace. Every valid pair required six HID exchanges.
- Exact sensor module, supply input and pull-up configuration remain unconfirmed. Existing wiring was used without electrical changes.

## Completed trials

| Requested rate | Elapsed seconds | Valid / attempted pairs | Read errors | Missed slots | Valid pairs/s | Acquisition p95 (ms) | Start lateness p95 (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2 Hz | 10.000120 | 20 / 20 | 0 | 0 | 2.0000 | 12.3997 | 0.6964 |
| 10 Hz | 30.000092 | 300 / 300 | 0 | 0 | 10.0000 | 12.2849 | 0.6155 |
| 20 Hz | 30.000521 | 600 / 600 | 0 | 0 | 19.9997 | 12.2658 | 0.7282 |

At 20 Hz, median acquisition took **11.7747 ms**, maximum **13.0352 ms**. The median valid-pair completion interval was **50.0008 ms**, p95 **50.4620 ms**, maximum **52.0788 ms**. Maximum start lateness was **2.3384 ms**. This is measured host scheduling variation on this setup, not a hard real-time guarantee.

## Additional runs and interruption accounting

| Requested rate | Elapsed seconds | Valid / attempted pairs | Read errors | Interrupted pairs | Missed slots | Valid pairs/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2 Hz | 10.000262 | 20 / 20 | 0 | 0 | 0 | 1.9999 |
| 20 Hz, stopped with Ctrl+C | 23.712656 | 474 / 475 | 0 | 1 | 0 | 19.9893 |

The stopped run's last CSV row has `status=interrupted`, `error_code=INTERRUPTED` and blank temperatures. Its earlier rows contain 474 valid pairs and no `error` rows. The original summary reported `failed_pairs=1` because it calculated attempts minus successes; this counted the interrupted acquisition as a failure despite `errors={}`.

Python reporting now distinguishes `failed_pairs` from `interrupted_pairs`. A read error followed by Ctrl+C during cancellation remains a failed pair; a pair stopped during acquisition is interrupted. Two fake-clock regression tests cover these cases. Existing CSV and summary files are preserved without rewriting; the compiled transport needs no rebuild for this reporting change.

## Startup observation

Before the completed trials, startup stopped before any sensor read. The bridge reported **SCL=0, SDA=1, pending=0, divider=118**:

```text
10 00 00 00 00 00 00 00 45 01 00 01 00 01 76 00 b4 00 08 28 00 60 00 01 00 00
```

With exclusive access confirmed, one explicit **I2C cancellation** was sent as `10 00 10 00 00 00 00 00` (remaining report bytes zero). A subsequent status read reported **SCL=1, SDA=1, pending=0, divider=118**:

```text
10 00 00 00 00 00 00 00 00 01 00 01 00 01 76 00 b4 00 10 28 00 60 01 01 00 00
```

The following trials succeeded. This establishes recovery for the observed state, without USB soft reset. It does not identify why SCL was low, prove repeated cold-start reliability, or resolve the historical browser speed-set `0x21` failure. The demo still stops on a busy/low-line startup rather than cancelling automatically.

## Evidence and limits

[Machine-readable evidence](NATIVE_HARDWARE_RESULTS.json) retains the original summaries, independently counted CSV statuses, source filenames and SHA-256 hashes. Raw CSVs and matching summaries remain local under `08_Software/mlx90614-hidapi-demo/output/` and are excluded from Git. Public evidence omits device serial numbers, HID paths and private filesystem paths.

**20 successful read pairs/s does not establish 20 independent sensor conversions/s.** The completed 20 Hz trial repeated the preceding raw object/ambient pair 399 times; the stopped run repeated it 280 times. A steady temperature and rereading stored sensor data can both produce identical words. Host monotonic acquisition timestamps are not sensor conversion timestamps, and the two registers are read sequentially.

These are 10–30-second tests, without a temperature reference, conversion-timestamp measurement, scope capture or matched browser benchmark. Long-run error rate, restart reliability, calibrated accuracy and a Cython-versus-Python performance advantage remain unmeasured. A 12 ms median acquisition is not a verified maximum polling rate; the OS, USB, bridge and sensor impose additional limits.

## Repeat the trials

Use the existing environment; no rebuild is needed unless native source/build inputs change. From **PowerShell at the repository root**, with the bridge connected and all browser sensor tabs/other readers stopped:

1. Run the low-rate check:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\08_Software\mlx90614-hidapi-demo\Run-Demo.ps1 -Hz 2 -Seconds 10
   ```

   Expect `100 kHz confirmed`, 20 valid pairs, zero failed/interrupted pairs and zero missed slots. Stop on setup/read errors and follow the [diagnostic and recovery steps](../08_Software/mlx90614-hidapi-demo/README.md#reuse-diagnostics-and-recovery).
2. Once it passes, run these commands sequentially in the same terminal with unchanged wiring:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\08_Software\mlx90614-hidapi-demo\Run-Demo.ps1 -Hz 10 -Seconds 30
   powershell -NoProfile -ExecutionPolicy Bypass -File .\08_Software\mlx90614-hidapi-demo\Run-Demo.ps1 -Hz 20 -Seconds 30
   ```

   Compare valid throughput, errors, missed slots and timing percentiles. Targets are 300 and 600 valid pairs; retain the generated evidence for any failure. Ctrl+C saves the interrupted run; it does not complete the requested duration. These repeats collect new evidence, not a required setup step.
