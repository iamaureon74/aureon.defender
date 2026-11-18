# Windows and Android downloads

The site uses `/api/download?platform=windows` and
`/api/download?platform=android` to redirect to published GitHub release assets.
Installers are hosted on GitHub, not in the website deployment.

## GitHub builds

Push a version tag such as `v0.4.6`, or run **Windows and Android release**
with an existing tag. The tag must match `VERSION` in
`windows/aureon_defender/core.py` and `versionName` in
`android/defender/AndroidManifest.xml`. Increment Android `versionCode` for updates.

The workflow tests and packages Windows on Windows, builds Android with JDK 17
and Android SDK 36 on Linux, verifies the setup extraction and APK signature,
and publishes the EXE, ZIP, APK and `SHA256SUMS.txt` only after both jobs pass.
The Android rule tests run before signing. Windows is currently unsigned.

Android builds require these repository Actions secrets:

- `ANDROID_KEYSTORE_BASE64`: base64 of the existing release PKCS12 keystore.
- `ANDROID_KEYSTORE_PASSWORD`: its password.

Keep the same signing key between releases. Missing secrets fail the build;
the workflow does not silently generate a replacement signing identity.
Never commit a keystore or password to the repository.

## Hosted runner availability

On November 17, 2026, GitHub refused the repository's hosted jobs before
execution with: “The job was not started because your account is locked due
to a billing issue.” The account owner must resolve that GitHub account issue
before hosted builds can execute. A workflow change cannot resolve billing.

Version 0.4.6 was built and verified on a Windows laptop and uploaded to GitHub
releases. It is not represented as a successful GitHub-hosted build.
