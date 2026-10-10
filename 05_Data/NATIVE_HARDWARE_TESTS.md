# Native MLX90614 hardware timing

On **2026-10-10**, the separate [Cython + HIDAPI demo](../08_Software/mlx90614-hidapi-demo/README.md) completed real MLX90614 object/ambient reads, increased the request to **100 Hz to find the paced timing failure**, then removed the scheduled wait in a separate unpaced mode. **60 Hz completed 3,600/3,600 pairs over one minute with zero missed paced deadlines. Unpaced acquisition later completed 4,993/4,993 over one minute at 83.20 pairs/s**, with an earlier failed unpaced trial retained below. These results apply to the native demo; the edited browser transport was not tested against it.

## Conditions

- Windows x64, CPython 3.11.15, Cython 3.3.0, HIDAPI 0.15.0; existing compiled extension reused.
- Initial trial source commit: `f6c742c29b59c60126378fdf1e0d3b084e9098cf`. Paced sweep source is preserved in commit `eae2c0e5236850b841994489298cb138290b9dfd` with fingerprints in [sweep evidence](NATIVE_RATE_SWEEP.json). Later unpaced source fingerprints are recorded separately; the native transport remains unchanged.
- One MCP2221A bridge client; other readers stopped. Same wiring throughout the sequential tests.
- Verified **100 kHz** bus, divider **118**, sensor address **0x5A**, ambient register **0x06**, object register **0x07**; per-register budget **100 ms**.
- PEC and sensor error-bit validation enabled; a valid pair requires both temperatures to pass. No hidden sample retries, fixed inter-register pause or USB soft reset.
- Ordinary timing runs used no verbose protocol trace. Every valid pair required six HID exchanges.
- Exact sensor module, supply input and pull-up configuration remain unconfirmed. Existing wiring was used without electrical changes.

## Initial completed trials

