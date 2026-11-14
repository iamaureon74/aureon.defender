# Aureon Defender

Signal interface, local security observations and direct downloads. **No app store is required for these downloads. Platform editions have different capabilities.**

## Downloads

| Device | Direct distribution | Scope |
|---|---|---|
| Windows 10/11 x64 | [Windows ZIP · 0.4.0](https://github.com/shep95/aureon.defender/releases/download/v0.4.1/aureon-defender-windows-x64-0.4.0.zip) | Windows engine and 15-tab Signal dashboard; unsigned publisher |
| Android 12+ | [Android APK · 0.4.1](https://github.com/shep95/aureon.defender/releases/download/v0.4.1/aureon-defender-android-0.4.1.apk) | Native local monitor; floating navigation; Android limits apply |
| iPhone / iPad | [Installable web edition](https://aureon-defender.vercel.app/) | Safari → Share → Add to Home Screen; local file/hash and report tools only |
| macOS Apple silicon / Intel | [Portable source preview](https://github.com/shep95/aureon.defender/releases/download/v0.4.1/aureon-defender-portable-source-0.4.1-preview.zip) | Source preview only; native builds blocked before execution by GitHub account billing lock |
| Linux x64 / ARM64 | [Portable source preview](https://github.com/shep95/aureon.defender/releases/download/v0.4.1/aureon-defender-portable-source-0.4.1-preview.zip) | Source preview only; native builds blocked before execution by GitHub account billing lock |
| Other laptops | [Source archive](https://github.com/shep95/aureon.defender/archive/refs/tags/v0.4.1.zip) | Python 3.12 portable companion where supported; no promise of every OS/device |

[Release notes and all downloads](https://github.com/shep95/aureon.defender/releases/tag/v0.4.1) · [SHA-256 checksums](https://github.com/shep95/aureon.defender/releases/download/v0.4.1/SHA256SUMS.txt)

Only assets actually attached to the release are downloadable builds. Mac/Linux packages are previews, not ports of the full Windows security engine. iOS web installation is **not** a native IPA or a 24/7 system antivirus.

## Windows

Extract the whole ZIP and retain `_internal` beside `aureon.defender.exe`. Open the executable for a portable session. Run `aureon.defender.exe install` to request the administrator-approved machine installation. Do not disable operating-system protections to install this software.

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

Open the [web edition](https://aureon-defender.vercel.app/) in Safari and choose **Add to Home Screen**. Once its offline cache is installed, the browser-local tools can operate offline. Downloads still need connectivity. Selected files/reports are processed locally, not uploaded. The app does not inspect other apps or run an unrestricted background monitor. [Web source](docs/index.html).

## Verification

- Windows: 101 tests ran successfully before packaging; one phone-connected test was skipped while disconnected. All 15 installed tabs were checked with live local state and no JavaScript errors. Isolated responsive checks covered 45 tab/width combinations.
- Android: 10 rule/file-check assertions and 19 Pixel 9 instrumentation assertions passed, including all five navigation tabs, header safe-area clearance, dock placement and local file/report flows.
- Portable preview: two local tests passed. Native CI and packaged-executable checks have not run because GitHub blocked hosted jobs before execution. No native Mac/Linux binary is claimed as tested or released.
- Web edition: local hash, import validation, report rendering and offline-cache tests are recorded in CI/local release checks.

There is no guarantee that all code works under every condition or that Windows/mobile features are identical. This code contains no country geofence. Network availability, OS rules, local requirements and hardware compatibility vary. The current interface is English with Unicode text support; it is not fully localized worldwide.

## Source, privacy and contributions

The original hardware project and pinned upstream references remain in [the legacy overview](docs/legacy-hardware-overview.md). The project catalog is research/selection metadata, not evidence that all listed projects are installed. Third-party code retains its own notices and licenses. This release does not invent a new blanket license grant over third-party components; see [notices](THIRD_PARTY.md).

No signing keys, passwords, runtime history, personal reports or API credentials belong in this repository. Report defects with platform/version and redacted diagnostics. Do not publish secrets in issues.
