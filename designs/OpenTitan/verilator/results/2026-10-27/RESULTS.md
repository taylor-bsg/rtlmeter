# OpenTitan default: saved placement with the final loop optimization

The saved 54-unit kk10 placement improves all four measured performance workloads.
The portable profile now selects the same 54 units with automatic assignment.
All configurations below use the same final compiler integration, so this
comparison measures grouping/placement, not the isolated effect of the loop optimization.

| Workload | 1 worker (s) | Earlier auto, 25 units (s) | Auto, 54 units (s) | Mapped 8 workers (s) | Speedup vs. 1 worker |
|---|---:|---:|---:|---:|---:|
| aes | 39.714 | 26.573 | 24.917 | 17.453 | 2.28x |
| cmark | 52.245 | 33.817 | 31.979 | 22.285 | 2.34x |
| rsa | 42.412 | 27.710 | 26.226 | 18.258 | 2.32x |
| sha | 40.059 | 27.302 | 25.953 | 17.881 | 2.24x |

Times are medians of three isolated runs per configuration/workload, measured
with the native process preload timer on kk10 on 2026-10-27, including model
initialization, simulation, and cleanup. The earlier automatic
control uses the [previous 25-unit grouping](original-auto.vlt). The other
automatic control has exactly the same unit inventory as the mapped profile.
The one-worker model is a separate serial build without grouping directives.

| Workload | Runtime reduction vs. earlier auto | Runtime reduction vs. same-unit auto | Mapped range (s) | Cycles |
|---|---:|---:|---:|---:|
| aes | 34.3% | 30.0% | 17.424–17.472 | 665,044 |
| cmark | 34.1% | 30.3% | 22.066–22.323 | 865,439 |
| rsa | 34.1% | 30.4% | 18.049–18.410 | 700,037 |
| sha | 34.5% | 31.1% | 17.742–17.981 | 679,627 |

## Source and execution setup

- RTLMeter inputs: `39a9a85c5b32da0ec8b0184fd57c9a9fb2b919ee`, unmodified RTL and firmware.
- Verilator: [`2487df5b4b8665f0caf8aed7ea174d13c037bf19`](https://github.com/taylor-bsg/verilator/tree/2487df5b4b8665f0caf8aed7ea174d13c037bf19),
  branch `codex/threads-unit-runtime-integration`.
- That branch combines worker assignment `8c052270`, final wide-zero-reset
  commit `546644f5` (PR #8916), and final bit-copy commit `ddbd470c` (PR #8933).
  The only extra adaptation removes two warning-control comments unsupported by
  the older base from a test. Scheduler, cost, and merging heuristics are unchanged.
- Both Verilator and every fresh model use Clang 21.1.8. Model compile/link drivers
  are explicitly `/usr/bin/clang++-21`; default hot-code optimization is `-Os`,
  with C++20. No PGO, LTO, or custom unrolling flags are added.
- Logical worker `i` is pinned to physical CPU `i`. CPUs 0–3 and 4–7 are two
  chiplets on socket 0. The caller/scheduler is worker 0. The serial reference
  also uses CPU 0. All runs bind memory to node 0.
- AES/RSA/SHA use their descriptor's three workload iterations; CoreMark uses
  one. Each timed process starts afresh. The `hello` sanity workload is not part
  of this four-workload timing matrix.
- Every run uses its own copied executable inode; live checks verify singleton
  per-thread CPU affinity and resident executable pages on node 0.
- A shared benchmark lock covers all builds and executions. All builds finish
  before correctness screens. All 16 screens finish before any timed run.
  Round 2 reverses case/configuration order; there are 48 timed runs total.

## Correctness and assignment verification

All **16 correctness screens and 48 timed runs passed** the original post-hook,
matched the immutable reference stdout byte for byte, and had identical cycle
counts for each workload. Reference outputs came from the already validated
package-60 runs; this comparison does not regenerate expected output from the candidate.
The descriptor, HDL/C++, firmware, and hook hashes match the pinned source.

All **54 selected units** and their emitted descendant calls were audited through
the generated worker dispatch. Child units override an enclosing unit; other
logic stays with its nearest selected ancestor. The mapped NBA graph has
237 tasks and 748 edges. All four builds perform 151 bit-copy lowerings.
The integration compiler also passed 23 focused tests in release and 23 in debug.

The original AES placement search selected this map. This follow-up validates
the saved map with the final compiler changes and the original synchronization
and merging heuristics. Performance on other hardware and worker counts remains
unmeasured.

## Reproduction and evidence

Use the [portable profile](../../threads-unit.vlt) or the self-contained
[kk10 profile](../../threads-unit-kk10.vlt), one at a time. See the
[collection documentation](../../../../../docs/source/threads-unit.rst) for selection syntax.
After normal RTLMeter setup and building the pinned Verilator with
`CC=/usr/bin/clang-21 CXX=/usr/bin/clang++-21`, a compile/listing example from
the RTLMeter root is:

```sh
profile="$PWD/designs/OpenTitan/verilator/threads-unit-kk10.vlt"
MAKEFLAGS='CXX=/usr/bin/clang++-21 LINK=/usr/bin/clang++-21 CXXFLAGS=-std=gnu++20 OBJCACHE=' \
  ./rtlmeter run --cases 'OpenTitan:default:aes' \
  --compileArgs="--threads 8 --compiler clang --threads-unit-list '$profile'" \
  --nExecute 0 --workRoot work-opentitan-kk10
```

The VLT does not set affinity. For timing, use the recorded launcher and preload
shim in the native evidence with `HB_CPUS=0,1,2,3,4,5,6,7` and
`VERILATOR_NUMA_STRATEGY=none`. A process-wide CPU mask alone does not reproduce
the per-thread placement. The original launcher's paths are recorded verbatim
and must be relocated when reproducing on another checkout.

- [Raw timings](timings.csv) and [medians/ranges](opentitan-summary.json).
- [Generated module-index-to-worker listing](threads-unit-indices.txt).
- [Assignment audit](opentitan-assignment-audit.json), [workload/source audit](opentitan-workload-audit.json),
  and [independent native audit](opentitan-native-audit.json).
- [Compiler/source provenance](source-provenance.json) and [compiler binary hashes](binaries.json).
- [Native evidence](native-evidence.tar.gz): all build commands/logs, correctness and
  timing stdout, hooks, cycle files, affinity records, placement samples,
  binary hashes, reference outputs, controller, worker, and machine topology.
- [Compiler evidence](compiler-evidence.tar.gz): integration build/test logs,
  model-generation commands/hashes, and audit scripts. Test harness logs named
  `vlt_gcc.log` contain the actual Clang invocations; the filename is historical.
- Both archives contain SHA-256 manifests; [manifest.json](manifest.json) hashes
  every published result file. Generated binaries are not committed.
