# OrbitWatch Protocols and Packet Processing

## 1. Purpose

This document describes the packet and protocol-processing architecture used by OrbitWatch.

The protocol layer is responsible for transforming received or replayed frames into structured information that can be consumed by the telemetry subsystem.

---

# 2. Protocol Processing Pipeline

```text
Input
  │
  ▼
Frame
  │
  ▼
Framing / Packet Handling
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
Structured Telemetry
```

The protocol layer is intentionally separate from the dashboard and persistence layers.

---

# 3. KISS

OrbitWatch's development replay demonstrates KISS-framed packet data.

KISS is commonly used to carry AX.25 frames between a host computer and a TNC-style interface.

The development frames contain KISS framing bytes around the encoded frame.

A representative KISS frame begins and ends with:

```text
C0
```

The development recording may therefore contain a hexadecimal representation such as:

```text
c00082a0...
...
c0
```

The exact frame contents depend on the generated development packet.

---

# 4. AX.25

The development packet pipeline uses KISS/AX.25-style frames.

AX.25 is a packet protocol widely associated with amateur packet radio and APRS-related systems.

OrbitWatch uses the protocol layer to separate:

```text
Frame
```

from:

```text
Telemetry Payload
```

This allows downstream telemetry processing to remain independent from the framing details.

---

# 5. Development Packet

A representative development packet contains:

```text
Protocol:
    KISS/AX.25

Satellite:
    OW-DEMO

Source:
    OWDEMO

Destination:
    APRS

Packet sequence:
    1, 2, 3, ...

Development:
    true
```

The development marker is important because it establishes data provenance.

---

# 6. Telemetry Payload

The controlled development payload contains simple telemetry values.

Representative fields include:

```text
TEMP
BATT
MODE
```

Example:

```text
TEMP=23.5
BATT=7.4
MODE=SAFE
```

These values are development data and must not be interpreted as measurements from an actual satellite unless they have entered the pipeline through a verified live receive source.

---

# 7. Packet Sequence

Development packets contain a packet sequence number.

Example:

```text
packet_sequence=1
packet_sequence=2
packet_sequence=3
```

Sequence information helps demonstrate packet ordering and gives the recording pipeline an identifiable progression.

---

# 8. Packet Processing Responsibilities

The protocol layer should handle:

* framing
* packet boundaries
* protocol identification
* protocol decoding
* payload extraction
* malformed packet handling

The telemetry layer should handle:

* telemetry field interpretation
* validation
* structured telemetry
* persistence

The dashboard should not perform protocol decoding itself.

---

# 9. Error Handling

Malformed packets should not silently become valid telemetry.

The processing pipeline should distinguish between:

```text
Decoded
```

and:

```text
Failed
```

This allows replay and live receive workflows to report processing quality.

---

# 10. Protocol Extensibility

Future protocol implementations can be added without coupling them directly to the Mission Control frontend.

Possible future protocol support could include:

* additional AX.25 variants
* custom satellite framing
* additional KISS-compatible packet formats
* other telemetry packet formats
* mission-specific protocols

Any new protocol should provide a clean boundary between raw frame data and structured payload data.

---

# 11. Data Provenance

OrbitWatch treats provenance as part of protocol processing.

Development data should carry indicators such as:

```text
mode=REPLAY
development=true
```

This makes it possible for downstream systems to distinguish controlled replay from live receive data.

---

# 12. Security Considerations

Protocol decoders should treat incoming packet content as untrusted data.

A real RF packet may contain malformed or unexpected values.

Therefore:

* validate field boundaries
* validate numeric values
* reject malformed frames
* avoid executing packet payloads
* avoid treating packet content as application commands
* keep protocol parsing separate from operating-system execution

---

# 13. Protocol Summary

The OrbitWatch packet architecture is:

```text
RF / Replay
    ↓
Frame
    ↓
KISS
    ↓
AX.25
    ↓
Payload
    ↓
Telemetry Parser
    ↓
Structured Telemetry
```

The development replay demonstrates this architecture without requiring live RF reception.
