# OrbitWatch Radio and SDR Architecture

## 1. Purpose

OrbitWatch contains a receive-side software architecture for interacting with SDR hardware.

The radio subsystem is responsible for representing the receive path without coupling hardware operations directly to the telemetry or dashboard layers.

---

# 2. Receive Architecture

The intended receive path is:

```text
Antenna
   │
   ▼
RF Front End
   │
   ▼
SDR Hardware
   │
   ▼
IQ Samples
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

OrbitWatch does not transmit RF.

---

# 3. SDR Abstraction

The SDR subsystem provides hardware-independent concepts such as:

* device discovery
* receiver configuration
* receiver state
* start
* stop
* capture
* reconfiguration
* error state

This prevents the rest of the application from depending directly on a particular SDR implementation.

---

# 4. Receiver State

The receiver subsystem defines states such as:

```text
IDLE
STOPPED
READY
RECEIVING
ERROR
```

These states represent receiver lifecycle.

They are distinct from OrbitWatch's higher-level runtime modes:

```text
IDLE
REPLAY
LIVE
```

The two state models should not be treated as interchangeable.

---

# 5. Device Discovery

The SDR device manager can use available system discovery mechanisms to identify compatible receive hardware.

Where supported, command-line SDR discovery is preferred.

Hardware discovery does not automatically mean that OrbitWatch is receiving valid satellite data.

The system must still successfully enter the receive path.

---

# 6. Signal Acquisition

A receive session generally involves:

```text
Configure
   ↓
Open device
   ↓
Start receiver
   ↓
Capture samples
   ↓
Process samples
   ↓
Stop receiver
```

Actual implementation details depend on the connected SDR backend.

---

# 7. IQ Data

IQ samples represent the complex baseband signal produced by the SDR.

They can be represented conceptually as:

```text
I = in-phase component
Q = quadrature component

IQ = I + jQ
```

The signal-processing subsystem operates on these samples.

---

# 8. Signal Processing

Signal processing may include stages such as:

```text
IQ Input
   ↓
Filtering
   ↓
Frequency Processing
   ↓
Signal Conditioning
   ↓
Demodulation
   ↓
Bit / Symbol Stream
```

The exact processing chain depends on the target satellite signal.

---

# 9. Satellite Frequency

Satellite radio operation is inherently mission-specific.

A real deployment may require:

* known downlink frequency
* modulation
* symbol rate
* bandwidth
* polarization
* Doppler compensation
* antenna characteristics

OrbitWatch does not claim that one fixed radio configuration works for every satellite.

---

# 10. Doppler

A real satellite pass produces relative motion between the satellite and ground station.

That motion can shift the observed frequency.

A production receive pipeline may therefore need:

```text
Predicted satellite position
        ↓
Relative motion
        ↓
Doppler correction
        ↓
SDR tuning
```

OrbitWatch's orbit/pass subsystem is designed to provide the tracking information needed for such integrations.

---

# 11. LIVE RF Requirements

LIVE RF mode is only meaningful when the software is connected to an actual receive-side source.

The following is not sufficient:

```text
Telemetry exists
```

The following is required:

```text
Actual receive source
        ↓
SDR
        ↓
Signal processing
        ↓
Decoder
        ↓
Telemetry
```

This distinction prevents simulated data from being presented as live reception.

---

# 12. Replay vs RF

Replay:

```text
Controlled sample
     ↓
Decoder
     ↓
Telemetry
```

Live:

```text
RF
 ↓
SDR
 ↓
IQ
 ↓
Signal processing
 ↓
Decoder
 ↓
Telemetry
```

Both can share downstream software components, but their provenance must remain distinguishable.

---

# 13. RF Safety

OrbitWatch does not provide an RF transmit workflow.

This is intentional.

The project focuses on:

* receive-side acquisition
* signal processing
* decoding
* telemetry
* tracking
* visualization

Any future hardware expansion must maintain appropriate RF safety and regulatory controls.

---

# 14. Future Radio Integration

Potential future improvements include:

* broader SDR device support
* automatic device configuration
* Doppler correction
* signal-quality monitoring
* frequency tracking
* automatic pass acquisition
* additional demodulators
* hardware-specific optimizations

Such features should be implemented without changing the data-provenance rules of the existing architecture.
