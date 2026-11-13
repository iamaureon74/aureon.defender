"""Regenerate docs/ORGANISM.md from aureon/organism.py (tests fail if it is stale)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from aureon.organism import ORGANS, dependents, mermaid  # noqa: E402


def render():
    caps = {c["id"]: c for c in json.loads((ROOT / "capabilities.json").read_text(encoding="utf-8"))}
    out = ["# Aureon as an organism", "",
           "Aureon's 53 capabilities (fused from all 790 projects) are grouped into 20 organs. Like a body, each organ",
           "needs others to work: the immune system must see the blood (traffic) and report through the nerves; the",
           "brain needs nerves to hear anything; reflexes act on their own before the brain answers.",
           "", "`python -m aureon body` shows live vitals; `python -m aureon body --fail <organ>` shows the cascade.",
           "", "```mermaid", mermaid(), "```", "",
           "| Organ | Body analogy | Job in Aureon | Needs | If it fails, these suffer | Capabilities | Projects |",
           "|---|---|---|---|---|---|---|"]
    for oid, (name, analogy, role, cids, needs) in ORGANS.items():
        hit = ", ".join(ORGANS[d][0] for d in ORGANS if d in dependents(oid)) or "-"
        nd = ", ".join(ORGANS[n][0] for n in needs) or "-"
        cn = "<br>".join(f"`{c}`" for c in cids)
        n = sum(len(caps[c]["members"]) for c in cids)
        out.append(f"| **{name}** | {analogy} | {role} | {nd} | {hit} | {cn} | {n} |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    (ROOT / "docs" / "ORGANISM.md").write_text(render(), encoding="utf-8")
    print("docs/ORGANISM.md written")
