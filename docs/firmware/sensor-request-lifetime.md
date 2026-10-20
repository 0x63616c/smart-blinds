# Sensor requests survive OFF-grant waits

The sensor worker now rechecks the control-owned request after obtaining an OFF
transaction and before waiting indefinitely after a completed park. The latest
queue value remains authoritative. A notification only wakes the worker; its
count does not identify which request the worker has processed.

A forced host ordering exposed the missing check: sensing copied a parked
request, then waited for control to grant a physical OFF transaction. Control
published a newer awake request during that wait. The wait consumed its
notification, so sensing completed the older park and slept indefinitely. The
control worker remained responsive and qualified, but the gauge was never read
and power readiness remained false. The correction releases the old transaction
and reads the newer request through the existing owner loop.

The test also forces the reverse transition and STOP/fault arrivals. The existing
held-I/O cases still cover queued commands, STOP, source changes, lost connection,
raw button STOP, global fault and expired holds. The 30 ms physical OFF age,
40 ms queued-command age, motor timing bounds and source freshness requirements
are unchanged. Empty physical records still keep actuation disabled.

A separate test-only failure was exposed on Linux: `std::exit` could hang while
destroying a global condition variable with a live blocked worker. Assertions
now flush their diagnostic and use immediate failure exit. Successful tests
still close and join every owner. A subprocess regression deliberately fails
while a real sensor-worker call is blocked; it must report the expected cause
and exit with status 1 within three seconds. The full runtime test has its own
90-second CTest ceiling and names each case, independently of CI's job timeout.

The review checkpoint passes all 24 host tests in a Linux arm64 container using
Ubuntu GCC 13.3. This is deterministic host/SDK evidence, not a physical device
or radio timing qualification. A fresh published CI run is still required. The
original GitHub runner log did not expose the assertion preceding its timeout;
the independent Linux diagnostic run and both restored-bug controls are retained
in the review evidence instead of claiming that missing log was recovered.
