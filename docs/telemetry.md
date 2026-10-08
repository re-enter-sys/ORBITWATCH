# OrbitWatch Telemetry Architecture

## 1. Purpose

Telemetry is the structured information extracted from decoded satellite packets.

OrbitWatch separates telemetry processing from:

* radio acquisition
* protocol framing
* mission logging
* runtime state
* dashboard presentation

---

# 2. Telemetry Pipeline

```text
RF / Replay
     │
     ▼
Packet
     │
     ▼
Protocol Decoder
     │
     ▼
Payload
     │
     ▼
Telemetry Parser
     │
     ▼
Validated Telemetry
     │
     ├──────────────► Telemetry Database
     │
     ├──────────────► Mission Data
     │
     └──────────────► Mission Control
```

---

# 3. Development Telemetry

The controlled development replay demonstrates telemetry fields including:

```text
TEMP
BATT
MODE
```

Representative development samples:

```text
TEMP=23.5
BATT=7.4
MODE=SAFE
```

followed by subsequent controlled samples such as:

```text
TEMP=23.7
BATT=7.3
MODE=SAFE
```

and:

```text
TEMP=23.9
BATT=7.2
MODE=SAFE
```

These are controlled development values.

They are not claimed to be measurements received from a real satellite.

---

# 4. Telemetry Provenance

Telemetry should always have identifiable provenance.

OrbitWatch distinguishes:

```text
LIVE
```

from:

```text
REPLAY
```

Development records can include:

```text
mode=REPLAY
development=true
```

This information prevents downstream consumers from confusing development telemetry with real RF telemetry.

---

# 5. Telemetry vs Runtime State

Telemetry records describe processed measurements.

Runtime state describes current application operation.

Therefore:

```text
Telemetry:
    TEMP=23.9
    BATT=7.2

Runtime:
    IDLE
```

is completely valid.

The existence of telemetry records does not imply that the station is currently receiving.

---

# 6. Telemetry Persistence

Telemetry is persisted independently of runtime state.

This enables:

* historical inspection
* replay analysis
* dashboard visualization
* mission reporting
* debugging
* testing

The telemetry store is therefore an historical data source.

It should not be used as the authoritative source for current operating mode.

---

# 7. Telemetry Validation

Telemetry values should be validated before being accepted as structured data.

Validation should consider:

* required fields
* numeric conversion
* valid ranges
* packet sequence
* source
* protocol
* provenance

Malformed telemetry should not silently become valid records.

---

# 8. Packet Sequence

The development packets contain sequence numbers.

Example:

```text
1
2
3
```

Sequence information is useful for:

* ordering
* replay verification
* packet-loss analysis
* debugging
* telemetry correlation

---

# 9. Mission Correlation

Telemetry can be correlated with mission events and timestamps.

Conceptually:

```text
Timestamp
    │
    ├── Packet
    ├── Telemetry
    ├── Mission Event
    └── Recording
```

This makes it possible to reconstruct what the software observed during a processing session.

---

# 10. Telemetry Dashboard

Mission Control can present telemetry in a human-readable form.

The dashboard should treat telemetry as observed data rather than generate measurements itself.

This is particularly important in LIVE mode.

---

# 11. Replay Telemetry

Replay allows telemetry processing to be tested repeatedly.

The development workflow is:

```text
Recorded / controlled frame
          ↓
Replay
          ↓
Decode
          ↓
Telemetry extraction
          ↓
Persistence
          ↓
Dashboard
```

This provides deterministic development behavior without requiring RF hardware.

---

# 12. Error Handling

Telemetry processing should distinguish:

```text
Packet decoded
```

from:

```text
Telemetry valid
```

A packet can be syntactically valid while its payload is malformed.

Therefore validation must continue after protocol decoding.

---

# 13. Future Telemetry Extensions

Future versions may support:

* additional telemetry channels
* health/status metrics
* attitude data
* power subsystem information
* thermal data
* GPS/location telemetry
* signal-quality metrics
* packet-loss statistics
* telemetry alarms
* mission-specific schemas

Additional telemetry must retain provenance information.

---

# 14. Telemetry Design Principle

The central telemetry principle is:

> **Telemetry is data produced by the receive/replay pipeline; it is not proof of the current operating mode.**

That distinction is fundamental to OrbitWatch's architecture.
