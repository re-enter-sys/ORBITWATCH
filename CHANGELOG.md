# Changelog

All notable changes to **OrbitWatch — Linux Satellite Ground Station** are documented here.

The project follows a milestone-based development approach. Each milestone adds a functional layer to the ground-station pipeline while preserving the existing system architecture and safety boundaries.

## [Unreleased]

### Documentation

* Finalized portfolio-oriented project documentation.
* Added GitHub-ready project structure and usage documentation.
* Added Mission Control screenshot documentation.
* Documented Replay / Development mode and its distinction from live RF operation.
* Documented read-only dashboard and RF transmission safety boundaries.
* Documented the complete receive-side data pipeline.
* Documented satellite tracking and pass prediction.
* Documented SDR architecture and receiver lifecycle.
* Documented signal-processing responsibilities.
* Documented KISS/AX.25 development packet handling.
* Documented telemetry processing and provenance.
* Documented recording and controlled replay.
* Documented Mission Control operations.
* Documented explicit runtime operating modes.
* Documented the distinction between runtime state and historical telemetry.
* Added clearer safety and security guidance.
* Updated contribution and operational guidance.

---

# Milestone 10 — Simulation / Development Replay

## Added

* Controlled development replay workflow.
* Development packet generation.
* Replay processing through the downstream telemetry pipeline.
* Explicit replay/development markers.
* Replay recording support.
* Demonstration satellite identifier `OW-DEMO`.
* Controlled KISS/AX.25 development frames.

## Safety

* Development replay does not perform RF transmission.
* Development data is explicitly marked as replay/development data.
* Replay is not represented as live satellite reception.

---

# Milestone 9 — Mission Log

## Added

* Mission event persistence.
* Mission-oriented operational history.
* Separation between mission records and telemetry records.
* Mission data integration with Mission Control.

---

# Milestone 8 — Recording and Replay

## Added

* Event recording.
* JSON Lines recording format.
* Recording storage under `data/recordings/events/`.
* Replay-oriented development workflow.
* Recorded packet/event inspection.

---

# Milestone 7 — Mission Control Dashboard

## Added

* Flask-based Mission Control dashboard.
* Dashboard API routes.
* Telemetry visualization.
* Mission information.
* Timeline information.
* Packet/development information.
* Dashboard runtime status.

## Design

* Established the dark deep-space Mission Control visual design.
* Dashboard remains read-oriented.
* RF transmission controls are intentionally absent.

---

# Milestone 6 — Telemetry Engine

## Added

* Structured telemetry processing.
* Telemetry persistence.
* Telemetry validation.
* Packet-to-telemetry processing.
* Development telemetry fields including temperature, battery, and operating mode.

---

# Milestone 5 — Packet Decoding

## Added

* Packet decoding architecture.
* KISS framing support.
* AX.25-oriented packet processing.
* Packet validation.
* Packet sequence handling.
* Decoder error handling.

---

# Milestone 4 — Signal Processing

## Added

* Signal-processing subsystem.
* IQ-oriented processing architecture.
* Processing boundaries between SDR input and packet decoding.

---

# Milestone 3 — SDR Subsystem

## Added

* SDR device abstraction.
* SDR discovery.
* Receiver lifecycle.
* Receiver states.
* Receive/capture architecture.
* Device management.

## Safety

* Receive-side architecture maintained.
* RF transmission excluded.

---

# Milestone 2 — Orbit and Pass Prediction

## Added

* Satellite orbital tracking architecture.
* Pass prediction.
* Satellite position/tracking components.
* Orbit-related data structures.

---

# Milestone 1 — Satellite Catalog

## Added

* Satellite catalog subsystem.
* Satellite metadata handling.
* Satellite-oriented configuration.

---

# Milestone 0 — Foundation

## Added

* Initial Linux satellite ground-station project structure.
* Python package architecture.
* CLI foundation.
* Configuration foundation.
* Test framework.
* Project scripts.
* Documentation structure.
* CI workflow.
* Initial data directories.

---

## [0.1.0] — OrbitWatch Mission Control Foundation

### Added

#### Foundation

* Project architecture for a Linux-based satellite ground station.
* Central configuration system.
* Command-line interface.
* Modular ground-station package structure.
* Automated test infrastructure.
* Project setup, run, and test scripts.

