# Third-party components and distribution scope

Upstream submodules keep their own licenses and remain references rather than automatically downloaded software. Their names, source URLs and pinned paths are in `.gitmodules`, `stack.json` and the catalog. Bundled browser-companion source remains under `windows/aureon_defender/noah_shield`; retain its existing notices, including vendored library notices.

The Windows distribution bundles CPython, PyInstaller runtime components, psutil, Pillow, yara-python/libyara and pywin32 dependencies. Their upstream licenses/redistribution notices still apply. PyInstaller's bootloader distribution exception does not change licenses of the application or other dependencies. Portable packages use CPython, PyInstaller and psutil.

This repository previously had no top-level project-wide license file. Publication here does not silently relicense all inherited or third-party code. The project owner must resolve any desired broader source-licensing grant separately. No patent license, certification, Apple approval, hardware attestation or security guarantee is conferred by this release.

## Country/territory compatibility reference
The generated country/territory names and codes use pycountry 26.2.16 / Debian iso-codes. Source: https://pypi.org/project/pycountry/26.2.16/ . Retained source license: docs/data-licenses/pycountry-LICENSE.txt. This is a reference dataset, not a geofence or per-country availability certification. The pycountry runtime package is not bundled into the app binaries.

## aureon.fold-memory (same author)

`windows/aureon_defender/fold_memory.py` is `fold_memory.py` 2.1.0 from https://github.com/iamaureon74/aureon.fold-memory at commit `12e359cc162d254218d3904b9d0b8983f157b4de` (SHA-256 `e35bb322a9b42b48f5e9ea8a59079bf22bbd158b21d17e97261ffb0ef46028d2`), copied unchanged. Its terms are the author's own ("all rights reserved by the author unless they say otherwise"). To update it, copy the newer file over and run `windows/tests/test_memory_049.py`.
