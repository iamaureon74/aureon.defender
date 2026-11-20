# Aureon Defender

Signal interface, local security observations and direct downloads. **No app store is required for these downloads. Platform editions have different capabilities.**

## Downloads

| Device | Direct distribution | Scope |
|---|---|---|
| Windows 10/11 x64 | [Windows Setup · 0.4.6](https://github.com/shep95/aureon.defender/releases/download/v0.4.6/aureon-defender-windows-x64-setup-0.4.6.exe) | Windows engine and 15-tab Signal dashboard; unsigned publisher |
| Android 12+ | [Android APK · 0.4.6](https://github.com/shep95/aureon.defender/releases/download/v0.4.6/aureon-defender-android-0.4.6.apk) | Native local monitor; floating navigation; Android limits apply |
| iPhone / iPad | [Installable web edition](https://defender.asherin.com/) | Safari → Share → Add to Home Screen; local file/hash and report tools only |
| macOS Apple silicon / Intel | [Portable source preview](https://github.com/shep95/aureon.defender/releases/download/v0.4.3/aureon-defender-portable-source-0.4.3-preview.zip) | Source preview only; native builds blocked before execution by GitHub account billing lock |
| Linux x64 / ARM64 | [Portable source preview](https://github.com/shep95/aureon.defender/releases/download/v0.4.3/aureon-defender-portable-source-0.4.3-preview.zip) | Source preview only; native builds blocked before execution by GitHub account billing lock |
| Other laptops | [Source archive](https://github.com/shep95/aureon.defender/archive/refs/tags/v0.4.3.zip) | Python 3.12 portable companion where supported; no promise of every OS/device |

[Release notes and all downloads](https://github.com/shep95/aureon.defender/releases/tag/v0.4.3) · [SHA-256 checksums](https://github.com/shep95/aureon.defender/releases/download/v0.4.3/SHA256SUMS.txt)

Only assets actually attached to the release are downloadable builds. Mac/Linux packages are previews, not ports of the full Windows security engine. iOS web installation is **not** a native IPA or a 24/7 system antivirus.

## What is new in 0.4.9 (source; installers on the release page are still 0.4.6 until rebuilt)

- **Silent memory, powered by [aureon.fold-memory](https://github.com/iamaureon74/aureon.fold-memory)**: Documents, Desktop and Pictures are kept on the machine itself with every earlier version, identical bytes stored once and every file checked against its SHA-256 before it comes back. It starts at login (Windows agent, mac/linux companion), runs hourly on the hardware budget, skips its turn on battery below 40% or when under 10% of the disk is free, and stays under 15% of the free disk (50 GB max) by keeping fewer old versions. Nothing leaves the device.
- **Ransomware undo**: when the tripwire fires, every watched file that was overwritten with encrypted-looking bytes, or renamed and encrypted, since just before the alarm is put back from the last trustworthy version, and the encrypted copy is deleted. Normal edits in that window are left alone. Folding pauses while this happens so encrypted junk is not stored.
- **Put any version back**: `aureon.defender memory versions <file>` and `aureon.defender memory restore <file> --version 2` on Windows; `python -m portable.app memory ...` on mac/linux. `memory dupes` lists the copies still taking space on your disk (reported, never deleted).
- Android and the web edition do not run Python, so they do not have memory yet.

## 0.4.8

- **Vulnerable-driver protection**: the LOLDrivers list (loldrivers.io, public, no key) now feeds the same reputation database as MalwareBazaar. A known-vulnerable driver dropped anywhere is removed like any other threat. One the OS has registered for a device is checked twice a day and reported with the fix (vendor update, Windows' blocklist), never deleted, because the hardware needs it.
- **Mac / Linux autostart guard**: user autostart entries (`~/.config/autostart`, systemd user units, macOS LaunchAgents) are read every minute. A new or changed entry that launches a flagged program, or pipes a download into a shell, is removed together with that program. System programs are never touched.
- **Android impostor installers**: an APK on shared storage that claims an installed app's package name but carries a different signing certificate (tampered or fake copy) is deleted.
- **Fixes**: the Windows leaks section could crash the dashboard when its data was missing; it is now guarded. The Windows-only autopilot paths (autostart removal, ransomware stop, driver audit) now have tests.

## 0.4.7 autopilot

Every edition now runs on autopilot: it finds something, removes it, and says why in one line. Nothing to approve.

- **Hardware guard** (`windows/aureon_defender/hwguard.py`, mirrored in Android `ShieldRules`): before anything is removed it checks whether a device, driver or the boot chain needs it. Drivers the OS registered (Windows service registry, any folder), `System32\drivers`, DriverStore, EFI/boot files, `/lib/modules`, `/lib/firmware`, `/boot`, macOS `/System` and `/Library/Extensions`, Android `Android/` and firmware folders are never touched. A stray `.sys` dropped in Downloads is not "needed" (bring-your-own-vulnerable-driver), so it stays removable.
- **Adapts to any machine**: a fixed formula over threads, RAM, battery and disk type picks light / balanced / full. Small or battery machines sweep less often; strong ones sweep more. Real-time protection keeps the same pace everywhere. No AI, no learned model: the same hardware always gets the same budget.
- **Windows**: suspicious unsigned files are now removed too (encrypted vault, deleted after the trash period); confirmed malware is still wiped at once. A flagged program that sets itself to autostart loses both the program and the entry. The ransomware tripwire now stops and removes the unsigned writer by default. Microsoft's vulnerable-driver blocklist joins "Protect this PC". Dashboard: animated orbit, autopilot panel, and each section now fails on its own instead of blanking the page.
- **Mac / Linux companion**: scans Downloads and Desktop (plus one sweep of what is already there) and removes disguised ELF/Mach-O programs, rogue `.desktop` launchers, shell droppers, reverse shells and miners. Redesigned dashboard.
- **Android**: with one "all files access" switch, shared storage is checked every 15 minutes and after installs; disguised APKs, double extensions, programs posing as documents and blocklisted hashes are deleted with one quiet notification. Without the switch it guards folders you pick. Android still does not allow silent uninstalls of other apps.
- **Web edition**: redesigned tools page.

## What is new in 0.4.3

The borderless landing header, themed scrollbars, original Signal footer and full ink/lime app artwork now share the same identity. Site-local download endpoints start the actual file transfer without opening a GitHub release page; GitHub still hosts the binary bytes. The header uses the full **aureon.defender** name at narrow widths.

[Devices & regions explorer](https://defender.asherin.com/compatibility.html) maps 249 ISO country/territory references × 16 device families. This is compatibility planning, not per-country certification, a count of sovereign states, or a global installed-device inventory. Country is not inferred from the hardware.

Android inventory adapts to exposed APIs: SoC, GPU driver strings, RAM/storage, display, thermal severity, battery, security patch and visible app names/versions. Windows provides existing CPU/GPU/device inventory plus available OS/driver thermal/fan/NVIDIA readings. Unsupported sensors remain unavailable.

[Hardware-layer integration plan](docs/HARDWARE-INTEGRATION-PLAN.md) labels OS-owned, planned, unsupported and existing functions. No firmware flashing, disk-encryption enrollment, kernel driver or key wipe is silently introduced. A universal all-fingerprint-removal claim would be false.

## Earlier 0.4.2 workflow additions

- Device-aware landing page, three visual directions, live GitHub release notes and offline fallback.
- Windows read-only full scan, cancellation/findings, reviewed quarantine and a previewed Fix all for reversible per-user settings.
- Metadata cleanup creates separate copies and reports unsupported/error cases; does not promise all fingerprints removed.
- Android granted-folder hash checks and JPEG/PNG clean-copy export, preserving orientation and originals.
- Battery precision/source definitions and observed upload/download Mbps; external speed test is explicit and transfers data.
- Full-artwork adaptive Android and multi-size Windows/web icons; dock placements, app pointer styles and appearance choices.
- Optional separately installed ClamAV adapter (disabled by default) and expanded Pi tool discovery. Other researched tools are not silently installed.

[Research, algorithms, creative options and exact platform matrix](docs/DEFENSIVE-INTEGRATIONS-AND-CUSTOMIZATION.md).

## Windows

Download Setup and open the EXE. It verifies/unpacks the bundled app automatically and starts the existing machine installer with the normal administrator prompt. The browser cannot launch a downloaded EXE or approve OS prompts for you. The portable ZIP remains an alternative: extract it fully and retain `_internal` beside `aureon.defender.exe`. Do not disable operating-system protections to install this software.

Existing functions include Defender/YARA/reputation/heuristic file checks, selected-folder monitoring, quarantine, Windows privacy and configuration observations, device history, explicit controls and an authenticated local dashboard. Some functions need administrator access, extra software, an API key, or hardware. Three abuse.ch feeds require a key; Feodo does not. Check the actual module state and evidence.

## Android

Download the APK directly, verify its hash, and choose whether to permit installation from your download source in Android settings. The package is `org.aureon.defender`. Tap **Start monitoring**. Android displays a quiet foreground-service notification and can defer/stop work. Force-stop requires reopening; uninterrupted 24/7 execution is not guaranteed.

Turn on **all files access** once (the overview offers the switch) and the app checks shared storage every 15 minutes, after app installs and at start-up. Disguised apps, double extensions, programs posing as documents, impostor installers and blocklisted hashes are deleted with one quiet notification; `Android/`, hidden and firmware folders are never touched. Without that switch it guards folders you pick. It also reviews granted-permission combinations, package installs/removals/updates, screen lock and USB host devices. Android does not let an ordinary app uninstall other apps silently, see arbitrary processes or quarantine other apps' private files, so those stay review prompts.

## macOS / Linux portable preview

The [portable companion](portable/) offers a loopback-only, token-protected browser dashboard. While it is open it scans Downloads and Desktop (plus one sweep of what is already there) and your login autostart entries, and removes what it finds unless the hardware needs it: disguised ELF/Mach-O programs, rogue launchers, shell droppers, reverse shells, miners and keychain theft. It also runs read-only OS posture checks and browser-local file/hash tools. It runs as you, not root, so it does not block processes, change firewall settings or touch system folders.

Run from source:

```sh
python -m pip install psutil==7.2.2
python -m portable.app
```

Close the process when finished. A Mac `.app` preview is not Apple Developer ID signed or notarized. The native build workflow targets Ubuntu 22.04 for the stated architectures, but no native Mac/Linux packages were produced: GitHub blocked every job before execution because the account is locked due to a billing issue. Use the Python source preview where supported. A Chromebook may need its Linux environment; no native ChromeOS system-security integration is claimed.

## iPhone / iPad web edition

Open the [web edition](https://defender.asherin.com/) in Safari and choose **Add to Home Screen**. Once its offline cache is installed, the browser-local tools can operate offline. Use Web tools; the landing page recommends downloads and checks public GitHub release notes while open. Downloads still need connectivity. Selected files/reports are processed locally, not uploaded. The app does not inspect other apps or run an unrestricted background monitor. [Web source](docs/index.html).

## Verification

- 0.4.9 source (Linux container): 7 memory tests pass, covering folding, unchanged-file skips, duplicates, the size cap, battery and disk skips, and ransomware rollback (in-place encryption, rename-and-encrypt, an encrypted version already folded before the alarm, a normal edit left alone, and the agent hook). Both dashboards were screenshot-checked with the memory panel.
- 0.4.8 source (Linux container): 28 new autopilot tests (hardware budget, hardware guard, removal policy, engine reactions, autostart removal, ransomware stop, driver audit) and the extended feed test (LOLDrivers parsing) pass; the remaining Windows suite failures on Linux are Windows-only tests that also failed before these changes. Portable: 5 tests pass, including live removal of planted threats and bad autostart entries. Android: sources compile against the Android 14 framework and 22 rule/file-check assertions pass. The Windows and portable dashboards and the web tools page were screenshot-checked at desktop and phone widths.
- Not yet run for 0.4.8: Windows installer build and install, Android APK build and device instrumentation, a live LOLDrivers download (the build container's proxy blocks loldrivers.io; the parser follows its documented `KnownVulnerableSamples` format).
- 0.4.6 release: Windows 111 tests plus eight workflow tests, 15 installed tabs checked with no JavaScript errors; Android 10 rule assertions and 35 Pixel 9 instrumentation assertions.

There is no guarantee that all code works under every condition or that Windows/mobile features are identical. This code contains no country geofence. Network availability, OS rules, local requirements and hardware compatibility vary. The current interface is English with Unicode text support; it is not fully localized worldwide.

## Source, privacy and contributions

The original hardware project and pinned upstream references remain in [the legacy overview](docs/legacy-hardware-overview.md). The project catalog is research/selection metadata, not evidence that all listed projects are installed. Third-party code retains its own notices and licenses. This release does not invent a new blanket license grant over third-party components; see [notices](THIRD_PARTY.md).

No signing keys, passwords, runtime history, personal reports or API credentials belong in this repository. Report defects with platform/version and redacted diagnostics. Do not publish secrets in issues.

## noah.shield and optional support
The landing download card includes an optional Bitcoin support popout with an address-copy control; no wallet connection or payment is initiated. A separate noah.shield section offers the supplied original ZIP and manifest-adapted Chromium ZIP, with browser-specific instructions and limitations in [the installation guide](docs/BROWSER-INSTALLATION.md). The single-file Windows Setup source/build is in `windows/setup/`; its extraction-only verification does not substitute for a real machine installation test.
