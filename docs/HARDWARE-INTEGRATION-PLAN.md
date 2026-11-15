# Hardware-layer integration plan

The two supplied hardware-protection notes were reviewed as requested scope and research leads, not as verified vendor specifications. The common machine-readable contract is `aureon/capability_plan.py`, exposed as a read-only integration plan in the Windows Hardware page. It labels planned/OS-owned/unavailable items explicitly; it is not evidence that these protections are installed.

| Requested family | Implemented in this update / existing work | Next integration prerequisite |
|---|---|---|
| USB/storage/BadUSB/Bluetooth | Existing Windows actions, keyboard guard, device history; Pi service discovery; Android exposed USB inventory | Device-specific policy, driver attribution, recovery input and false-positive evaluation. VID/PID/serial alone is spoofable. |
| Cable/dock cryptographic authentication | Plan only | Controller/firmware support and authorized vendor/OS APIs. Arbitrary cables cannot gain certificates through an app. |
| TPM/enclaves/attestation | Plan only; preserve OS ownership | Challenge/nonce, trusted root chain, revocation and relying-party validation; never call a local unsigned report hardware attestation. |
| Full-disk encryption / SEDs | OS-owned; no automatic encryption changes | Correct platform APIs, recovery-key handling and approved enrollment. An app cannot grant a phone's Secure Enclave policy to Windows. |
| Secure boot / measured boot / DBX | Read-only integration target | OS state/logs, OEM firmware support and current advisories. Secure Boot is not arbitrary peripheral-firmware inspection. |
| IOMMU / DMA / VBS / HVCI / CET / PAC | Plan only | Compatible hardware/firmware/OS, signed drivers and compatibility testing. No bypassing kernel isolation to implement “parity.” |
| SPI/UEFI/NIC/SSD/GPU firmware inspection | Plan only | Exact supported hardware, privilege boundary, safe acquisition/parser tests, signed inventories. No universal rootkit detector shipped. |
| Firmware update orchestration | Plan only; no flash writes performed | Signed OEM/LVFS package, model match, power, recovery keys and rollback. Never blind-flash or automatically suspend encryption. |
| Thermal/voltage/fan/wattage | Battery and resource observations implemented; unsupported readings absent | OEM sensor API, units, calibration and baseline. Universal 100–105°C cutoffs are not assumed. Resource anomalies have benign explanations. |
| Battery charge cap / drive wear | Battery charge and precision implemented; no generic charge-cap control | Charge-controller API and SMART/NVMe support. SSD wear leveling is firmware behavior, not an antivirus algorithm. |
| Chassis/tamper/zeroization | Plan only; no wipe behavior | Actual physical sensor/tamper mesh and explicit recovery policy. No inference of an unopened chassis from software alone. |
| HBOM / counterfeit detection | Inventory observations only | Signed manufacturing provenance/attestation; serials and descriptors are not authenticity guarantees. |
| BLE/NFC/AirDrop/Wi-Fi Direct profiles | Limited OS observations and existing Windows controls | Enterprise/device-owner APIs and tested policy rollback; sandboxed apps cannot uniformly control every radio/profile. |
| Agentless IoT/OT visibility | Existing reports/network inventory | Authorized passive vantage point and device-specific validation; no active tests on medical/industrial equipment. |
| Media metadata/fingerprints | New selected-file and Downloads controls; copy-first supported formats; automatic new-download opt-in | Structural metadata needed to decode a file remains; visible names/watermarks, hidden payloads and prior copies are not universally removable. Android/iOS cannot silently intercept every download. |

## Correcting assumptions in the supplied notes

“Seven layers” is a useful organizing proposal, not a universal hardware standard. Thermal limits differ by component. A MAT table does not by itself prove all SMM isolation. “Unforgeable” identifiers and anomaly-based implant claims require a threat model and evidence. Hardware-backed disk encryption, Secure Boot, DMA protection, attestation and peripheral policy are separate mechanisms; none proves all the others.

Vendor marketing capabilities and licensing are not source code available for copying. A cross-platform product can share an event schema, UI and policy intent while using different supported enforcement mechanisms. This ordinary Android APK and iOS web edition cannot have identical Windows kernel privileges.

Primary references reviewed: [Microsoft kernel DMA requirements](https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/oem-kernel-dma-protection), [Secured-core Windows requirements](https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/oem-highly-secure-11), [Android hardware key/ID attestation](https://source.android.com/docs/security/features/keystore/attestation), [Apple FileVault and Secure Enclave storage](https://support.apple.com/guide/security/volume-encryption-with-filevault-sec4c6dc1b6e/1/web/1), and the separately linked defensive-integration review.

No target Pi, Mac or iPhone hardware was available to validate these deeper integrations. Native Mac/Linux packaging remains blocked by GitHub account billing. The Windows installer launch was rejected by automatic approval review, so current laptop installation was not updated automatically.
