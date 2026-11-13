# Phones

## Android
1. **Private DNS** - Settings > Network & internet > Private DNS > hostname of your Node
   (AdGuard Home DoT on 853, needs a TLS cert - use Caddy or AdGuard's built-in ACME).
2. **WireGuard always-on** - import the wg-easy QR. Settings > VPN > gear > *Always-on VPN* and
   *Block connections without VPN* (kill switch).
3. **Spyware check (MVT)** on the laptop:
   ```bash
   pip install mvt
   mvt-android download-iocs
   mvt-android check-adb --output mvt-out/     # enable USB debugging temporarily, disable after
   ```
   Or make an `androidqf` acquisition and run `mvt-android check-androidqf`.
4. **Network inspection** - boot a spare SD card with PiRogue OS, join the phone to its AP,
   and review flows/alerts (Suricata rules, DNS, TLS SNI) for unknown destinations.
5. **Termux toolbox** - `scripts/android-termux/setup.sh` (install Termux from F-Droid).
6. **De-Googling** - only on devices with an officially unlockable bootloader. Use the ROM
   project's own device page (LineageOS, GrapheneOS for Pixels, CalyxOS). Unlocking wipes data
   and can void warranty; never flash a build not made for your exact model.

## iOS
1. AdGuard Home > Setup guide > iOS: install the DoH/DoT `.mobileconfig`.
2. WireGuard app: import QR, enable *On-Demand* for all networks.
3. MVT: make an **encrypted** local backup in Finder/iTunes, then
   ```bash
   mvt-ios decrypt-backup -p <backup-password> -d decrypted/ <backup-dir>
   mvt-ios download-iocs
   mvt-ios check-backup --output mvt-out/ decrypted/
   ```
4. High-risk users: enable Lockdown Mode.

If MVT reports a match, don't wipe straight away: preserve the output and contact a digital
security helpline (e.g. Access Now's) before changing the device.
