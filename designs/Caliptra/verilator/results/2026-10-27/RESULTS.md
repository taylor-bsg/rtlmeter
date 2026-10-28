# Caliptra default: measured thread-unit placement

One worker is fastest on all four measured workloads. Automatic grouping is the
fastest eight-worker configuration; the explicit map remains an experimental
placement baseline.

| Workload | 1 worker (s) | Default 8 (s) | Same units, auto 8 (s) | Mapped 8 (s) | Speedup vs. 1 worker |
|---|---:|---:|---:|---:|---:|
| hmac | 31.362 | 38.114 | 34.916 | 35.970 | 0.87x |
| mlkem | 126.910 | 153.619 | 140.207 | 144.799 | 0.88x |
| sha3 | 39.642 | 48.777 | 44.150 | 45.339 | 0.87x |
| trng | 51.173 | 62.079 | 56.836 | 58.393 | 0.88x |

Times are medians of **two** isolated timing rounds per workload/configuration.
The final column compares the mapped eight-worker model with one worker.
Each workload retains its RTLmeter setting of `+iterations=1`. Round two reverses
both workload and configuration order. Timings include initialization,
simulation, and cleanup; profiling runs are excluded from this table.
The serial model has no grouping directives. The default eight-worker control
has no grouping directives. Automatic grouping and the mapped model select
the same 24 instances from 22 module types.

| Workload | Reduction vs. default 8 | Reduction vs. automatic grouping | Change vs. serial |
|---|---:|---:|---:|
| hmac | 5.6% | -3.0% | +14.7% |
| mlkem | 5.7% | -3.3% | +14.1% |
| sha3 | 7.0% | -2.7% | +14.4% |
| trng | 5.9% | -2.7% | +14.1% |

Positive reductions mean less elapsed time; a positive change versus serial means
a slowdown. Individual samples and ranges are in [summary.json](summary.json)
and [timings.csv](timings.csv). Two repetitions establish a short comparison,
not a claim of precise sub-percent differences.

## Placement and profiling

The initial map used the existing [0.25% hierarchy inventory](../../analysis/README.md),
disjoint NBA instruction-cost estimates, and shared-variable connectivity.
ABR's large arithmetic children are separate units. The initial static map
was slower than the serial model on all four correctness runs; it is retained
as [initial-static.vlt](initial-static.vlt).

Call-stack profiles distinguish serial ACT evaluation from NBA work, even when
both phases reuse a generated helper. They also attribute library copies through
their observed callers. The static map's profiles show the main limitation:

| Workload | Caller cycles in serial ACT | Call-stack samples |
|---|---:|---:|
| hmac | 82.5% | 57,384 |
| mlkem | 83.3% | 230,129 |
| sha3 | 83.6% | 72,653 |
| trng | 82.6% | 93,079 |

These are fractions of sampled caller **cycles**, not exact wall-clock phase
timings or a serial fraction of the separate one-worker build. Most pool-worker
cycles were waiting for dispatch or dependencies. The first flat HMAC sample
gave different unit proportions from the call-stack profile; the solver uses
the four call-stack profiles, which consistently identify the AXI testbench
memory, key vault, and ABR memory among the largest NBA units. Flat profiles are
preserved as diagnostics, not used as complete work estimates.

Within the sampled serial ACT work, testbench services account for about 26.5%,
the masked GS butterflies for 17–18%, and masked PWM units for about 12%.
Those modules' ACT portions still execute on the caller even when their NBA
pieces are assigned elsewhere. The [serial ACT breakdown](serial-act-breakdown.json)
records module-type shares and the hottest generated functions.

The revised map puts AXI memory on the caller and keeps ABR memory and the key
vault on the caller's chiplet. Under those locality constraints, CP-SAT first
minimizes the largest normalized worker load across the four workloads, then
allows 3% slack while reducing chiplet imbalance and structural cuts. The solved
NBA chiplet totals differ by at most 2.9%. This is a model of sampled NBA work;
it covers attributed selected-unit work and excludes residual automatically
scheduled top-level tasks and ambiguous samples. It does not balance the serial
ACT phase or prove an optimal runtime placement.
The 59 shared-variable hyperedges count distinct variables, without width or
activity weighting, so their cut objective is a connectivity proxy, not bandwidth.

