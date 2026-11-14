"""Evidence-based, read-only infrastructure audit; runs on Pi and Windows.

Inventory is user supplied. MQTT telemetry is an observation, never proof of
circuit topology, appliance identity, occupancy or malicious intent.
"""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path


LIMITS = [
    "A client cannot prevent its access point from revoking access or stop RF jamming.",
    "QoS requires control of the router carrying the traffic; it cannot create radio capacity.",
    "One outlet cannot reveal all building wiring, hidden devices or people.",
    "HomePlug peers are network observations, not a map of breakers or copper routes.",
    "Power signatures are ambiguous; unknown devices and anomalies are not proof of an intruder.",
    "Circuit mapping needs recorded tracing/inspection; switching needs rated installed hardware.",
]


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite nonnegative number")
    return value


def timestamp(value):
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return t.astimezone(timezone.utc)


def validate(data):
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("inventory requires version: 1")
    ids = set()
    circuits = data.get("circuits", [])
    outlets = data.get("outlets", [])
    for group in (circuits, outlets):
        if not isinstance(group, list):
            raise ValueError("circuits/outlets must be lists")
        for item in group:
            if not isinstance(item, dict):
                raise ValueError("circuit/outlet records must be objects")
            key = item.get("id")
            if not isinstance(key, str) or not key or key in ids:
                raise ValueError("circuit/outlet IDs must be nonempty and unique")
            ids.add(key)
    circuit_ids = {c["id"] for c in circuits}
    for c in circuits:
        if "monitor_limit_a" in c:
            number(c["monitor_limit_a"], "monitor_limit_a")
    topics = set()
    for o in outlets:
        if o.get("circuit_id") and o["circuit_id"] not in circuit_ids:
            raise ValueError("unknown circuit_id")
        if o.get("mapping") not in (None, "unknown", "user_label", "traced"):
            raise ValueError("mapping must be unknown, user_label or traced")
        if o.get("mapping") == "traced" and (not o.get("evidence") or not o.get("circuit_id")):
            raise ValueError("traced mapping requires circuit_id and evidence")
        topic = o.get("topic")
        if topic:
            if not isinstance(topic, str) or topic in topics or "+" in topic or "#" in topic:
                raise ValueError("topics must be unique exact MQTT topics")
            topics.add(topic)
        if "monitor_limit_w" in o:
            number(o["monitor_limit_w"], "monitor_limit_w")
    return data


def audit(data, observations=(), now=None):
    validate(data)
    now = now or datetime.now(timezone.utc)
    latest, rejected = {}, 0
    topics = {o["topic"] for o in data.get("outlets", []) if o.get("topic")}
    for row in observations:
        try:
            topic = row["topic"]
            t = timestamp(row["received_at"])
            energy = row["payload"]["ENERGY"]
            watts = number(energy["Power"], "Power")
            amps = number(energy["Current"], "Current") if "Current" in energy else None
            if topic not in topics or (now - t).total_seconds() < -60:
                raise ValueError("unmapped topic or future observation")
            if topic not in latest or t > latest[topic][0]:
                latest[topic] = (t, watts, amps)
        except (KeyError, TypeError, ValueError, AttributeError):
            rejected += 1
    findings, outlets = [], []

    def finding(code, level, asset, evidence, impact, patch):
        findings.append(dict(code=code, level=level, asset=asset, evidence=evidence,
                             impact=impact, patch=patch))

    wifi = data.get("wifi", {})
    if not isinstance(wifi, dict):
        raise ValueError("wifi must be an object")
    if wifi.get("pmf_required") is not True:
        finding("pmf_unverified", "low", "wifi", "PMF-required configuration not recorded.",
                "Compatible clients may be exposed to forged management frames.",
                "Verify PMF-required on your managed AP and client compatibility; retain a fallback connection.")
    for o in data.get("outlets", []):
        row = dict(o)
        obs = latest.get(o.get("topic"))
        row["measurement"] = None
        if obs:
            t, watts, amps = obs
            age = (now - t).total_seconds()
            row["measurement"] = dict(watts=watts, amps=amps, received_at=t.isoformat(), stale=age > 300)
            if age > 300:
                finding("stale_sensor", "low", o["id"], f"Last receipt {int(age)} seconds ago.",
                        "Current state is unknown.", "Check sensor power, connectivity and collector.")
            elif "monitor_limit_w" in o and watts > o["monitor_limit_w"]:
                finding("load_threshold", "medium", o["id"], f"Measured {watts} W exceeds configured {o['monitor_limit_w']} W.",
                        "Load exceeded the user's monitoring threshold; cause is unverified.",
                        "Review the load and equipment rating; use an electrician for wiring concerns.")
        elif o.get("topic"):
            finding("missing_sensor", "low", o["id"], "No accepted telemetry.",
                    "Electrical state is unknown.", "Check the exact topic and collect telemetry.")
        if o.get("mapping") != "traced":
            finding("unverified_mapping", "low", o["id"], "Circuit relationship has no tracing record.",
                    "Shared-breaker impact cannot be established.", "Record qualified circuit tracing and its evidence.")
        outlets.append(row)
    if rejected:
        finding("rejected_telemetry", "low", "collector", f"Rejected {rejected} observations.",
                "Malformed, unmapped or future-dated data was excluded.", "Review collector clock, topics and JSON format.")
    return dict(version=1, generated_at=now.isoformat(), mode="read_only", outlets=outlets,
                circuits=data.get("circuits", []), findings=findings, limits=LIMITS,
                rejected_observations=rejected, identity="User labels only; no people identification",
                control_available=False)


def load_report(inventory, telemetry=None):
    data = json.loads(Path(inventory).read_text(encoding="utf-8"))
    rows = []
    if telemetry and Path(telemetry).exists():
        # Bad JSON is a visible input error rather than a silently clean audit.
        rows = [json.loads(line) for line in Path(telemetry).read_text(encoding="utf-8").splitlines() if line.strip()]
    return audit(data, rows)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("inventory")
    p.add_argument("--telemetry", help="JSONL: topic, received_at (timezone), payload (Tasmota SENSOR JSON)")
    p.add_argument("--out")
    a = p.parse_args(argv)
    try:
        report = json.dumps(load_report(a.inventory, a.telemetry), indent=2)
    except (ValueError, OSError, TypeError) as ex:
        p.error(str(ex))
    if a.out:
        Path(a.out).write_text(report + "\n", encoding="utf-8")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
