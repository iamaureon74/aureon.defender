# Aureon Defender

Signal interface, local security observations and direct downloads. **No app store is required for these downloads. Platform editions have different capabilities.**

## Downloads

| Device | Direct distribution | Scope |
|---|---|---|
| Windows 10/11 x64 | [Windows Setup · 0.4.3](https://aureon-defender.vercel.app/api/download?platform=windows) | Windows engine and 15-tab Signal dashboard; unsigned publisher |
| Android 12+ | [Android APK · 0.4.3](https://github.com/shep95/aureon.defender/releases/download/v0.4.3/aureon-defender-android-0.4.3.apk) | Native local monitor; floating navigation; Android limits apply |
| iPhone / iPad | [Installable web edition](https://aureon-defender.vercel.app/) | Safari → Share → Add to Home Screen; local file/hash and report tools only |
| macOS Apple silicon / Intel | [Portable source preview](https://github.com/shep95/aureon.defender/releases/download/v0.4.3/aureon-defender-portable-source-0.4.3-preview.zip) | Source preview only; native builds blocked before execution by GitHub account billing lock |
| Linux x64 / ARM64 | [Portable source preview](https://github.com/shep95/aureon.defender/releases/download/v0.4.3/aureon-defender-portable-source-0.4.3-preview.zip) | Source preview only; native builds blocked before execution by GitHub account billing lock |
| Other laptops | [Source archive](https://github.com/shep95/aureon.defender/archive/refs/tags/v0.4.3.zip) | Python 3.12 portable companion where supported; no promise of every OS/device |

[Release notes and all downloads](https://github.com/shep95/aureon.defender/releases/tag/v0.4.3) · [SHA-256 checksums](https://github.com/shep95/aureon.defender/releases/download/v0.4.3/SHA256SUMS.txt)

Only assets actually attached to the release are downloadable builds. Mac/Linux packages are previews, not ports of the full Windows security engine. iOS web installation is **not** a native IPA or a 24/7 system antivirus.

## What is new in 0.4.3

The borderless landing header, themed scrollbars, original Signal footer and full ink/lime app artwork now share the same identity. Site-local download endpoints start the actual file transfer without opening a GitHub release page; GitHub still hosts the binary bytes. The header uses the full **aureon.defender** name at narrow widths.

[Devices & regions explorer](https://aureon-defender.vercel.app/compatibility.html) maps 249 ISO country/territory references × 16 device families. This is compatibility planning, not per-country certification, a count of sovereign states, or a global installed-device inventory. Country is not inferred from the hardware.

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

The app reviews selected granted-permission combinations, visible-package installs/removals/updates and history, screen-lock status, exposed USB host devices, and selected-file SHA-256 matches against operator-imported lists. It does not have Windows Defender, arbitrary process visibility, system-wide quarantine or building-wiring discovery. Permissions and unfamiliar devices are review prompts, not malware verdicts.

## macOS / Linux portable preview

The [portable companion](portable/) offers a loopback-only, token-protected browser dashboard, read-only supported OS posture checks, local resource observations and browser-local file/hash tools. It does not block processes or change firewall settings.

Run from source:

```sh
python -m pip install psutil==7.2.2
python -m portable.app
```

Close the process when finished. A Mac `.app` preview is not Apple Developer ID signed or notarized. The native build workflow targets Ubuntu 22.04 for the stated architectures, but no native Mac/Linux packages were produced: GitHub blocked every job before execution because the account is locked due to a billing issue. Use the Python source preview where supported. A Chromebook may need its Linux environment; no native ChromeOS system-security integration is claimed.

## iPhone / iPad web edition

Open the [web edition](https://aureon-defender.vercel.app/) in Safari and choose **Add to Home Screen**. Once its offline cache is installed, the browser-local tools can operate offline. Use Web tools; the landing page recommends downloads and checks public GitHub release notes while open. Downloads still need connectivity. Selected files/reports are processed locally, not uploaded. The app does not inspect other apps or run an unrestricted background monitor. [Web source](docs/index.html).

## Verification

- Windows: 111 tests passed on the expanded release, plus the final eight focused workflow tests (including one added after the full run). A packaged inert-file scan returned the expected review exit code 3. All 15 installed tabs were checked with live local state and no JavaScript errors. Isolated responsive checks covered 45 tab/width combinations.
- Android: 10 rule/file-check assertions and 35 Pixel 9 instrumentation assertions passed, including navigation, safe insets, dock choices, file/report flows and oriented metadata-clean image output.
- Portable preview: two local tests passed. Native CI and packaged-executable checks have not run because GitHub blocked hosted jobs before execution. No native Mac/Linux binary is claimed as tested or released.
- Web edition: local hash, import validation, report rendering and offline-cache tests are recorded in CI/local release checks.

There is no guarantee that all code works under every condition or that Windows/mobile features are identical. This code contains no country geofence. Network availability, OS rules, local requirements and hardware compatibility vary. The current interface is English with Unicode text support; it is not fully localized worldwide.

## Source, privacy and contributions

The original hardware project and pinned upstream references remain in [the legacy overview](docs/legacy-hardware-overview.md). The project catalog is research/selection metadata, not evidence that all listed projects are installed. Third-party code retains its own notices and licenses. This release does not invent a new blanket license grant over third-party components; see [notices](THIRD_PARTY.md).

No signing keys, passwords, runtime history, personal reports or API credentials belong in this repository. Report defects with platform/version and redacted diagnostics. Do not publish secrets in issues.

## noah.shield and optional support
The landing download card includes an optional Bitcoin support popout with an address-copy control; no wallet connection or payment is initiated. A separate noah.shield section offers the supplied original ZIP and manifest-adapted Chromium ZIP, with browser-specific instructions and limitations in [the installation guide](docs/BROWSER-INSTALLATION.md). The single-file Windows Setup source/build is in `windows/setup/`; its extraction-only verification does not substitute for a real machine installation test.