#### Satellite Catalog

* Satellite catalog subsystem.
* Satellite identification and lookup.
* Satellite metadata handling.
* Satellite selection for tracking workflows.

#### Orbit and Pass Prediction

* Orbit propagation support.
* Satellite position calculations.
* Ground-station pass prediction.
* Visibility and pass-window calculations.
* Orbital tracking data exposed to Mission Control.

#### SDR Subsystem

* SDR device abstraction.
* Device discovery.
* Receiver abstraction.
* IQ sample handling.
* Receiver configuration for center frequency, sample rate, gain, and PPM correction.
* Explicit RF transmission boundary: OrbitWatch is receive-only.

#### Signal Processing

* Signal filtering pipeline.
* Synchronization stage.
* Demodulation architecture.
* Support for modulation-processing workflows used by supported satellite protocols.

#### Packet Processing

* AX.25 frame handling.
* KISS framing and deframing.
* Packet validation.
* CRC handling.
* Packet metadata extraction.
* APRS-oriented packet workflow support.

#### Telemetry

* Telemetry decoding.
* Telemetry field parsing.
* Telemetry engine.
* Persistent telemetry database.
* Telemetry history.
* Satellite-associated telemetry records.
* Packet validity and CRC state tracking.

#### Mission Control Dashboard

* Dark deep-space Mission Control interface.
* Satellite status panel.
* Signal and radio status.
* Live/replay telemetry presentation.
* Packet analysis.
* Telemetry timeline.
* Orbit tracking.
* Mission information.
* Processing pipeline status.
* Read-only interaction model.
* Dashboard API endpoints.
* Health endpoint.

#### Recording and Replay

* Event recording.
* IQ recording architecture.
* Recording metadata.
* Replay reader.
* Controlled development/replay workflow.
* Replay data clearly identified as `REPLAY / DEVELOPMENT`.

#### Mission Log

* SQLite-backed Mission Log.
* Mission event persistence.
* Event severity.
* Event types.
* Satellite filtering.
* Mission filtering.
* Search support.
* Mission event statistics.
* Mission event detail views.

#### Simulation / Development

* Controlled development mission.
* Sample packet generation.
* Development telemetry generation.
* End-to-end replay workflow.
* Demonstration command for exercising the complete telemetry pipeline without RF transmission.

### Safety

* No RF transmission functionality exposed by Mission Control.
* Dashboard controls remain read-only.
* Replay/development data is explicitly labeled.
* No synthetic data is presented as live RF contact.
* External SDR/protocol input is treated as untrusted data.
* Runtime databases and recordings are separated from source-controlled project assets.

### Validation

Current automated validation:

```text
318 passed
```

The complete test suite covers:

* API behavior
* AX.25
* KISS
* telemetry
* telemetry engine
* telemetry database
* satellite catalog
* orbit calculations
* pass prediction
* SDR subsystem
* signal processing
* recording/replay
* simulation
* Mission Log
* pipeline integration

---

## Development Milestones

| Milestone | Component                       | Status   |
| --------- | ------------------------------- | -------- |
| 0         | Foundation                      | Complete |
| 1         | Satellite Catalog               | Complete |
| 2         | Orbit / Pass Prediction         | Complete |
| 3         | SDR Subsystem                   | Complete |
| 4         | Signal Processing               | Complete |
| 5         | Packet Decoding                 | Complete |
| 6         | Telemetry Engine                | Complete |
| 7         | Mission Control Dashboard       | Complete |
| 8         | Recording & Replay              | Complete |
| 9         | Mission Log                     | Complete |
| 10        | Simulation / Development Replay | Complete |

---

## Future Development

Potential future improvements may include:

* Additional SDR hardware integrations.
* Additional satellite protocol decoders.
* More modulation/demodulation implementations.
* Expanded telemetry schemas.
* Improved orbital visualization.
* Additional ground-station configuration profiles.
* Hardware-specific integration testing.
* Extended packet analysis.
* More comprehensive recording metadata.
* Additional automated integration tests.

Future functionality must preserve the receive-only safety boundary and must clearly distinguish live RF data from replay/development data.
