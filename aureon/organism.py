"""Aureon as one organism: every capability is part of an organ, and organs depend on each other.

Like a body, no organ is useful alone: the immune system has to see the blood (traffic), it reports through
the nerves, the brain makes sense of it, and reflexes act before the brain answers. When one organ fails,
`aureon body` shows which others it takes down with it.

  python -m aureon body               organ map + live vitals of this machine (and the Node if AUREON_NODE is set)
  python -m aureon body --graph       Mermaid diagram of organ dependencies
  python -m aureon body --fail skin   what breaks if an organ goes down
  python -m aureon body --json
"""
import json
import os
import shutil
import socket
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME = Path.home() / ".aureon"

# id: (name, body analogy, role in Aureon, capability ids, needs [organ ids])
ORGANS = {
    "dna": ("DNA", "Genome that builds identical bodies",
            "Reproducible images and provisioning: rebuild a lost device identically",
            ["system.image"], []),
    "skeleton": ("Skeleton", "Frame everything hangs on",
                 "Firmware, secure boot, base OS and appliance personalities",
                 ["system.firmware", "system.appliance", "system.research-os"], ["dna"]),
    "heart": ("Heart", "Pumps blood to every organ",
              "Container/VM runtime that keeps every service alive and restarts it",
              ["perform.compute"], ["skeleton"]),
    "skin": ("Skin", "Barrier that keeps germs out",
             "Filtered DNS and firewall: most threats never get in",
             ["network.dns"], ["skeleton"]),
    "blood": ("Circulatory system", "Carries oxygen between organs",
              "Encrypted VPN and mesh that carry traffic between phone, laptop and Node",
              ["network.vpn", "network.access"], ["skin"]),
    "lungs": ("Lungs", "Exchange with the outside air",
              "Controlled contact with the outside world: anonymity, tunnels, sync and transfer",
              ["network.anonymity", "network.storage", "network.crypto-nodes"], ["blood"]),
    "immune": ("Immune system", "Finds and kills infections",
               "IDS/IPS, endpoint protection, tripwires, phone forensics, secret hygiene",
               ["protect.network-ids", "protect.endpoint", "protect.deception", "protect.mobile",
                "protect.secrets"], ["blood", "nerves"]),
    "liver": ("Liver", "Breaks down toxins after they get in",
              "Forensics and reverse engineering: take apart what got through",
              ["protect.forensics"], ["immune"]),
    "vaccine": ("Vaccination", "Controlled exposure that builds immunity",
                "Authorized self-audit: attack your own devices so the immune system learns",
                ["protect.audit", "protect.wifi-audit", "protect.physical", "protect.osint"], ["immune"]),
    "nerves": ("Nervous system", "Carries signals to the brain",
               "Metrics, logs and alerts flowing from every sensor (Netdata, Prometheus, dashboards)",
               ["perform.observe", "freedom.dashboard"], ["skeleton"]),
    "brain": ("Brain", "Understands and decides",
              "Local LLM: the security analyst and the private assistant",
              ["intel.llm", "intel.accel"], ["heart", "nerves"]),
    "reflex": ("Reflexes", "Spinal cord acts before the brain does",
               "Instant reactions with no AI in the loop: Key panic/tamper lock, HID injection guard",
               ["hardware.key"], ["nerves"]),
    "ears": ("Ears", "Hear what is around you",
             "Radio senses: SDR, rogue WiFi and fake cell-tower watch, voice input",
             ["radio.sdr", "protect.wireless-watch", "intel.voice", "radio.aviation-space"], ["nerves"]),
    "eyes": ("Eyes", "See what is around you",
             "Cameras and vision: presence detection, NVR",
             ["hardware.camera", "intel.vision"], ["nerves", "brain"]),
    "hands": ("Hands", "Act on the physical world",
              "GPIO/sensors, remote control and below-OS rescue (PiKVM)",
              ["hardware.io", "freedom.remote", "intel.robotics", "make.fabrication", "make.astro"], ["nerves"]),
    "voice": ("Voice", "Speak to others",
              "Own communications plus off-grid LoRa mesh when the network is gone",
              ["freedom.comms", "network.offgrid", "radio.ham"], ["nerves"]),
    "memory": ("Memory", "Remembers everything",
               "Personal cloud, databases and web serving: your data on your hardware",
               ["freedom.cloud", "freedom.data", "freedom.web", "freedom.business", "freedom.dev"], ["heart", "blood"]),
    "endocrine": ("Endocrine system", "Slow hormones that tune the whole body",
                  "Home automation: schedules and presence that adjust everything else",
                  ["home.automation"], ["nerves", "blood"]),
    "muscles": ("Muscles", "Do the physical work fast",
                "Performance: run any software, light desktop, streaming to the phone",
                ["perform.compat", "perform.desktop", "perform.stream"], ["skeleton"]),
    "digestion": ("Digestive system", "Turns food into energy",
                  "Offline knowledge, learning and media feed the user and the brain",
                  ["system.knowledge", "learn.code", "media.center", "media.play"], ["memory", "brain"]),
}


