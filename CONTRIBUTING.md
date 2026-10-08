# Contributing to OrbitWatch

Thank you for contributing to OrbitWatch.

OrbitWatch is a modular Linux satellite ground-station project focused on receive-side acquisition, signal processing, packet decoding, telemetry, tracking, recording, replay, and Mission Control.

---

# 1. Development Principles

Contributions should preserve:

* modular architecture
* testability
* clear data provenance
* receive-side safety
* explicit runtime state
* separation between historical data and current state
* clear documentation

---

# 2. Before Making Changes

Run:

```bash
pytest -q
```

and:

```bash
python -m compileall -q src
```

Make sure the existing project is healthy before starting work.

---

# 3. Code Structure

Major components include:

```text
groundstation/
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

Place new functionality in the subsystem that owns that responsibility.

Avoid putting processing logic directly into dashboard JavaScript or Flask routes when it belongs in a backend subsystem.

---

# 4. Runtime State

Do not infer current operating mode from historical telemetry.

Use the runtime state system.

The supported conceptual states are:

```text
IDLE
REPLAY
LIVE
```

LIVE must represent an actual receive-side pipeline.

---

# 5. Development Replay

Replay data must be clearly marked.

Development packets should not be represented as real satellite reception.

If adding replay functionality, preserve explicit indicators such as:

```text
mode=REPLAY
development=true
```

---

# 6. RF Safety

Do not add an RF transmission workflow without explicit architectural and safety review.

OrbitWatch is designed around receive-side operation.

Any radio-related contribution should clearly document:

* hardware assumptions
* frequency assumptions
* receive/transmit behavior
* regulatory considerations
* safety implications

---

# 7. Tests

New functionality should include tests where practical.

Run:

```bash
pytest -q
```

before submitting changes.

Also run:

```bash
python -m compileall -q src
```

---

# 8. Documentation

Update documentation when behavior changes.

Relevant documentation includes:

```text
README.md
docs/architecture.md
docs/operations.md
docs/protocols.md
docs/radio.md
docs/telemetry.md
```

Security-sensitive changes should also update:

```text
SECURITY.md
```

---

# 9. Dashboard Changes

The Mission Control dashboard has an established visual design.

Changes should avoid unnecessary visual redesign.

When implementing functionality:

* preserve the existing visual language
* avoid unrelated CSS changes
* keep the dashboard readable
* avoid adding controls that imply unsupported capabilities
* keep LIVE RF semantics accurate

---

# 10. Data Integrity

Do not commit:

* private network information
* credentials
* API keys
* SDR secrets
* private telemetry
* personal data
* unnecessary machine-specific configuration

Use sanitized or controlled example data for documentation.

---

# 11. Commit Guidelines

Use clear commit messages.

Examples:

```text
feat: add satellite pass filtering
fix: correct replay runtime lifecycle
test: add telemetry validation tests
docs: update SDR architecture
refactor: isolate packet decoder
```

---

# 12. Pull Requests

A useful pull request should describe:

1. What changed
2. Why it changed
3. Which subsystem is affected
4. How it was tested
5. Whether documentation was updated
6. Whether runtime behavior changed

---

# 13. Review Checklist

Before submitting:

```text
[ ] Tests pass
[ ] Source compiles
[ ] No secrets committed
[ ] No private network data committed
[ ] Runtime mode behavior remains explicit
[ ] Replay data is clearly labeled
[ ] LIVE is not simulated
[ ] Documentation reflects behavior
[ ] Dashboard appearance is not unnecessarily changed
```

---

# 14. Philosophy

OrbitWatch values correctness over impressive-looking simulation.

A controlled development replay is useful.

Pretending that controlled replay is live satellite reception is not.

Contributions should preserve that distinction.
