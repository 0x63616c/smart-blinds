# Isolated KiCad 10 runner

`tools/kicad-run` runs KiCad and its Python bindings **inside Linux**, never the
installed macOS application. The host process only uses Python's standard library
and Docker. It does not disable macOS crash reporting or hide native failures.

The image uses the [KiCad team's stable Ubuntu PPA](https://www.kicad.org/download/linux-distros/),
as the repository CI does. The recipe pins the Ubuntu 24.04 ARM64 manifest and
KiCad package `10.0.7~ubuntu24.04.1`; it checks the
[PPA signing fingerprint](https://launchpad.net/~kicad/+archive/ubuntu/kicad-10.0-releases).
Other Ubuntu dependencies are recorded in the image's
`/usr/local/share/kicad-runner-packages.tsv`. They are not claimed to be snapshot-pinned.
The local `image.lock.json` binds each run to an immutable image ID. Rebuilding may
produce a different ID as Ubuntu dependencies change; review the new lock.

## Build and disk budget

From the repository root:

```sh
python3 tools/kicad-linux/build.py
```

This is explicit: the run wrapper never builds, pulls, upgrades or retries an image.
The build uses a small metadata stage to calculate the package download first and
stops above 2 GB. The measured initial plan is about 248 MB downloaded and 1.05 GB
additional installed space, plus the 28.94 MB compressed Ubuntu base and its metadata
stage. The full KiCad 3D libraries, symbols, footprints and documentation are omitted
unless they are required dependencies; project-local assets remain available.
Do not prune unrelated images, containers or volumes to make room.

## Use

```sh
tools/kicad-run -- python3 tools/kicad-linux/smoke.py
tools/kicad-run -- kicad-cli version
tools/kicad-run --timeout 600 -- python3 work/my-study/export.py
```

Inside the container the selected repository is `/work` and the working directory
is `/work`. Use repository-relative script and file paths. `python3` resolves to the
Ubuntu `/usr/bin/python3` with `pcbnew`, wxPython, Shapely and PyYAML. Xvfb provides a
private X11 display; no host display/socket is mounted. Create one `wx.App(False)` before importing `pcbnew`; do not add another app
inside a helper that already owns one. Keep native diagnostics enabled.

By default the entire repository is read-only and only its `work/` subtree is
writable. For a deliberately isolated source clone within this repository:

```sh
tools/kicad-run --repo work/my-candidate/repo --write-repo -- python3 tools/my_builder.py
```

The explicit write option is restricted to a clone below this project’s `work/`
directory. The owning checkout and other subdirectories are rejected. This is an
access setting, not authorization to overwrite a canonical source. A clone outside
this project is rejected. Absolute macOS
`/Applications/...` launch paths are rejected. Scripts that hard-code host paths
must be corrected to use their repository root or the Linux executable on `PATH`.

Every invocation has no network, no added capabilities, a read-only container root,
a 512 MB temporary directory, 4 GB memory limit, two CPUs, a process limit and a
single 300-second wall-clock timeout (configurable up to 1800 seconds). These are
runtime bounds, not a guarantee that a native library cannot crash. An abnormal
exit is retained and returned; there is no automatic rerun or host fallback.

Logs and command/image/exit metadata are saved under `work/kicad-runs/<run-id>/` in
the mounted repository. On timeout or interruption, the wrapper stops only its own
uniquely named container. It does not close the user's KiCad window or touch other
containers.

## Verification boundary

The smoke test loads the canonical main board, snapshots and iterates native
objects while retaining their owning board, saves **a copy in work/**, reloads it,
and compares the complete physical pin graph plus the canonical SHA256. It never
executes the known unsafe deletion loop. Native DRC is a separate invocation and
its findings remain visible. A successful runner smoke is not board acceptance or
proof that every possible pcbnew mutation is safe.

3D render/export smoke can use project-local models. Missing external system models
must be reported; the large optional 3D package is deliberately not installed.

## Verified local run and current limitations

The [verification record](verification.json) binds the image, canonical source,
smoke results, DRC comparison, guard probes and rendered output hashes. On
2026-10-20 the Linux runner loaded/iterated 196 footprints and 1,268 copper items,
saved/reloaded a work copy, and preserved the exact electrical graph and canonical
SHA256. Native DRC returned exit 5 with the same seven category counts (267 findings)
and 122 open connections as the tracked report. Individual selected silk pairs and
open-end representatives differ; the reports are not byte-identical and this does
not constitute board acceptance.

Six live guard probes verified exit-code propagation, read-only source/writable
scratch mounts, bounded timeout cleanup and rejected mounts/host paths. Six
host-only fault tests also cover failed cleanup, launch failure, SIGTERM handling,
preflight logging and scratch-write restrictions:

```sh
python3 tools/kicad-linux/test_runner.py
python3 tools/kicad-linux/verify_runner.py
```

`--init` is required: the first test left `xvfb-run` as PID 1 waiting for readiness.
That named container was stopped; no KiCad command had started. The image also uses
Xvfb `-noreset`, and its diagnostics are retained. Earlier wx startup failures are
recorded, not converted into successes. The final load/save, DRC, render and GLB
commands succeeded. Xvfb keyboard-symbol warnings and duplicate wx image-handler
messages remain visible in the logs.

After those successful jobs, Docker temporarily stopped responding even to
`docker ps`/image inspection; new requests were rejected before container launch.
OrbStack logged sleep followed by API timeouts. No daemon restart, broad cleanup or
unrelated-container action was performed. Parent independently observed recovery
with Docker 29.8.2. Run one native batch at a time; a failed request is never retried
automatically. This isolates the automation workflow; it does **not** fix or prove
safe the underlying native object-lifetime defect.

The work-only corrected-model render was generated successfully but is **not
accepted**: the native WRL renderer exposes connector-tail misalignment despite
expected transforms in the STEP-substituted GLB. No canonical model promotion was
performed. Model alignment must be resolved separately.
