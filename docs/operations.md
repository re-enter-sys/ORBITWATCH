# OrbitWatch Operations Guide

## 1. Purpose

This document describes how to install, start, operate, test, and troubleshoot OrbitWatch.

OrbitWatch supports three operational states:

```text
IDLE
REPLAY / DEVELOPMENT
LIVE RF
```

The built-in development workflow uses controlled replay data.

---

# 2. Requirements

Recommended environment:

* Linux
* Python 3
* Python virtual environment
* required Python dependencies
* optional SDR hardware for actual receive-side development

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# 3. Project Setup

Enter the project:

```bash
cd Linux-Satellite-Ground-Station
```

Optional virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# 4. Available Commands

The project provides:

```bash
./scripts/run.sh dashboard
./scripts/run.sh demo
./scripts/run.sh help
```

---

# 5. Start Mission Control

Run:

```bash
./scripts/run.sh dashboard
```

The dashboard starts locally.

The dashboard is designed as Mission Control and is primarily read-oriented.

---

# 6. Run Development Replay

Run:

```bash
./scripts/run.sh demo
```

The development replay uses controlled data.

It does not perform RF transmission.

A successful run reports information about:

* replay status
* satellite identifier
* recording
* packets processed
* packets decoded
* failed packets
* telemetry database
* mission database
* recording path

---

# 7. Development Replay Lifecycle

The expected lifecycle is:

```text
IDLE
 │
 │ Start demo
 ▼
REPLAY
 │
 │ Process controlled frames
 ▼
Telemetry / Recording
 │
 │ Replay complete
 ▼
IDLE
```

The replay process should not remain active after the development dataset has been consumed.

---

# 8. Dashboard Replay

The Mission Control dashboard can request:

```text
REPLAY
```

through the mode API.

The dashboard starts the development replay process.

The replay process owns the active replay lifecycle.

Once the replay completes, runtime state returns to IDLE.

---

# 9. Checking Runtime State

Runtime state is stored in:

```text
data/runtime/state.json
```

Inspect it:

```bash
cat data/runtime/state.json
```

Example IDLE state:

```json
{
  "mode": "IDLE",
  "session_id": null,
  "satellite": null,
  "data_source": "NONE",
  "started_at": null,
  "status": "idle"
}
```

Example replay state:

```json
{
  "mode": "REPLAY",
  "satellite": "OW-DEMO",
  "data_source": "REPLAY",
  "status": "running"
}
```

---

# 10. Checking the Mode API

Read the current mode:

```bash
curl -s http://127.0.0.1:5000/api/mode | python -m json.tool
```

Request replay:

```bash
curl -i -X POST http://127.0.0.1:5000/api/mode \
  -H 'Content-Type: application/json' \
  -d '{"mode":"REPLAY"}'
```

A successful request returns:

```text
HTTP/1.1 202 ACCEPTED
```

---

# 11. Selecting IDLE

The API can explicitly return the system to IDLE:

```bash
curl -i -X POST http://127.0.0.1:5000/api/mode \
  -H 'Content-Type: application/json' \
  -d '{"mode":"IDLE"}'
```

---

# 12. LIVE RF

The dashboard does not simulate LIVE RF.

Requesting LIVE through the dashboard is rejected because LIVE requires an actual receive-side pipeline.

This prevents:

```text
Development Data
       ↓
False claim of
       ↓
LIVE RF
```

---

# 13. Recordings

Event recordings are stored under:

```text
data/recordings/events/
```

List recent recordings:

```bash
find data/recordings/events -type f | sort | tail
```

Inspect JSONL event count:

```bash
wc -l data/recordings/events/*.jsonl
```

Inspect an event recording:

```bash
head data/recordings/events/<recording>.jsonl
```

---

# 14. Recording Format

OrbitWatch records event-oriented data as JSON Lines.

Each line represents one event.

Example:

```json
{
  "timestamp": "...",
  "event_type": "KISS_FRAME",
  "payload": {
    "mode": "REPLAY",
    "development": true,
    "protocol": "KISS/AX.25"
  }
}
```

---

# 15. Testing

Run:

```bash
pytest -q
```

Compile the source:

```bash
python -m compileall -q src
```

A successful compile produces no output.

---

# 16. Debugging the Dashboard

For development debugging:

```bash
PYTHONPATH="$PWD/src" python -m src.main dashboard --debug
```

The Flask debugger should only be used during local development.

Do not expose the development debugger to an untrusted network.

---

# 17. Runtime Troubleshooting

### Dashboard reports REPLAY unexpectedly

Check:

```bash
cat data/runtime/state.json
```

If runtime state is IDLE but historical telemetry exists, the system is behaving correctly.

Historical records should not automatically change the current mode.

### Replay does not start

Check:

```bash
python -m compileall -q src
```

Then inspect the dashboard server output.

Test the API directly:

```bash
curl -i -X POST http://127.0.0.1:5000/api/mode \
  -H 'Content-Type: application/json' \
  -d '{"mode":"REPLAY"}'
```

### Replay starts and immediately disappears

A short development replay can legitimately finish quickly.

Check for newly created recordings:

```bash
find data/recordings/events -type f -printf '%T@ %p\n' | sort -n | tail
```

Then inspect the newest JSONL recording.

---

# 18. Operational Safety

OrbitWatch should be operated with the following assumptions:

* RF transmission is disabled.
* LIVE RF requires real receive-side input.
* Replay data is development data.
* The dashboard should not be treated as a flight-control system.
* Development debug mode should remain local.
* Actual RF operation requires appropriate hardware and regulatory compliance.

---

# 19. Recommended Development Workflow

Use:

```text
1. Start in IDLE
2. Run tests
3. Start Mission Control
4. Start REPLAY / DEVELOPMENT
5. Inspect telemetry
6. Inspect recordings
7. Inspect mission data
8. Confirm runtime returns to IDLE
9. Run tests again after code changes
```

---

# 20. Operational Principle

The most important operating rule is:

> **Never confuse a successful software replay with successful reception of a real satellite signal.**

OrbitWatch explicitly maintains this distinction throughout the runtime, recording, and dashboard layers.
