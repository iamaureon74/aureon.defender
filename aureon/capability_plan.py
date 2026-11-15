"""Cross-device integration contract. These records describe availability, never active protection."""
import platform

ITEMS = [
 ('ports','USB / storage / Bluetooth governance','Existing Windows control actions and Linux USBGuard discovery; Android observes exposed USB host devices.','Privileged device-management APIs, recovery input, explicit policy and OS-specific enforcement tests.'),
 ('hid','Behavioral BadUSB review','Existing new-keyboard guard/tripwire observations; not cryptographic device authentication.','Driver-level attribution and false-positive tests for accessibility tools/macros; never infer malicious intent from typing rate alone.'),
 ('cable-auth','USB-C / Thunderbolt certificate authentication','Not implemented.','Compatible controller/cable/dock firmware, OS/vendor API and a certificate trust policy. Cannot add authentication to arbitrary cables in software.'),
 ('disk','BitLocker / FileVault / hardware-bound storage','OS-owned feature; Aureon is not a replacement disk-encryption engine.','Read supported OS state; recovery-key provisioning and operator-approved enrollment before configuration changes.'),
 ('tpm','TPM / Secure Enclave / Titan / Knox','Hardware-backed roots of trust are not interchangeable app APIs.','Platform-specific attestation, certificate-chain verification, revocation, nonce freshness and a relying-party trust policy.'),
 ('boot','Secure / measured boot and revocation','No universal raw-firmware validation is claimed.','Supported OS measurements, TPM logs where authorized, OEM-specific firmware and current vendor advisories.'),
 ('dma','IOMMU / kernel DMA isolation','Not enforced by this application.','Compatible hardware, firmware and OS isolation configuration; supported read-only status before changes.'),
 ('kernel','VBS / HVCI / CET / PAC and driver controls','Not a custom kernel security driver.','OS/CPU support, driver compatibility, signed components and controlled validation. Hardware feature names alone do not establish active enforcement.'),
 ('memory','Full-memory encryption / confidential hardware','Not implemented or independently attested.','CPU/SoC and firmware support; protected interfaces are not available uniformly to ordinary apps.'),
 ('firmware','Component firmware inventory / inspection','Research and OS inventory only; no universal firmware dump/implant detector.','Per-component access, signed vendor inventories, flash-layout knowledge and a safe parser corpus. No generic implant verdict from a version string.'),
 ('patch','Cross-vendor firmware patching','Not implemented; no BIOS or peripheral firmware writes performed.','Exact model matching, signed OEM/LVFS package, AC power, recovery keys, rollback and native maintenance approval.'),
 ('thermal','Thermal / voltage / fan / power anomalies','Reported battery/network/resource observations exist; missing sensors remain unavailable.','OEM sensor APIs and calibrated per-device baselines. Heat/power anomalies have many benign causes and are not proof of an implant.'),
 ('wear','Battery charge caps / SSD wear','Charge percentage is shown with source precision; no universal charge-limit control.','OEM charge-controller support and SMART/NVMe access; wear leveling belongs to drive firmware.'),
 ('tamper','Chassis intrusion / physical tamper / key zeroization','Not implemented. No wipe/zeroization action is added.','Physical sensor/firmware integration and independently approved recovery policy. App telemetry cannot prove a case was never opened.'),
 ('hbom','Hardware bill of materials / counterfeit review','Inventory identifiers are observations, not authenticity proofs.','Manufacturer-signed provenance/attestation and supply-chain evidence; serial/MAC fingerprints are spoofable.'),
 ('radio','BLE / NFC / AirDrop / Wi-Fi Direct profiles','Existing Windows observations/limited controls; no universal radio-profile enforcement.','OS enterprise/device-owner permissions, supported radio APIs and loss-of-connectivity recovery.'),
 ('iot','Agentless IoT / OT visibility','Network inventory/report support, not every-device firmware protection.','Authorized passive observation point, privacy-minimized logs and validated device-specific parsers; no invasive medical/OT tests.'),
 ('media','Download media metadata layers','Windows supported-field copies and automatic-download opt-in; Android selected JPEG/PNG clean PNG copies.','No guarantee for all file types/fingerprints, watermarks, steganography or prior shared copies. Originals and visible format limitations are retained.'),
]

def plan():
    return {'host':platform.system(),'kind':'capability_and_integration_plan','active_protection_claim':False,
            'items':[{'id':key,'name':name,'current':current,'requires':requires} for key,name,current,requires in ITEMS]}
