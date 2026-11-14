"""Collect Tasmota SENSOR messages from a local mosquitto_sub stream.

Usage: mosquitto_sub -h localhost -t 'tele/+/SENSOR' -F '%t %p' |
       python scripts/collect_power.py > infrastructure-telemetry.jsonl
Broker authentication/TLS belong in mosquitto_sub's protected config file.
Use a read-only broker account restricted to authorized sensor topics.
"""
import json
import sys
from datetime import datetime, timezone


def main():
    for line in sys.stdin:
        try:
            topic, payload = line.rstrip().split(' ', 1)
            value = json.loads(payload)
            if not isinstance(value, dict) or not isinstance(value.get('ENERGY'), dict):
                raise ValueError('not an ENERGY observation')
            print(json.dumps(dict(topic=topic, received_at=datetime.now(timezone.utc).isoformat(), payload=value)), flush=True)
        except (ValueError, TypeError):
            print('Rejected malformed/non-energy MQTT message', file=sys.stderr)


if __name__ == '__main__':
    main()
