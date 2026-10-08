# Security Policy

## OrbitWatch — Linux Satellite Ground Station

OrbitWatch is a Linux-based satellite ground-station software project designed for receiving, decoding, recording, analyzing, and visualizing satellite telemetry and radio data.

Security is treated as a core part of the system design, particularly because OrbitWatch interfaces with radio receivers, recorded signal data, telemetry, mission data, and operational interfaces.

---

## Supported Versions

OrbitWatch is currently developed as an active portfolio and research project.

Security fixes should be evaluated against the latest version of the project.

| Version                     | Supported   |
| --------------------------- | ----------- |
| Current development version | Yes         |
| Older development versions  | Best effort |
| Archived versions           | No          |

---

## Reporting a Vulnerability

If you discover a security vulnerability in OrbitWatch, please report it responsibly rather than publicly disclosing the issue immediately.

When reporting a vulnerability, provide:

* A clear description of the issue
* The affected component or file
* Steps required to reproduce the issue
* Expected behavior
* Actual behavior
* Potential security impact
* Relevant logs or screenshots, if safe to share
* A proposed mitigation, if known

Please do not include:

* Passwords
* API keys
* Authentication tokens
* Private keys
* Personal information
* Private network information
* Sensitive satellite or ground-station credentials

---

## Security-Sensitive Areas

The following areas require particular attention.

### 1. SDR Input

OrbitWatch is designed to receive radio data through an SDR subsystem.

Input from an SDR should be treated as untrusted data.

The system should not assume that received radio frames are valid merely because they originate from a known frequency or satellite.

---

### 2. Packet Decoding

AX.25, KISS, APRS, and telemetry payloads are external input.

Malformed or intentionally crafted frames must not be allowed to:

* Crash the application
* Execute arbitrary commands
* Escape expected parsing boundaries
* Corrupt persistent databases
* Cause uncontrolled resource consumption

Decoders should validate data before passing it to subsequent processing stages.

---

### 3. Telemetry Data

Telemetry received from external sources must be treated as untrusted.

Telemetry fields should be validated according to the expected data model.

OrbitWatch should not interpret telemetry payloads as executable code or shell commands.

---

### 4. Recorded Data

Recorded event files, IQ recordings, and replay datasets may contain untrusted content.

Replay functionality must process recorded data as data rather than executable content.

Do not execute scripts or binaries obtained from recordings.

---

### 5. Database Security

OrbitWatch uses local SQLite databases for telemetry and mission data.

Applications interacting with these databases should:

* Use parameterized SQL queries
* Validate externally supplied values
* Avoid constructing SQL statements through string concatenation
* Restrict database file permissions where appropriate
* Avoid committing sensitive operational databases to public repositories

---

### 6. Dashboard Security

The Mission Control dashboard is designed primarily as a local, read-only observation interface.

The dashboard should not expose unnecessary administrative or operating-system functionality.

The dashboard must not provide arbitrary shell execution through HTTP requests.

If the dashboard is deployed beyond localhost, additional security controls should be considered, including:

* Authentication
* HTTPS
* Network access restrictions
* Reverse-proxy security controls
* Request logging
* Rate limiting
* Host firewall rules

The development Flask server should not be treated as a production internet-facing server.

---

## RF Transmission Safety

OrbitWatch is designed around a receive-oriented ground-station workflow.

The dashboard currently reports:

```text
RF TX: DISABLED
```

No RF transmission capability should be enabled accidentally through the dashboard.

Any future transmission functionality must be implemented as an explicitly controlled subsystem with appropriate authorization, hardware safeguards, frequency restrictions, and operator confirmation.

Users are responsible for complying with applicable radio regulations and licensing requirements in their jurisdiction.

---

## Replay and Development Mode

OrbitWatch provides controlled replay/development functionality.

Replay data must be clearly distinguished from live RF telemetry.

Development data must not be presented as genuine live satellite telemetry.

The project uses explicit status information such as:

```text
REPLAY / DEVELOPMENT
```

when controlled development data is being processed.

This distinction is important for both technical correctness and operational safety.

---

## Secrets

Do not commit secrets to the repository.

Examples include:

* API keys
* Passwords
* Private keys
* Authentication tokens
* Cloud credentials
* Database credentials
* Personal access tokens
* SDR service credentials

If a secret is accidentally committed:

1. Revoke or rotate the credential immediately.
2. Remove the secret from the working tree.
3. Remove it from repository history where appropriate.
4. Check for unauthorized use.
5. Report the incident if necessary.

Removing a secret from the latest commit does not necessarily remove it from Git history.

---

## Sensitive Data

Do not commit private operational information to the public repository.

This includes:

* Personal IP addresses
* Private network topology
* MAC addresses
* Home network details
* Private radio infrastructure
* Credentials
* Personally identifying information
* Private telemetry datasets
* Sensitive station configuration

Public demonstrations should use sanitized or controlled development data.

---

## Dependency Security

Project dependencies should be kept reasonably current.

Before upgrading dependencies:

1. Review release notes.
2. Check compatibility.
3. Run the complete test suite.
4. Run compilation checks.
5. Verify the dashboard.
6. Verify replay functionality.

Dependency changes should not be accepted solely because a newer version exists.

---

## Secure Development Practices

Contributors should:

* Validate external input.
* Prefer safe parsing methods.
* Avoid shell execution where unnecessary.
* Avoid dynamic code execution.
* Use parameterized database queries.
* Keep secrets outside source code.
* Keep runtime data outside version control.
* Run tests before submitting changes.
* Review changes for unintended RF or operational behavior.
* Clearly distinguish simulated/replay data from live data.

---

## Runtime Data

Runtime databases, recordings, caches, generated files, and temporary artifacts should not normally be committed to the repository.

The project's `.gitignore` is intended to prevent accidental commits of these files.

---

## Responsible Disclosure

Security issues should be handled responsibly and privately whenever possible.

Please allow reasonable time for investigation and remediation before publicly disclosing a vulnerability.

---

## Scope

This policy applies to the OrbitWatch source code, dashboard, telemetry engine, protocol decoders, SDR interfaces, recording/replay system, mission logging system, simulation components, and supporting scripts.

OrbitWatch is an educational and portfolio-oriented ground-station project. Deployment in operational environments requires additional security review appropriate to the environment, hardware, radio configuration, and threat model.
