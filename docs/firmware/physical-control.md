# Physical HA control ownership

The optional [physical-control bridge](../../integrations/physical_control/README.md)
now implements the missing persistent owner around the existing group coordinator,
sequence ledger and qualified motion transport. HA's locally selected physical mode
has covers plus informational diagnostics. Movement remains unavailable without
existing local commissioning/enrollment, and remote preflight still requires real
device clock, power, calibration, reference and I/O qualification.

A move reserves durable sequence space before any prepare. One native owner per
device suspends informational polling through preflight/movement/settling, then
requires the existing authenticated actual-OFF handoff before resuming telemetry.
The exact motion JSON and firmware qualification defaults are unchanged. The new
native handle is explicit; evaluation and telemetry-only handles retain their
restricted endpoint allowlists.

This is implemented localhost application wiring, not physical commissioning or
hardware/radio validation. See the bridge README for exact lifecycle, source ages,
STOP bounds, explicit recovery and fixture limits. The current board still needs
physical tests and records; this software does not manufacture them.

This is an integration candidate, not a passing release gate. Application ownership
and strict-schema checks are separate from the unchanged strict motion timing
campaign and its unresolved failures. A separately named scripted peer supplies
only explicit synthetic READY/terminal/OFF observations over real DTLS. Its original
seven-peer first clock fault remains unresolved despite a subsequent instrumented
pass. See the bridge README for the evidence boundaries; no firmware deadline,
clock model, qualification default or required check is relaxed.

The [integration checkpoint evidence](physical-control-checkpoint.json) records
current application checks separately from inherited authenticated-scripted
results, strict host timing failures and absent C6 physical qualification.

An independent owning-checkout run built all three native fixture configurations
and passed 63 application tests, 10 scripted transport checks and 12 read-only
telemetry checks. The full strict transport suite passed 46/49, the persistent
actor suite 7/10, and Home Assistant 18/19. The HA failure was the qualified
**scripted one-peer** case; both strict HA cases and all four scripted seven-peer
scenarios passed that run. The first one-peer fault occurred before movement and
still needs diagnosis. No test was retried or deadline relaxed. This change
remains under review and does not establish a passing release gate.

The first [review-branch CI run](https://github.com/0x63616c/smart-blinds/actions/runs/39564511324)
passed 12 of 13 jobs. Its failure was a separate test dependency error: the strict
seven-peer lifecycle reached its final schema check, which imported Home Assistant
in the lightweight transport job. The successor loads the actual validator without
the HA entrypoint and defers HTTP-library imports until a request. All schema
functions and the seven-peer assertion remain intact. A clean no-framework check
and two actual HA mocked-client regressions pass; fresh CI is pending.

The one-peer failure capture now retains the fixture's existing first-fault fields,
decoded requests and copied worker history. One targeted diagnostic execution with
that capture passed, preserving one connection through synthetic READY, movement,
terminal/OFF and resumed telemetry. It had no fault predicate to inspect and does
not resolve the original failure. Source review narrows the old failure to the
active clock guard: a currently qualified clock can still fail the stricter future
projection used during a move. No clock policy or timing bound was changed.