# ---------------- vitals: live checks, each returns (state, detail) ----------------
def _port(host, port, timeout=1.5):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _has(*tools):
    found = [t for t in tools if shutil.which(t)]
    return found


def _http(url, timeout=2):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status < 500
    except Exception:
        return False


def vitals():
    """Live state per organ: 'alive', 'weak' (partly present), 'absent' (not installed/configured)."""
    from .audit import run_audit
    audit = {r["check"]: r["status"] for r in run_audit()["results"]}
    node = os.environ.get("AUREON_NODE")
    v = {}

    def put(oid, ok, weak, detail):
        v[oid] = ("alive" if ok else "weak" if weak else "absent", detail)

    put("dna", (ROOT / "stack.json").exists() and (ROOT / "capabilities.json").exists(), False,
        "manifest + capability map present")
    sb = audit.get("Secure Boot")
    put("skeleton", sb == "PASS", sb in ("SKIP", "WARN"), f"secure boot: {sb}")
    rt = _has("docker", "podman")
    put("heart", bool(rt), True, f"container runtime: {rt or 'none - native OS services only (Node needs Docker/Podman)'}")
    fw = audit.get("Firewall")
    dns_node = bool(node) and _port(node, 53)
    put("skin", fw == "PASS" and dns_node, fw == "PASS", f"firewall {fw}; node DNS {'up' if dns_node else 'not reachable/unset'}")
    vpn = audit.get("VPN")
    put("blood", vpn == "PASS", False, f"VPN interface: {vpn}")
    lungs = _has("syncthing", "rclone", "tor")
    put("lungs", len(lungs) >= 2, bool(lungs), f"{lungs or 'no sync/backup/anonymity tools'}")
    av = audit.get("Defender") or audit.get("Firewall")
    ids = bool(node) and _port(node, 3000)
    put("immune", av == "PASS" and ids, av == "PASS", f"endpoint {av}; node shield {'up' if ids else 'not reachable/unset'}")
    put("liver", bool(_has("volatility", "vol", "r2", "ghidraRun", "wireshark", "tshark")), False,
        f"forensic tools: {_has('vol', 'r2', 'tshark', 'wireshark') or 'none'}")
    put("vaccine", bool(_has("nmap", "nuclei", "lynis")), False, f"audit tools: {_has('nmap', 'nuclei', 'lynis') or 'none'}")
    nd = bool(node) and _port(node, 19999)
    put("nerves", nd, True, "local audit always on; node netdata " + ("up" if nd else "not reachable/unset"))
    llm_url = os.environ.get("AUREON_LLM_URL", "http://127.0.0.1:11434")
    brain = _http(llm_url + "/api/tags") or _http(llm_url.rstrip("/") + "/models")
    put("brain", brain, True, f"LLM at {llm_url}: {'up' if brain else 'down - analyst falls back to rule-based triage'}")
    reflex = (HOME / "hid_baseline.json").exists()
    put("reflex", reflex, True, "hidguard baseline " + ("learned" if reflex else "not learned (aureon hidguard --learn)"))
    ears = (HOME / "wifi_baseline.json").exists()
    put("ears", ears, True, "wifi baseline " + ("learned" if ears else "not learned (aureon rf wifi --learn)"))
    put("eyes", False, False, "no camera pipeline configured (Frigate optional)")
    kvm = bool(os.environ.get("AUREON_KVM_URL"))
    put("hands", kvm, True, "PiKVM " + ("configured" if kvm else "not configured") + "; aureon rescue ready")
    put("voice", bool(_has("meshtastic")), False, f"meshtastic CLI: {'present' if _has('meshtastic') else 'absent'}")
    mem = bool(node) and _port(node, 443)
    put("memory", mem, bool(_has("syncthing")), "node cloud " + ("up" if mem else "not reachable/unset"))
    put("endocrine", bool(node) and _port(node, 8123), False, "Home Assistant on node :8123")
    put("muscles", True, False, f"{os.cpu_count()} CPUs; perf profile available")
    kiwix = bool(node) and _port(node, 8181)
    put("digestion", kiwix, False, "Kiwix on node :8181 " + ("up" if kiwix else "not reachable/unset"))
    return v


