"""Off-grid messaging over Meshtastic LoRa radios (meshtastic/python).

  python -m aureon mesh send --port COM7 "node is up"          one message to the primary channel
  python -m aureon mesh listen --port /dev/ttyUSB0             print incoming texts
  python -m aureon mesh bridge --port /dev/ttyUSB0 --watch reports/latest.md --log inbox.jsonl
      relay the headline of every new analyst report over LoRa, log inbound texts

LoRa packets are small (~200 bytes) and slow: only short headlines go over the mesh.
Meshtastic encrypts channels with AES-256 when you set a channel PSK (do it: the default key is public).
"""
import json
import os
import time

MAX = 200


def _iface(port):
    try:
        import meshtastic.serial_interface as si
    except ImportError:
        raise SystemExit("pip install meshtastic")
    return si.SerialInterface(devPath=port)


def chunks(text, n=MAX):
    text = " ".join(text.split())
    return [text[i:i + n] for i in range(0, len(text), n)] or [""]


def headline(md_text):
    """First heading + first severity line of an analyst report."""
    lines = [l.strip() for l in md_text.splitlines() if l.strip()]
    head = next((l.lstrip("# ") for l in lines if l.startswith("#")), "Aureon report")
    sev = next((l for l in lines if l.lower().startswith(("**severity", "severity"))), "")
    return f"{head} | {sev}".strip(" |")


def send(port, text):
    iface = _iface(port)
    try:
        for c in chunks(text):
            iface.sendText(c)
            time.sleep(2)  # be nice to the duty cycle
    finally:
        iface.close()


def _on_receive(log):
    def cb(packet, interface):
        d = packet.get("decoded", {})
        if d.get("portnum") != "TEXT_MESSAGE_APP":
            return
        rec = {"t": int(time.time()), "from": packet.get("fromId"), "text": d.get("text", "")}
        print(f"[{rec['from']}] {rec['text']}")
        if log:
            with open(log, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
    return cb


def listen(port, log=None, watch=None):
    from pubsub import pub  # dependency of meshtastic
    pub.subscribe(_on_receive(log), "meshtastic.receive")
    iface = _iface(port)
    last = os.path.getmtime(watch) if watch and os.path.exists(watch) else 0
    try:
        while True:
            time.sleep(10)
            if watch and os.path.exists(watch) and os.path.getmtime(watch) > last:
                last = os.path.getmtime(watch)
                with open(watch, encoding="utf-8") as f:
                    msg = "AUREON " + headline(f.read())
                for c in chunks(msg):
                    iface.sendText(c)
                    time.sleep(2)
                print(f"relayed: {msg}")
    finally:
        iface.close()


def cli(a):
    if a.action == "send":
        send(a.port, " ".join(a.text))
    elif a.action == "listen":
        listen(a.port, a.log)
    elif a.action == "bridge":
        listen(a.port, a.log, a.watch)
    return 0
