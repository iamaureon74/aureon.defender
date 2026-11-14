# Aureon Defender: Raspberry Pi additions and patent research

Researched and extended on 2026-11-14. This is source work in the existing
`aureon-hardware` project, not a rebuilt or deployed Windows executable.

## Software choices

| Component | Purpose | Current Aureon state |
|---|---|---|
| [USBGuard](https://usbguard.github.io/) | Linux USB authorization policies; descriptors can be spoofed, so this is one defensive layer | New Pi sensor inventories USB and checks daemon state. Does not install or configure enforcement. GPL-2.0 project. |
| [AIDE](https://aide.github.io/) | Baseline and compare file contents/metadata | New sensor checks tool presence only. Real file-integrity checks still need an initialized trusted AIDE database, scoped rules and scheduled checks. |
| [Lynis](https://github.com/CISOfy/lynis) | Linux configuration auditing | Already catalogued; sensor checks presence. No automatic hardening. |
| [CrowdSec](https://docs.crowdsec.net/docs/intro/) | Log-driven behavioral detections | Existing shield stack and analyst support; requires correct log acquisition and an enforcement component to block. New sensor checks host service state. |
| [Suricata](https://docs.suricata.io/) | Network IDS alerts | Existing optional shield stack and EVE analyst importer. Needs actual traffic visibility, suitable rules and Pi throughput testing. |
| [Zeek](https://zeek.org/) | Network protocol metadata | Already catalogued. Size and tune deployment to available CPU/storage and captured traffic. |
| [Kismet](https://www.kismetwireless.net/docs/readme/intro/kismet/) | Passive wireless observations | Previously researched; needs a compatible capture radio. Not installed by this extension. |

Use a supported 64-bit Raspberry Pi OS and verify current package/ARM availability
on the actual board. This Windows session did not test Pi execution, package
installation, container architecture support or throughput. A catalog entry is
not an installed capability. Host systemd service state does not reflect Docker
container state, and a running service alone does not demonstrate protection.

Prioritize USBGuard/AIDE for the Pi itself, then tune existing network sensors.
Do not run every heavyweight IDS and analytics stack on one board by default.
The Pi's USB inventory covers its own USB bus, not the laptop's physical ports.

## New implemented sensor

From the project checkout on the Pi:

```sh
python -m aureon.security_node --out security-node.json
# Review this snapshot and store it somewhere trusted before using it as a baseline.
python -m aureon.security_node --baseline trusted-baseline.json --out security-node.json
```

The collector reads Linux sysfs USB descriptors, emits SHA-256 descriptor
fingerprints without exporting raw serial numbers, compares port/fingerprint
pairs, checks tool presence, and queries systemd states for USBGuard, CrowdSec,
Suricata and auditd. Missing visibility and failed collection are explicit.
Serial hashing is pseudonymization, not strong anonymization or device attestation.
Expected device swaps and port moves can produce differences; a difference does
not identify an attacker. No commands block USB, install packages or change a firewall.

Copy `security-node.json` through an existing trusted transfer method to Aureon's
data directory as returned by `core.data_dir()` (normally `C:\ProgramData\Aureon`,
with environment/per-user fallbacks). The desktop source displays service states
and findings under Network & Power. Reports older than five minutes or more than
one minute in the future are marked stale/clock-invalid. Imported JSON is an
operator-supplied snapshot, not authenticated live attestation. No SSH transport,
background scheduling or automatic baseline acceptance was added.

USBGuard enforcement needs a reviewed allowlist and a recovery path, especially
if keyboard/network access uses USB. AIDE requires an independently trusted
baseline; accepting a compromised state as the baseline defeats its purpose.

## Patent resources and concrete research leads

Open-source software licenses, patent licenses and publicly disclosed patent
documents are different things. [WIPO's patent FAQ](https://www.wipo.int/en/web/patents/faq_patents)
explains disclosure and licensing. Public disclosure alone does not authorize
implementing an invention.

Google's [OPN patent list](https://www.google.com/patents/opnpledge/patents/)
includes security-related disclosures. Three research leads verified against that
list and their patent documents:

| Patent | Research subject | Potential Aureon direction, not an implemented patent |
|---|---|---|
| [US6839841B1](https://patents.google.com/patent/US6839841B1/en) | Device-side certificate creation using protected processing | Study hardware-backed node identity and enrollment. |
| [US7007104B1](https://patents.google.com/patent/US7007104B1/en) | Correlation of network and system management events | Study a shared event model linking node, network and host observations. |
| [US7039807B2](https://patents.google.com/patent/US7039807B2/en) | Workflows for obtaining digital signatures | Study authenticated report approval and provenance. |

The proposed Aureon directions are engineering inferences, not claim mappings.
No patent claims were implemented in this change. Although Google Patents shows
expired status for these US documents, those labels are not independently verified
legal conclusions or clearance of related families/other rights.

Read the actual [Google OPN pledge](https://www.google.com/patents/opnpledge/pledge/):
it covers specified patents and qualifying FOSS activities, includes defensive
termination and important exclusions for hardware and certain combinations.
It is not blanket permission for a proprietary hardware/software appliance.

[Red Hat's patent promise](https://www.redhat.com/en/about/patent-promise) provides
conditional non-assertion for covered FOSS, with defined combination and defensive
limits. It supplies no plug-in source code or certification for this project.

[OIN's agreement](https://openinventionnetwork.com/license-agreement-2/) is a
royalty-free licensing arrangement with reciprocal obligations and defined scope.
No agreement was signed or accepted in this session. These resources are research
and licensing paths, not a determination that Aureon has freedom to operate.

For near-term implementation, mature maintained FOSS is more useful than
reimplementing old patented cryptography. A later authenticated Pi transport
should use established TLS/device-key libraries and a specified enrollment model.

## Logo verified

Existing files: `windows/assets/aureon.png`, `aureon.ico`, and dashboard
`windows/aureon_defender/ui/icon.png`. The image is a cream shield with an amber
sunrise over a dark rounded square. The build script references the ICO, and
the dashboard references `/icon.png`. The assets already existed; no new logo
was generated. The currently running application's embedded icon was not extracted.

## Checks

Six new sensor tests pass: USB identity change, raw serial exclusion, absent bus,
invalid baseline rejection, Windows visibility limits, service collection errors,
and report staleness (some checks share tests). Nine earlier infrastructure tests
also pass. Python compilation and dashboard JavaScript syntax are checked.
Live Pi, USBGuard enforcement, AIDE checks, visual browser validation, Windows
rebuild and deployment remain unperformed. Earlier broad suites had a feed fixture
failure and three Linux-shell failures due to no WSL distribution; they were not
changed or rerun for this isolated extension.
