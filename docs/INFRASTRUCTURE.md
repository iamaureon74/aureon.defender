# Infrastructure extension, 2026-11-14

This extends the unfinished Wi-Fi/powerline work without claiming measurements
that the laptop cannot perform. Source changes are not installed into the running EXE.

## Open-source components to use

| Requirement | Component | What it actually supplies |
|---|---|---|
| Router queue management | [OpenWrt SQM/CAKE](https://openwrt.org/docs/guide-user/network/traffic-shaping/sqm) | Queue scheduling and latency control on a managed gateway. Device priority needs suitable classification/policy; SQM alone is not a device priority button. |
| Raspberry Pi access point | [RaspAP](https://github.com/RaspAP/raspap-webgui) | GPL-3.0 access-point/router management on supported Debian/Pi configurations. Use as an alternative gateway stack to OpenWrt. |
| Radio audit | [Kismet](https://www.kismetwireless.net/docs/readme/intro/kismet/) | Passive wireless observations and alerts with compatible capture hardware. Not an anti-jamming shield or people attribution tool. |
| Metered plug telemetry/control | [Tasmota](https://tasmota.github.io/docs/) | Open-source device firmware, local MQTT telemetry and relays on supported hardware. Aureon currently consumes telemetry only. |
| Circuit measurements | [OpenEnergyMonitor](https://openenergymonitor.org/docs/emonpi/technical.html) | Pi-connected measurement hardware/CT inputs, logging and MQTT. Channel coverage depends on installed hardware. |
| Alternative multi-channel sensors | [ESPHome ATM90E32](https://esphome.io/components/sensor/atm90e32/) | Supported energy metering hardware, including multi-channel boards. |
| HomePlug discovery | [open-plc-utils](https://github.com/qca/open-plc-utils) | Compatible HomePlug device management/discovery. Not electrical wiring tomography. |
| Experimental appliance signatures | [NILMTK](https://github.com/nilmtk/nilmtk) | Load-disaggregation research. Requires appropriate measurements/training; no guaranteed device count, identity, occupancy or adversary detection. Not integrated. |

The software components are free/open source; Pi, radios, metered plugs, tracing
tools, sensors and installation are additional hardware/work. Preserve upstream licenses.

## Wi-Fi feasibility

PMF (802.11w) protects certain management frames against forgery when negotiated.
It does not stop a legitimate AP from removing a client, interference, jamming,
an upstream outage or power loss. A separate managed AP with Ethernet uplink and
an independent backup connection provides more resilience than a Wi-Fi repeater
using the same upstream radio. Configure PMF with compatible clients on your own AP.
Reference: [Cisco PMF configuration guide](https://www.cisco.com/c/en/us/td/docs/wireless/controller/9800/17-10/config-guide/b_wl_17_10_cg/m-802-11w.pdf).

To prioritize a user's hardware, route it through a gateway you administer.
Measure uplink/downlink, configure SQM for that link, then define device/service
classification and test latency under load. Radio airtime scheduling requires AP
and driver support. Aureon's Windows profile preference changes local connection
order only; no router QoS changes are implemented or applied by this extension.

## What is implemented

`python -m aureon.infrastructure docs/infrastructure.example.json --out report.json`

The dependency-free Python audit runs on Pi OS or Windows. It validates recorded
circuits/outlets, imports Tasmota observations, checks configured per-outlet watt
thresholds and missing/stale telemetry, and returns findings with evidence,
possible impact and remediation. It does not calculate a whole-circuit load from
partial plug coverage. Thresholds are monitoring settings, not electrical safety ratings.

An outlet record can contain:

```json
{
  "id": "office-outlet-1",
  "circuit_id": "panel-a-7",
  "mapping": "traced",
  "evidence": "Qualified tracing record reference and date",
  "topic": "tele/office-meter/SENSOR",
  "monitor_limit_w": 200
}
```

Declare `panel-a-7` in `circuits` as `{"id":"panel-a-7"}`. Use `user_label`
or `unknown` if the relationship has not been traced. Labels/evidence are supplied
by the user and are not independently certified by this program. Do not enter
people identities based on electrical signatures.

Read-only collection with a separately installed Mosquitto client:

```sh
mosquitto_sub -h localhost -t 'tele/+/SENSOR' -F '%t %p' | python scripts/collect_power.py >> infrastructure-telemetry.jsonl
python -m aureon.infrastructure inventory.json --telemetry infrastructure-telemetry.jsonl --out report.json
```

Use broker authentication, TLS for untrusted links and topic ACLs. The collector
accepts standard Tasmota ENERGY messages; OpenEnergyMonitor/ESPHome payloads need
an explicit adapter before import. Receipt timestamps indicate collection time,
not guaranteed measurement time; retained MQTT values can be old. Rotate telemetry
files; the current importer reads a file in memory and is intended for bounded logs.

The updated desktop source loads `infrastructure.json` and optional
`infrastructure-telemetry.jsonl` from `core.data_dir()` (normally
`C:\ProgramData\Aureon`, with per-user/environment fallbacks). It displays the
audit under Network & Power. These files are not created or populated with fake
building data. No remote Pi transport, automatic discovery of wiring, remote
outlet switching, or automatic patch deployment is implemented.

## Whole-building audit and control design

Record panel → breaker → outlet → metered device relationships from qualified
tracing and inspection; retain uncertain edges explicitly. Install enough sensor
channels to cover the circuits of interest. Use appropriately rated certified
smart outlets/contactors and qualified installation for mains/panel work. Never
wire Pi GPIO directly to mains. A normal smart plug controls only its downstream load.

Future control must use an authenticated allowlist of enrolled devices, exclude
critical loads, log operator actions, and preserve manual operation. No automatic
shutdown based on anomaly scores. The current release deliberately has no relay
commands. Building-wide management requires authority for the affected circuits.

Auditable threat patterns include an exposed MQTT broker (unauthorized telemetry
or relay commands), insecure HomePlug pairing (network exposure), firmware/admin
weaknesses (device compromise), missing sensors (blind spots), and shared circuit
dependencies (one outage affects multiple assets). Verify each condition with
configuration or measurements before raising a finding. Review credentials,
ACLs, firmware, network segmentation and physical installation accordingly.
An unusual electrical load alone does not establish a malicious action.

## Validation and remaining deployment

Regression tests cover negative PMF detection, HomePlug discovery behind a generic
NIC, collection failures, duplicate IDs, tracing provenance, stale observations,
out-of-order observations, NaN/bool/future inputs and threshold findings.
Hardware tests, ARM/Pi execution, real radio capture, electrical measurements and
EXE deployment remain unverified. Test on the actual equipment before relying on it.


Observed verification on Windows, 2026-11-14:
- New infrastructure regression tests: 9/9 passed.
- Dashboard JavaScript: node --check passed. Python compilation passed.
- Empty-inventory CLI smoke test passed (no fake measurements).
- Windows suite: 90 run, 1 feed-test failure, 3 skipped. Existing feed fixture expects an older feed API/configuration; feeds.py was not changed in this extension.
- Core suite: 54 run, 3 Linux shell-test failures because WSL has no installed distribution. Linux scripts were not changed.
- No ARM hardware run, live broker/sensor test, browser visual test, EXE rebuild or deployment performed.