# ---------------- graph logic ----------------
def dependents(oid):
    """All organs that directly or indirectly need `oid`."""
    out, frontier = set(), {oid}
    while frontier:
        nxt = {o for o, spec in ORGANS.items() if set(spec[4]) & frontier} - out
        out |= nxt
        frontier = nxt
    return out


def impaired(v):
    """Organs that are alive themselves but depend on an absent organ."""
    down = {o for o, (s, _) in v.items() if s == "absent"}
    hit = {}
    for o in down:
        for d in dependents(o):
            if v.get(d, ("absent",))[0] != "absent":
                hit.setdefault(d, set()).add(o)
    return hit


def check_graph():
    """Graph must be acyclic and reference only known organs/capabilities."""
    caps = {c["id"] for c in json.loads((ROOT / "capabilities.json").read_text(encoding="utf-8"))}
    used = []
    for oid, (_, _, _, cids, needs) in ORGANS.items():
        for n in needs:
            assert n in ORGANS, f"{oid} needs unknown organ {n}"
        for c in cids:
            assert c in caps, f"{oid} lists unknown capability {c}"
        used += cids
    assert sorted(used) == sorted(caps), f"capabilities not in exactly one organ: {set(caps) ^ set(used)}"
    seen, stack = set(), set()

    def visit(o):
        assert o not in stack, f"dependency cycle through {o}"
        if o in seen:
            return
        stack.add(o)
        for n in ORGANS[o][4]:
            visit(n)
        stack.discard(o)
        seen.add(o)
    for o in ORGANS:
        visit(o)
    return True


def mermaid():
    lines = ["graph TD"]
    for oid, (name, *_rest) in ORGANS.items():
        lines.append(f'  {oid}["{name}"]')
    for oid, spec in ORGANS.items():
        for n in spec[4]:
            lines.append(f"  {n} --> {oid}")
    return "\n".join(lines)


def cli(a):
    if a.graph:
        print(mermaid())
        return 0
    if a.fail:
        if a.fail not in ORGANS:
            raise SystemExit(f"unknown organ; choose from {', '.join(ORGANS)}")
        hit = dependents(a.fail)
        print(f"If {ORGANS[a.fail][0]} fails, these organs lose something they need:")
        for o in sorted(hit, key=list(ORGANS).index):
            print(f"  - {ORGANS[o][0]}: {ORGANS[o][2]}")
        return 0
    v = vitals()
    imp = impaired(v)
    if a.json:
        print(json.dumps({o: {"name": ORGANS[o][0], "state": s, "detail": d, "needs": ORGANS[o][4],
                              "impaired_by": sorted(imp.get(o, []))} for o, (s, d) in v.items()}, indent=1))
        return 0
    icon = {"alive": "+", "weak": "~", "absent": "-"}
    print("Aureon organism - live vitals (+ alive, ~ weak, - absent)\n")
    for o, spec in ORGANS.items():
        s, d = v[o]
        print(f" [{icon[s]}] {spec[0]:<20} {d}")
        if o in imp:
            print(f"      ! impaired: needs {', '.join(ORGANS[x][0] for x in sorted(imp[o]))}")
    alive = sum(1 for s, _ in v.values() if s == "alive")
    print(f"\n{alive}/{len(v)} organs fully alive. Set AUREON_NODE=<node-ip> to include Node organs.")
    return 0
