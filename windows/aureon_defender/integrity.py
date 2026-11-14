"""Offline integrity checks for packaged UI/rules. Not protection against admin tampering."""
import hashlib
import json
from pathlib import Path


def check(root=None):
    root = Path(root or Path(__file__).parent).resolve()
    manifest = root / 'integrity.json'
    if not manifest.exists():
        return {'status':'unavailable', 'findings':[], 'detail':'No packaged integrity baseline.'}
    try:
        entries = json.loads(manifest.read_text(encoding='utf-8'))['files']
        if not isinstance(entries, dict) or not entries:
            raise ValueError('empty baseline')
        findings = []
        for name, expected in entries.items():
            p = (root / name).resolve()
            if root not in p.parents or not isinstance(expected, str) or len(expected) != 64:
                raise ValueError('invalid baseline entry')
            if not p.is_file():
                findings.append({'path':name,'reason':'missing'})
            elif hashlib.sha256(p.read_bytes()).hexdigest() != expected:
                findings.append({'path':name,'reason':'changed'})
        return {'status':'changed' if findings else 'matches_baseline', 'checked':len(entries), 'findings':findings,
                'detail':'Bundled UI/rules only. Baseline is local and unsigned; this is not code attestation.'}
    except (ValueError, OSError, KeyError, TypeError) as ex:
        return {'status':'collection_failed', 'findings':[], 'detail':str(ex)}
