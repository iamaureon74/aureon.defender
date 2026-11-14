# Aureon expansion review — 14 November 2026

This review separates implemented adapters, existing integrations, discovery and future work. A tool listed here is not automatically installed or licensed for redistribution as part of Aureon. Raspberry Pi hardware was not connected during this work; hardware sizing and enforcement need deployment tests.

## What this update implements

Windows: read-only full local-drive scanning with progress/cancel, bounded findings, selected quarantine with a fresh hash check, reversible per-user bulk privacy fixes, original-preserving metadata copies, reported battery precision, observed network throughput, dock placement and app cursor styles. Optional ClamAV command-line scanning is disabled by default and requires a separately installed binary and signatures. It never passes ClamAV deletion flags.

Android: a user-granted folder hash scan, JPEG/PNG decoded-pixel clean-copy tool, battery definitions, observed aggregate network rates, bottom/side/automatic navigation, pointer styles for an attached mouse within Aureon, larger dock labels, Copper/Signal/Frost appearance and reduced motion. System-wide file access, Windows Defender and registry fixes are not available to this ordinary sandboxed APK.

Pi node reporting: additional local tool/service discovery. Discovery is not an installed engine, a verified packet path, ruleset validation or enforcement.

## Defensive components evaluated

| Component and primary source | Mechanism / useful integration | Current Aureon status | Constraints and next validation |
|---|---|---|---|
| [Microsoft Defender](https://learn.microsoft.com/en-us/defender-endpoint/overview-attack-surface-reduction) | OS antivirus, behavior/attack-surface controls, protected folders, device controls | Existing Windows custom scan integration; full-scan workflow adds review | Proprietary OS capabilities are not copied to Android/iOS. Read actual supported settings, tamper protection and results. ASR changes need audit-first trials, exclusions and rollback. |
| [ClamAV](https://docs.clamav.net/manual/Usage/Scanning.html) | Signature/container scanning with local signatures | New optional `clamscan` adapter; missing/error state distinct from no match | GPL family; binary/signature distribution notices must be reviewed for the exact package. Separate install; signatures need updating. On-access prevention is a separate Linux deployment and can affect performance. Mocked adapter tests do not establish live detection efficacy. |
| [Suricata](https://docs.suricata.io/en/latest/ips/setting-up-ipsinline-for-linux.html) | Flow-aware signatures and protocol inspection; EVE event ingestion | Existing Pi service discovery; event ingestion/enforcement remains future work | Inline IPS needs a real bridge/routing path and interfaces. Encryption, packet loss and offload affect visibility. Prove a benign test flow reaches the sensor before claiming protection. |
| [Zeek](https://zeek.org/about/) | Stateful protocol analysis and semantic network logs | Binary discovery only | BSD-licensed. Requires a network observation point and storage/retention plan. A Pi on ordinary switched Wi-Fi cannot see every client's traffic. No network-owner attribution from a MAC/name. |
| [CrowdSec](https://docs.crowdsec.net/u/troubleshooting/remediation_components/) | Log scenarios create decisions; separate remediation component enforces | Existing node service/tool discovery only | A running engine does not imply blocking. Verify the relevant bouncer, acquisition sources, decision TTL and rollback. Review exact component licenses and community-data behavior before deployment. |
| [Pi-hole](https://docs.pi-hole.net/main/prerequesites/) | DNS-domain filtering shared by clients using the resolver | Added tool/service discovery | Requires DNS configuration, available port 53, stable addressing and redundancy. DNS-over-HTTPS, other resolvers and shared domains limit coverage. Not malware removal, per-file scanning or an endpoint firewall. |
| [AdGuard Home](https://github.com/AdguardTeam/AdGuardHome) | Alternative network DNS filtering with ARM builds | Researched; not installed or connected | GPL-3.0. Choose one DNS listener per address/port, rather than blindly stacking DNS servers. Configure privacy/log retention and explicit client routing. |
| [OpenWrt SQM / CAKE](https://openwrt.org/docs/guide-user/network/traffic-shaping/sqm) | Active queue management and flow fairness reduce queueing latency | Research candidate; existing laptop Wi-Fi preference is not router QoS | Must control the router/gateway and shape below the real bottleneck rate. CPU/interface capacity matters. It cannot force someone else's AP to retain a client or create bandwidth. Test loaded latency as well as throughput. |
| [USBGuard](https://github.com/USBGuard/usbguard) | Explicit device authorization policy and interface restrictions | Existing Linux service discovery; no policy changes applied | GPL-2.0-or-later. Stage allow rules and recovery input before enforcement so you do not lock out the keyboard. Descriptors/fingerprints can be spoofed. |
| [osquery](https://osquery.io/) | SQL-shaped local inventory, scheduled queries and event tables | New binary availability reporting only | Apache license reported by upstream. Specify reviewed read-only queries, costs, privacy and platform table availability. Finding a binary is not a connected fleet agent. |
| [Wazuh](https://documentation.wazuh.com/current/quickstart.html) | Agent inventory, file-integrity monitoring, configuration assessment and correlated events | Researched; no manager or agent installed | Check current supported architectures and sizing. A complete server stack is not assumed suitable for every small Pi. Agents do not bypass Android/iOS sandboxing. Evaluate manager storage/retention, enrollment and secure update path. |
| [Lynis](https://cisofy.com/legal/) | Linux/Unix configuration audits and hardening recommendations | Existing Pi executable discovery only | Community GPLv3; plugins may differ. Audit output is advice, not proof of compromise. Map supported changes to reversible, reviewed actions. |
| [ExifTool](https://exiftool.org/) | Broad format-aware metadata reading/writing | Availability reporting only; not invoked or bundled | Upstream explicitly does not guarantee complete metadata removal. PDF updates can be reversible; prefer format-aware rewrite and verify the resulting structure. Exact version/license and unsupported tags must be checked before adding execution. |
| [Detect It Easy](https://github.com/horsicq/Detect-It-Easy/blob/master/README.md) | File/container identification, compiler/packer signals | Research candidate only | MIT upstream license. A packer/unknown format is an inspection signal, not a malware verdict. Needs bounded parsing and corpus tests before integration. |

## Algorithm choices and improvements

1. **Streamed SHA-256 and exact sets:** use deterministic file identity for blocklist lookup. Android imports at most 10,000 operator-supplied entries. Hash provenance is separate from matching; benign files can be in a bad list.
2. **Reviewed remediation bound to identity:** the full scan stores the file hash and rechecks it before quarantine. Permission failures or changed files are reported. This reduces stale-result mistakes; it does not eliminate every filesystem race or privileged attacker.
3. **Bounded traversal:** skip symbolic links/junctions, expose unreadable-file counts, limit retained findings, permit cancellation between engine calls. Do not display a fabricated percent when the total file count is unknown.
4. **Byte-counter deltas / elapsed time:** Mbps = bytes × 8 / seconds / 1,000,000. Negative counter/reset deltas do not become traffic. Link rate, observed traffic, throughput-test result and internet capacity are different measurements.
5. **Reported precision:** a battery capacity integer is not a hidden two-decimal estimate. [Android documents capacity as an integer percentage](https://developer.android.com/reference/android/os/BatteryManager). [psutil documents OS battery/network counters](https://psutil.readthedocs.io/stable/). Expose source, unavailable values and estimation limits.
6. **Optional EWMA traffic baselines:** a future local baseline could flag an unusual rate relative to the device's own history. Require minimum samples and hysteresis; an unusual rate alone does not establish exfiltration.
7. **Finite-state USB baselines:** compare explicitly trusted inventory snapshots and distinguish missing reads from removals. Device hashes describe observed identifiers, not a person's identity or intent.
8. **Queue discipline rather than “Wi-Fi boosting”:** CAKE/fq_codel target congestion at a gateway. Benchmark loaded latency, fairness and CPU cost; do not infer control of an AP from client access.
9. **Detection provenance:** keep signature, hash, heuristic and OS-engine results separate. Do not turn an aggregate heuristic score into a guarantee. Evaluate precision/recall with benign and approved test corpora before changing auto-remediation thresholds.
10. **Format-specific sanitization:** document selected fields and residuals; preserve originals; reject unsupported/malformed/oversized inputs visibly. Do not claim all metadata, steganography, watermarks, perceptual fingerprints, filesystem records or already shared copies are removed.

## Creative hardware and interface system

**Implemented in this update:** app-local lime-outline / precision / system cursors; Android external-mouse pointer styles; Windows left/right/bottom navigation; Android bottom/left/right/automatic tablet rail with narrow/short-window fallback; larger Android labels; dark/light/warm Android themes; reduced motion; full-artwork adaptive launcher icon with a dark background; multi-resolution Windows icon; matching web icons. These are Aureon controls, not replacement navigation for every other app.

Primary design references: [Microsoft mouse interactions](https://learn.microsoft.com/en-us/windows/apps/develop/input/mouse-interactions), [Apple pointing devices](https://developer.apple.com/design/human-interface-guidelines/pointing-devices), and [Material adaptive rail behavior](https://api.flutter.dev/flutter/material/NavigationRail-class.html). Preserve platform focus, input and accessibility conventions. Pointer customization on iPhone/web depends on browser/OS support; never advertise a global iOS cursor replacement.

**Next prototypes, not released features:**

| Family | Creative direction | Validation before shipping |
|---|---|---|
| Pointer studio | Large high-contrast arrow, fine crosshair, subtle focus ring, left-handed arrow, hardware-mouse preset | Correct hotspot, sharp 1×/2× rendering, clear text insertion cursor, no trails that obscure evidence |
| Dock studio | Compact capsule, side rail, thumb-reachable controls, tablet expanded labels, keyboard shortcuts | No content under the dock; reachable settings to undo changes; landscape and 200% text tests |
| Ambient themes | Copper dusk, forest, slate, paper, system-following schedule | Contrast and OS motion settings; local preferences; no distracting alerts or faux protection state |
| Focus modes | Quiet monitoring, audit workspace, presentation mode, travel view | No hidden disabling of detection; show effective settings and changes clearly |
| Hardware cards | Mouse DPI/polling where the device/API exposes it, keyboard battery, headset levels, storage health | Never infer unsupported sensor values. Vendor SDK permissions and licenses differ; make unavailable states useful |
| Battery-aware effects | Reduce ornamental motion on low battery; optional charging visualization | Hysteresis and user override, no fake energy-savings figures; never change security coverage silently |
| Haptics and touch | Optional confirmation haptic, larger targets, left/right thumb preference, stylus-friendly inputs | Respect device/OS support and accessibility settings; no mandatory vibration or gesture-only actions |
| Shared view | Common finding/report schema with platform capability labels; trusted Pi report import | Authenticated device enrollment, replay protection, explicit permissions and secure transport before remote controls |

## Capability parity contract

| Workflow | Windows | Android | iPhone web | Pi / desktop source preview |
|---|---|---|---|---|
| File checks | Local multi-engine scan; optional separately installed ClamAV | Selected file/folder SHA-256 versus imported list | Selected-file SHA-256 versus imported list | Browser-selected hash tools; no shared full Windows engine |
| Whole-device scan | Accessible fixed-drive files, visible bounds and errors | Not available to this APK; granted folder only | Not available | Not a released native antivirus |
| Metadata cleanup | Selected format fields; copy-first; partial PDF/video coverage | JPEG/PNG pixel-derived PNG copy | No metadata cleaner in this release | Not integrated |
| Fix all | Supported reversible per-user privacy settings; admin/manual items separate | OS settings require user interaction; no registry equivalent | Not available | Not integrated |
| Quarantine | Reviewed selected findings; restore/delete through Quarantine | File-manager review; no silent deletion | Not available | Not integrated |
| Battery/network | OS precision and observed traffic | OS precision and observed traffic | Browser cannot provide reliable full-device equivalent | Depends on supported host APIs |
| Customization | App dock/cursor/themes | App dock/mouse/theme/labels | Responsive web interface | Limited web dashboard |

The shared goal is a consistent workflow and honest evidence, not identical privileges. Kernel drivers, EDR, secure boot, protected storage, VPN inspection and enterprise device management are separate engineering efforts. This release does not replicate every commercial defender, issue patent clearance, or guarantee protection on every device/country.
