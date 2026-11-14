# Third-party components and distribution scope

Upstream submodules keep their own licenses and remain references rather than automatically downloaded software. Their names, source URLs and pinned paths are in `.gitmodules`, `stack.json` and the catalog. Bundled browser-companion source remains under `windows/aureon_defender/noah_shield`; retain its existing notices, including vendored library notices.

The Windows distribution bundles CPython, PyInstaller runtime components, psutil, Pillow, yara-python/libyara and pywin32 dependencies. Their upstream licenses/redistribution notices still apply. PyInstaller's bootloader distribution exception does not change licenses of the application or other dependencies. Portable packages use CPython, PyInstaller and psutil.

This repository previously had no top-level project-wide license file. Publication here does not silently relicense all inherited or third-party code. The project owner must resolve any desired broader source-licensing grant separately. No patent license, certification, Apple approval, hardware attestation or security guarantee is conferred by this release.
