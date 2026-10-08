# OrbitWatch Architecture

## 1. Purpose

OrbitWatch is structured as a modular Linux satellite ground-station application.

The architecture separates:

* satellite tracking
* SDR hardware access
* signal processing
* packet decoding
* telemetry
* recording
* mission logging
* runtime state
* dashboard presentation

The goal is to keep each subsystem independently testable and replaceable.

---

# 2. High-Level Architecture

```text
                         ┌──────────────────────┐
                         │ Satellite Catalog    │
                         │ Orbit / Pass Engine  │
                         └──────────┬───────────┘
                                    │
                                    ▼
┌──────────────┐          ┌──────────────────────┐
│ Antenna / RF │ ───────► │ SDR Receive Layer   │
└──────────────┘          └──────────┬───────────┘
                                     │
                                     ▼
                           ┌─────────────────────┐
                           │ IQ / Signal Layer   │
                           └──────────┬──────────┘
                                      │
                                      ▼
                           ┌─────────────────────┐
                           │ Demodulation /      │
                           │ Signal Processing   │
                           └──────────┬──────────┘
                                      │
                                      ▼
                           ┌─────────────────────┐
                           │ Protocol / Packet   │
                           │ Decoder             │
                           └──────────┬──────────┘
                                      │
                                      ▼
                           ┌─────────────────────┐
                           │ Telemetry Engine    │
                           └──────┬─────┬────────┘
                                  │     │
                     ┌────────────┘     └────────────┐
                     ▼                               ▼
              ┌─────────────┐                 ┌─────────────┐
              │ Recording   │                 │ Mission Log │
              └──────┬──────┘                 └──────┬──────┘
                     │                               │
                     └──────────────┬────────────────┘
                                    ▼
                          ┌─────────────────────┐
                          │ Mission Control     │
                          │ Dashboard           │
                          └─────────────────────┘
```

---

# 3. Source Tree

```text
src/
├── main.py
└── groundstation/
    ├── cli.py
    ├── config.py
    ├── runtime.py
    ├── dashboard/
    ├── mission/
    ├── pipeline/
    ├── protocols/
    ├── recording/
    ├── satellites/
    ├── sdr/
    ├── signal/
    ├── simulation/
    └── telemetry/
```

---

# 4. Runtime State Architecture

Runtime state is deliberately separated from telemetry storage.

The runtime state describes:

```text
What is the station doing now?
```

Telemetry storage describes:

```text
What data has the station processed?
```

These are different questions.

The runtime subsystem provides explicit states:

```text
IDLE
REPLAY
LIVE
```

A representative state is:

```json
{
  "mode": "REPLAY",
  "session_id": null,
  "satellite": "OW-DEMO",
  "data_source": "REPLAY",
  "started_at": "...",
  "updated_at": "...",
  "status": "running"
}
```

---

# 5. Why Runtime State Is Separate

Suppose the database contains telemetry from yesterday's replay:

```text
500 records
```

That does not mean the station is currently replaying.

Therefore:

```text
Telemetry DB != Runtime State
```

The dashboard reads runtime state for current mode information.

This prevents historical records from changing current operational state.

---

# 6. Replay Architecture

The development replay is launched as a separate process.

```text
Dashboard
    │
    │ POST /api/mode
    │ mode=REPLAY
    ▼
Runtime Manager
    │
    ▼
Replay Process
    │
    ▼
Controlled Sample Data
    │
    ▼
Packet Decoder
    │
    ▼
Telemetry
    │
    ├──► Recording
    └──► Mission Data
```

When replay finishes:

```text
Replay Process
      │
      ▼
    set_idle()
      │
      ▼
Runtime = IDLE
```

---

# 7. LIVE RF Boundary

LIVE mode has a stricter requirement.

```text
LIVE
  │
  ▼
Actual receive-side input
  │
  ▼
SDR
  │
  ▼
Signal processing
```

The dashboard cannot manufacture LIVE RF data.

This is an intentional architectural boundary.

---

# 8. Dashboard Architecture

The dashboard consists of:

```text
dashboard/
├── app.py
├── routes.py
├── templates/
│   └── index.html
└── static/
    ├── css/
    │   └── dashboard.css
    └── js/
        └── dashboard.js
```

`app.py` creates and runs the Flask application.

`routes.py` provides API endpoints.

The frontend uses JavaScript to retrieve current station information and interact with the runtime mode API.

---

# 9. API Architecture

The mode API provides two responsibilities:

### GET

```text
GET /api/mode
```

Reads the current runtime state.

It does not infer mode from historical telemetry.

### POST

```text
POST /api/mode
```

Accepts a requested operating mode.

Supported behavior:

```text
IDLE
    → activate IDLE

REPLAY
    → start controlled development replay

LIVE
    → reject dashboard simulation
```

---

# 10. Data Flow

## Development Replay

```text
Controlled sample
      │
      ▼
Packet generation
      │
      ▼
KISS/AX.25 frame
      │
      ▼
Packet decoder
      │
      ▼
Telemetry extraction
      │
      ├──► Telemetry storage
      ├──► Event recording
      └──► Mission data
```

## Live Receive Path

The intended live architecture is:

```text
RF
 │
 ▼
Antenna
 │
 ▼
SDR
 │
 ▼
IQ
 │
 ▼
Signal Processing
 │
 ▼
Demodulation
 │
 ▼
Packet Decoder
 │
 ▼
Telemetry
```

---

# 11. Persistence Boundaries

OrbitWatch maintains different categories of persistent information.

```text
data/
├── mission/
├── recordings/
├── samples/
├── satellites/
└── telemetry/
```

Runtime state is maintained separately:

```text
data/runtime/state.json
```

This organization helps prevent state contamination between subsystems.

---

# 12. Safety Boundaries

The architecture intentionally prevents:

* simulated data being presented as live RF
* historical telemetry determining current mode
* dashboard controls silently transmitting RF
* development replay being confused with hardware reception

The project is therefore suitable for development and demonstration without requiring an RF transmitter.

---

# 13. Extensibility

The architecture can be extended with:

* additional SDR backends
* additional modulation schemes
* additional packet protocols
* additional telemetry schemas
* additional satellite sources
* additional recording formats
* additional visualization components

New components should preserve existing subsystem boundaries.

---

# 14. Design Principles

OrbitWatch follows:

1. Separation of concerns
2. Explicit runtime state
3. Receive-side safety
4. Deterministic development replay
5. Testable components
6. Clear data provenance
7. Replaceable hardware abstractions
8. Read-oriented Mission Control

---

# 15. Architectural Summary

OrbitWatch is best understood as a layered receive-side ground-station architecture:

```text
Tracking
   ↓
Acquisition
   ↓
Signal Processing
   ↓
Protocol Decoding
   ↓
Telemetry
   ↓
Persistence
   ↓
Mission Control
```

The runtime layer crosses these components by defining the current operating state without becoming dependent on historical telemetry.
