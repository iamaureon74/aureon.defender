# noah.shield direct browser installation

The supplied original ZIP is preserved unchanged. The Chromium ZIP changes only the manifest/background declaration for consumer Manifest V3 compatibility and removes browser-generated `_metadata` cache. It retains the supplied source and third-party notice. It removes the Firefox background script list/browser settings and the `webRequestBlocking` permission unavailable to ordinary Chromium MV3 installations; it does not manufacture that privileged capability.

## Chrome, Edge and Brave desktop

1. Download the Chromium ZIP and extract it into a folder you will retain.
2. Type `chrome://extensions`, `edge://extensions` or `brave://extensions` into that browser's address bar.
3. Enable Developer mode.
4. Choose **Load unpacked** and select the extracted folder containing `manifest.json`.
5. Review the extension and requested access. Pin its icon if wanted, then configure settings. Some features require external services, additional configuration or a native host.

Chromium 137+ is required by the supplied manifest. Managed-browser policy can disallow unpacked installations; do not disable organization policy or browser protections. Keep the extracted folder. Updates are manual: replace the files with the new version and reload the extension.

## Firefox

The original ZIP includes Firefox-specific settings. Temporary developer testing can use `about:debugging#/runtime/this-firefox` → **Load Temporary Add-on** → extracted `manifest.json`. Compatibility was not tested in Firefox. This ends at browser restart. Ordinary permanent installation requires a compatible Mozilla-signed XPI, not merely renaming a ZIP; none is supplied. No instruction to disable signing is provided.

## Phones, tablets and Safari

This ZIP is not an installable extension for mobile Chrome or Safari. Browser-specific mobile/Safari packages are separate work. The aureon.defender Android APK and limited web edition remain distinct products, with their stated OS restrictions.

## Verification and scope

The adapted package's background service worker and popup loaded in an isolated Chromium profile, with no popup JavaScript errors. This is a load/UI smoke check, not a complete security/feature audit. The user's real browser profile and proxy settings were not modified. Broad site/history/cookie/proxy/download permissions are visible because they affect a meaningful installation decision.

References: [Chrome MV3 blocking request limits](https://developer.chrome.com/docs/extensions/develop/migrate/blocking-web-requests), [Mozilla temporary installation](https://extensionworkshop.com/documentation/develop/temporary-installation-in-firefox/), [Mozilla distribution/signing](https://extensionworkshop.com/documentation/publish/signing-and-distribution-overview/).