| Worker | Assigned units |
|---:|---|
| 0 | AXI testbench memory, device wrapper remainder, RTLmeter utility |
| 1 | ABR testbench memory |
| 2 | Key vault, DOE controller |
| 3 | PCR vault, SoC interface, testbench services remainder |
| 4 | Both masked PWM units |
| 5 | VeeR CPU, CSRNG, data vault, entropy source |
| 6 | AES, ECC, HMAC, SHA3, SHA256 |
| 7 | ABR remainder, both masked GS butterflies, SHA512 |

Worker `i` is pinned to physical CPU `i`. CPUs 0–3 and 4–7 are two four-core
chiplets on socket 0 of kk10 (dual AMD EPYC 9374F). Memory is bound to NUMA node 0.
The profile itself does not set affinity. The residual top-level testbench tasks
remain automatically scheduled; selected child units override their parents.
All 24 selected instances appear in the index listing. Every unit with emitted
NBA work has its owner verified in generated C++ dispatch, including descendant
interface calls; the RTLmeter utility has no emitted NBA task.
The portable profile produces byte-identical code to
the tested automatic control across all 293 generated C++/header/make files.

## Correctness and the startup-banner gate

The initial exact-output gate stopped on automatic grouping. Investigation found
only a permutation of two complete time-zero banners: memory preloading and
strap initialization print from separate `initial` blocks. No timing or profiling
phase was started by that failed gate. Its raw stop record is retained.

The reviewed comparator allows exactly those two unchanged banner blocks to
exchange order. Every other output byte, the clock count, and the RTLmeter post-hook
remain checked. Negative controls reject changed banner content and changed
subsequent output. Firmware console logs match the immutable package-60 evidence;
the emitted memory snapshots match the freshly checked serial run. These snapshots
are the testbench's emitted ranges, not a full-state equivalence proof.

The initial four configurations passed all 16 workload checks before profiling.
The revised mapping passed all four workload checks before timing. Every timed run
also passed the output, console, snapshot, affinity, and executable-page checks.
Each execution used a unique copied binary with resident executable pages on node 0.
Raw output hashes are retained even when the permitted banner ordering differs.

## Sources and tools

- RTLmeter input tree: `ce4d260ba7c61a92d194b30dbb4676258c700ed6`; Caliptra RTL,
  descriptor, utility, firmware and hook hashes are recorded and verified against
  the staged compilation/execution inputs. No RTL or firmware changes.
- Verilator: [`2487df5b4b8665f0caf8aed7ea174d13c037bf19`](https://github.com/taylor-bsg/verilator/tree/2487df5b4b8665f0caf8aed7ea174d13c037bf19),
  `codex/threads-unit-runtime-integration`. This combines worker assignment
  `8c052270`, final wide-zero-reset PR #8916 and final bit-copy PR #8933, with the
  documented test-comment compatibility adjustment. Scheduler, cost estimator,
  merging heuristics and runtime synchronization are unchanged between controls.
- Verilator and every fresh model use Clang 21.1.8. C++ compilation and linking
  explicitly use `/usr/bin/clang++-21`, with C++20 and the default hot-code `-Os`.
  Clang's default GCC 15 standard-library toolchain is permitted; no GCC compiler
  or GCC 11 C++ toolchain is selected. No PGO, LTO or custom unrolling flags.
- Flat diagnostics use `cycles:u` at 999 Hz; call stacks use `cycles:u` at 199 Hz
  with DWARF unwinding. Both attach shortly after launch and are excluded from
  the final timing samples. Statistical sampling and instruction skid apply.

## Files

- [Portable profile](../../threads-unit.vlt), [kk10 profile](../../threads-unit-kk10.vlt),
  and [index-to-instance listing](threads-unit-indices.txt).
- [Native audit](native-audit.json), [dispatch audit](runtime-assignment-audit.json),
  [runtime placement model](runtime-placement.json), and [call-stack analysis](static-callgraph-profile.json).
- [Interactive runtime profile](runtime-profile.html): download and open locally to
  compare worker work/wait distributions and attributed units across the four workloads.
- [Raw native evidence](native-evidence.tar.gz) and [reproduction scripts/provenance](reproduction.tar.gz).
  The archive retains code hashes, build/run logs, decoded perf samples, and
  correctness/affinity records. Native binaries and binary perf recordings remain on kk10.
  Archive manifests verify member hashes. Repeated disassemblies have only their
  objdump pathname header normalized and are stored as hard links; original header
  paths and hashes are recorded so the original derived text can be reconstructed.

Only Caliptra `default` with eight workers and the four listed performance workloads
is validated here. Other worker counts and the separate `hello` test remain untested
by this placement experiment. NVDLA placement is still pending.
