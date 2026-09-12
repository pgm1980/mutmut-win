# Execution-basis diagnostics

`mutmut-win run --basis-diagnostics C:\evidence\run-01.json` records the inputs
observed by execution-basis hashing. The absolute destination must be a new file
in an existing directory outside the project, interpreter, import and editable
source roots. Nothing is written to it until the run exits. No environment
variable or configuration field activates this option.

The canonical hash byte streams, completeness flags and authority decisions are
unchanged. The diagnostic recorder attributes every update to a stream and an
ordered component occurrence. It also records actual read errors and return
flags, including incomplete traversals that add no hash bytes. File contents,
bound metadata and the three existing file-identity observations are separated.
Environment entries and runtime/configuration field tokens come from the values
already consumed by the canonical computation.

Reports contain paths, environment variable names and numeric file metadata.
They contain no raw environment values or raw file contents. Private per-session
HMAC tokens allow comparison within one report; their key is not exported, and
tokens from separate reports cannot be compared directly.

Each snapshot has the four returned basis fields, timing, process/thread identity,
component IDs/parents/occurrences, events and hash-stream attribution. Adjacent
snapshots have explicit deltas. A normally completed real run currently takes four
snapshots: two at the start and two at the end, yielding three adjacent transitions.
An aborted run can contain fewer. `diagnostics_complete` describes the observations
that were captured; it does not certify a complete mutation campaign or authorized
results. Check run completion, expected snapshot count, JSON/SQLite identities and
authority fields separately.

Recording errors produce an incomplete report. An unsafe dynamically discovered
destination or publication failure produces a stderr diagnostic and no usable
report. Such failures never promote or revoke execution evidence and must stop an
investigation from treating that run as a complete diagnostic capture.

Observation adds CPU, memory and elapsed time. Hash parity does not prove temporal
neutrality. These are four observation windows, not an atomic environment history.
A changed input identifies an interval; it does not identify the writing process.
Unchanged repetitions do not resolve historical invalidations whose original
component observations are missing.