| Requested rate | Elapsed seconds | Valid / attempted pairs | Read errors | Missed slots | Valid pairs/s | Acquisition p95 (ms) | Start lateness p95 (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2 Hz | 10.000120 | 20 / 20 | 0 | 0 | 2.0000 | 12.3997 | 0.6964 |
| 10 Hz | 30.000092 | 300 / 300 | 0 | 0 | 10.0000 | 12.2849 | 0.6155 |
| 20 Hz | 30.000521 | 600 / 600 | 0 | 0 | 19.9997 | 12.2658 | 0.7282 |

At 20 Hz, median acquisition took **11.7747 ms**, maximum **13.0352 ms**. The median valid-pair completion interval was **50.0008 ms**, p95 **50.4620 ms**, maximum **52.0788 ms**. Maximum start lateness was **2.3384 ms**. This is measured host scheduling variation on this setup, not a hard real-time guarantee.

## Rate sweep and timing failure

A rate passes this experiment's strict criterion only if the requested window completes with **zero failed/interrupted pairs and zero missed nominal slots**. Read-error count alone does not establish that a requested rate was maintained.

| Requested rate | Window (s) | Valid / nominal pairs | Missed slots | Valid pairs/s | Acquisition p95 (ms) | Start lateness p95 (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 30 Hz | 30 | 900 / 900 | 0* | 29.9997 | 12.3707 | 0.6621 |
| 40 Hz | 30 | 1,200 / 1,200 | 0 | 39.9996 | 12.3428 | 0.7500 |
| 50 Hz | 30 | 1,500 / 1,500 | 0 | 49.9995 | 12.2834 | 0.6827 |
| 60 Hz | 30 | 1,800 / 1,800 | 0 | 59.9978 | 12.3711 | 0.7455 |
| 70 Hz | 30 | 2,100 / 2,100 | 0 | 69.9990 | 12.2726 | 0.6294 |
| 80 Hz | 30 | 2,061 / 2,400 | 339 | 68.6992 | 12.2664 | 0.6507 |
| 100 Hz | 30 | 1,500 / 3,000 | 1,500 | 49.9993 | 12.1761 | 0.6619 |
| 75 Hz, boundary check | 30 | 2,244 / 2,250 | 6 | 74.7995 | 12.2974 | 0.6892 |
| 72.5 Hz, boundary check | 30 | 2,174 / 2,175 | 1 | 72.4649 | 12.2800 | 0.6638 |
| 70 Hz, longer repeat | 60 | 4,196 / 4,200 | 4 | 69.9332 | 12.3062 | 0.6409 |
| 65 Hz, longer check | 60 | 3,898 / 3,900 | 2 | 64.9665 | 12.3054 | 0.6653 |
| 60 Hz, longer check | 60 | 3,600 / 3,600 | 0 | 59.9996 | 12.2771 | 0.5911 |

**Every attempted pair was valid in these runs:** zero PEC, sensor-flag, I2C-command or HID transport errors; no interrupted pairs or USB soft resets. All valid pairs used six HID exchanges. Misses were verified against CSV slot numbers, rather than inferred from temperature values.

The first timing failure during the ascending sweep was at **80 Hz**, with **14.125%** of nominal slots skipped. At 100 Hz the period is 10 ms while a pair takes approximately 12 ms. The scheduler then skips the next deadline and waits for a later slot; this produced even-numbered slots and about 50 valid pairs/s. Increasing the request past the limit can therefore reduce throughput in this scheduler.

The shorter 70 Hz trial was clean, but its longer repeat missed four slots. One of those acquisitions finished **1.868 ms before** the next deadline, showing that work/scheduling after acquisition also consumed the remaining margin. Other misses exceeded the deadline during acquisition because of start lateness or longer reads. The 65 Hz run also missed twice. These observations locate a practical boundary for the whole demo, including CSV/output and Windows scheduling; they do not isolate a USB-only or sensor-only maximum.

**60 Hz is the highest rate demonstrated without misses in a one-minute trial.** Its median acquisition was 11.8320 ms, maximum 13.8865 ms; median completion interval 16.9596 ms, p95 17.0784 ms, maximum 20.8243 ms. A zero-miss trial still has interval variation. Desktop load was not controlled, and this is not an all-duration timing guarantee. The fastest observed valid throughput was 74.7995 pairs/s at requested 75 Hz, with six skipped slots.

\* The initial 30 Hz summary reported one missed slot despite all 900 nominal slots being present. Rounding the 33,333,333.333… ns period to an integer caused the old window formula to create a 901st deadline just before the end. Window counting now uses the nominal duration multiplied by rate, independently of the rounded period. A fake-clock regression covers 30, 70, 3.3 and 2.5 Hz. Original CSV/summary files are preserved; the public evidence explicitly retains the original count and its correction.

## Unpaced acquisition: no target period

The later Python/launcher change adds `-Unpaced` / `--unpaced`. It starts the next pair after the previous attempt and host output, without sleeping for a target-period deadline. The ordinary `-Hz` mode retains its absolute deadlines and skip behavior. Neither mode overlaps HID/I2C transactions or changes the 100 kHz bus.

| Mode / trial | Requested window (s) | Actual elapsed (s) | Valid / attempted pairs | Failed pairs | Valid pairs/s | Missed slots |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Unpaced, first trial, stopped on error | 30 | 14.906100 | 1,240 / 1,241 | 1 | 83.1874 | N/A |
| Paced 100 Hz control | 30 | 30.000179 | 1,500 / 1,500 | 0 | 49.9997 | 1,500 |
| Unpaced, repeat | 30 | 30.001258 | 2,482 / 2,482 | 0 | 82.7299 | N/A |
| Unpaced, longer repeat | 60 | 60.010436 | 4,993 / 4,993 | 0 | 83.2022 | N/A |

The first unpaced trial failed at ambient register `0x06` with:

```text
I2C_DATA: reg=0x06 reply=40 41 25 7f 00 00 00 00
RECOVERY_CANCEL: Cancellation failed: 10 00 00 00 00 00 00 00 00 03 00 00 00 00 76 00 b5 00 10 28 40 60 01 01 00 00
```

The failed row and both errors are retained. The demo stopped after the cancellation response failed validation. Without USB reset, the subsequent paced control and two unpaced repeats completed. This does not prove the intermittent failure is fixed or establish its cause; cancellation response interpretation and repeatability require a separate discriminating test. A regression test verifies that failed recovery stops unpaced acquisition and retains the original read error.

The one-minute unpaced run had **12.0000 ms median completion interval**, p95 **12.2891 ms**, maximum **14.0405 ms**. Acquisition median was **11.9625 ms**, p95 **12.2295 ms**, maximum **13.9240 ms**. Median host gap from one acquisition finishing to the next starting was **0.0377 ms**, compared with **8.1601 ms** in the paced 100 Hz control. Removing the scheduled wait therefore improves throughput without reducing the measured USB/I2C acquisition time to below 10 ms.

There are no scheduled deadlines in unpaced mode. `requested_hz`, `missed_slots` and lateness percentiles are `null`, and CSV scheduled-time/lateness cells are blank. They must not be reported as zero misses or exact timing. An attempt started before the window ends completes before exit, so actual elapsed time may be slightly longer than the request. CSV/output and host scheduling still add overhead. All successful pairs used six HID exchanges.

The one-minute unpaced run repeated the previous raw pair 4,459 times. Faster reads do not establish faster independent sensor conversions. The failed first run and shorter repeat's 31.9386 ms maximum interval also prevent a general reliability or constant-interval claim. [Unpaced/control evidence](NATIVE_UNPACED_RESULTS.json) contains every original summary, CSV hashes, errors, source fingerprints and calculated host-gap percentiles.

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

[Initial machine-readable evidence](NATIVE_HARDWARE_RESULTS.json), [paced rate-sweep evidence](NATIVE_RATE_SWEEP.json) and [unpaced/control evidence](NATIVE_UNPACED_RESULTS.json) retain original summaries, independently counted CSV statuses/slots, source filenames and SHA-256 hashes. Raw CSVs and matching summaries remain local under `08_Software/mlx90614-hidapi-demo/output/` and are excluded from Git. Public evidence omits device serial numbers, HID paths and private filesystem paths.

**20 successful read pairs/s does not establish 20 independent sensor conversions/s.** The completed 20 Hz trial repeated the preceding raw object/ambient pair 399 times; the stopped run repeated it 280 times. A steady temperature and rereading stored sensor data can both produce identical words. Host monotonic acquisition timestamps are not sensor conversion timestamps, and the two registers are read sequentially.

These are 10–60-second tests, without a temperature reference, conversion-timestamp measurement, scope capture or matched browser benchmark. Longer-run error rate, restart reliability, calibrated accuracy and a Cython-versus-Python performance advantage remain unmeasured. A 12 ms median acquisition is not a verified maximum polling rate; the OS, USB, bridge, sensor and host output impose additional limits. The one-minute 60 Hz trial repeated the previous raw pair 3,234 times out of 3,600 valid pairs; higher read rates do not establish faster independent conversion rates.

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

## Repeat the rate sweep

Optional: the recorded sweep above is already completed. First finish the low-rate checks above. Continue in the **same PowerShell terminal at the repository root**, with unchanged wiring and exclusive bridge access. The environment and native extension can be reused.

1. Execute the increasing-rate loop from the [timing-limit guide](../08_Software/mlx90614-hidapi-demo/README.md#test-the-timing-limit). It runs 30/40/50/60/70/80/100 Hz sequentially for 30 seconds each, about four minutes including startup. Any protocol/setup failure stops the loop; timing misses remain visible even with exit code `0`.
2. Reproduce the boundary checks one command at a time:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\08_Software\mlx90614-hidapi-demo\Run-Demo.ps1 -Hz 75 -Seconds 30
   powershell -NoProfile -ExecutionPolicy Bypass -File .\08_Software\mlx90614-hidapi-demo\Run-Demo.ps1 -Hz 72.5 -Seconds 30
   powershell -NoProfile -ExecutionPolicy Bypass -File .\08_Software\mlx90614-hidapi-demo\Run-Demo.ps1 -Hz 70 -Seconds 60
   powershell -NoProfile -ExecutionPolicy Bypass -File .\08_Software\mlx90614-hidapi-demo\Run-Demo.ps1 -Hz 65 -Seconds 60
   powershell -NoProfile -ExecutionPolicy Bypass -File .\08_Software\mlx90614-hidapi-demo\Run-Demo.ps1 -Hz 60 -Seconds 60
   ```

   Expect new `HARDWARE` summaries and CSVs. A pass requires the target nominal count with zero failed/interrupted pairs and zero missed slots. Compare the complete CSV and p95/max values when a rate passes a short trial but misses during the longer repeat. Stop and retain evidence on protocol/setup failure; never hide it through retries or reset.
