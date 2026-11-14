"""Read-only Linux/Pi USB baseline and security-service observations.

No installers, USB blocking, firewall changes or baseline writes occur implicitly.
USB descriptors are spoofable; a baseline difference is not proof of an attack.
"""
import argparse
import hashlib
import json
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

SERVICES = ("usbguard", "crowdsec", "suricata", "auditd")
TOOLS = ("usbguard", "aide", "lynis", "cscli", "suricata", "zeek")


def load_report(path):
    """Import an operator-copied report; it is not authenticated remote attestation."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('version') != 1 or data.get('mode') != 'read_only':
        raise ValueError('unsupported security-node report')
    t = datetime.fromisoformat(data['generated_at'].replace('Z', '+00:00'))
    if t.tzinfo is None:
        raise ValueError('report timestamp requires timezone')
    age = (datetime.now(timezone.utc)-t).total_seconds()
    data['stale'] = age > 300 or age < -60
    data['provenance'] = 'operator-imported; not authenticated attestation'
    if not isinstance(data.get('findings'), list) or any(not isinstance(f, dict) or not isinstance(f.get('text'), str) for f in data['findings']):
        raise ValueError('invalid report findings')
    return data


def usb_inventory(root=Path('/sys/bus/usb/devices')):
    result = []
    if not root.is_dir():
        return None
    for device in sorted(root.iterdir()):
        if not (device / 'idVendor').is_file():
            continue  # skip interface entries
        values = {}
        try:
            for key in ('idVendor', 'idProduct', 'bDeviceClass', 'manufacturer', 'product', 'serial', 'authorized'):
                p = device / key
                values[key] = p.read_text(encoding='utf-8', errors='replace').strip() if p.is_file() else ''
        except OSError:
            result.append(dict(port=device.name, status='read_failed'))
            continue
        # Do not export serials or manufacturer-provided text by default.
        identity = {k: values[k] for k in ('idVendor', 'idProduct', 'bDeviceClass', 'serial')}
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        result.append(dict(port=device.name, vendor=values['idVendor'], product=values['idProduct'],
                           device_class=values['bDeviceClass'], fingerprint=digest,
                           authorized=values['authorized'] == '1' if values['authorized'] in ('0', '1') else None,
                           status='observed'))
    return result


def service_status(name):
    tool = shutil.which('systemctl')
    if not tool:
        return 'unknown'
    try:
        r = subprocess.run([tool, 'is-active', name + '.service'], capture_output=True,
                           text=True, timeout=4)
    except (OSError, subprocess.TimeoutExpired):
        return 'collection_failed'
    value = r.stdout.strip()
    return value if value in ('active', 'inactive', 'failed', 'activating', 'deactivating') else 'unknown'


def compare(current, baseline):
    def keys(rows):
        if not isinstance(rows, list) or any(not isinstance(r, dict) or not isinstance(r.get('port'), str)
                                            or not isinstance(r.get('fingerprint'), str) for r in rows):
            raise ValueError('baseline/current USB records require port and fingerprint')
        return {(r['port'], r['fingerprint']) for r in rows}
    before, after = keys(baseline), keys(current)
    return dict(added=[dict(port=p, fingerprint=f) for p, f in sorted(after-before)],
                removed=[dict(port=p, fingerprint=f) for p, f in sorted(before-after)])


def collect(baseline=None, root=Path('/sys/bus/usb/devices')):
    linux = platform.system() == 'Linux'
    usb = usb_inventory(root) if linux else None
    services = {s: service_status(s) for s in SERVICES} if linux else {}
    findings = []
    changes = None
    if baseline is not None and usb is not None:
        if any(r.get('status') != 'observed' for r in usb):
            findings.append(dict(level='low', text='USB reads failed; baseline comparison skipped.'))
        else:
            changes = compare(usb, baseline)
            if changes['added'] or changes['removed']:
                findings.append(dict(level='medium', text='USB baseline differs. Review expected replacements, moves and reconnects before treating this as suspicious.'))
    for name, state in services.items():
        if state != 'active':
            findings.append(dict(level='low', text=f'{name} service state: {state}. Coverage is unverified; check whether this service is intended on this node.'))
    return dict(version=1, generated_at=datetime.now(timezone.utc).isoformat(),
                platform=platform.system(), machine=platform.machine(), mode='read_only',
                usb_status='observed' if usb is not None else 'unavailable', usb=usb,
                tools={t: bool(shutil.which(t)) for t in TOOLS} if linux else {},
                services=services, changes=changes, findings=findings,
                limits=['Service active does not verify rules, traffic visibility or enforcement.',
                        'USB descriptors and serial hashes are spoofable, and identify neither a person nor intent.',
                        'A Pi monitors its own USB bus; it does not inspect laptop USB ports remotely.',
                        'Moving devices between ports changes the comparison; no baseline is trusted automatically.'])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', help='Earlier security-node JSON report explicitly trusted by the operator')
    p.add_argument('--out')
    a = p.parse_args(argv)
    try:
        baseline = None
        if a.baseline:
            old = json.loads(Path(a.baseline).read_text(encoding='utf-8'))
            if old.get('version') != 1 or old.get('usb_status') != 'observed':
                raise ValueError('baseline requires version 1 and observed USB data')
            baseline = old['usb']
            compare([], baseline)  # validate even if current host is not Linux
        report = json.dumps(collect(baseline), indent=2)
        if a.out:
            Path(a.out).write_text(report+'\n', encoding='utf-8')
        else:
            print(report)
    except (OSError, ValueError, KeyError, TypeError) as ex:
        p.error(str(ex))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
