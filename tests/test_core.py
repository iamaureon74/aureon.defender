"""Catalog, capability map, organism graph, profiles and CLI."""
import configparser
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aureon import organism  # noqa: E402
from aureon.profiles import PROFILES  # noqa: E402

STACK = json.loads((ROOT / "stack.json").read_text(encoding="utf-8"))
CAPS = json.loads((ROOT / "capabilities.json").read_text(encoding="utf-8"))


def aureon(*args):
    return subprocess.run([sys.executable, "-m", "aureon", *args], cwd=ROOT, capture_output=True, text=True, timeout=120)


class Catalog(unittest.TestCase):
    def test_every_project_has_exactly_one_capability(self):
        repos = [m["repo"] for c in CAPS for m in c["members"]]
        self.assertEqual(len(repos), 790)
        self.assertEqual(len(set(repos)), 790)
        self.assertTrue(all(m["best"] for c in CAPS for m in c["members"]))

    def test_every_capability_explains_fusion_and_location(self):
        for c in CAPS:
            self.assertGreater(len(c["fused"]), 30, c["id"])
            self.assertTrue(c["realised"], c["id"])

    def test_picks_are_pinned_and_mapped(self):
        mapped = {m["repo"] for c in CAPS for m in c["members"]}
        for s in STACK:
            self.assertRegex(s["commit"] or "", r"^[0-9a-f]{40}$", s["repo"])
            self.assertIn(s["repo"], mapped)
        self.assertEqual(sum(m["picked"] for c in CAPS for m in c["members"]), len(STACK))

    def test_gitmodules_match_stack(self):
        cp = configparser.ConfigParser()
        cp.read(ROOT / ".gitmodules", encoding="utf-8")
        paths = {cp[s]["path"] for s in cp.sections()}
        self.assertEqual(paths, {s["path"] for s in STACK})
        out = subprocess.run(["git", "ls-files", "-s", "upstream"], cwd=ROOT, capture_output=True, text=True).stdout
        pinned = {l.split("\t")[1]: l.split()[1] for l in out.splitlines() if l.startswith("160000")}
        for s in STACK:
            self.assertEqual(pinned.get(s["path"]), s["commit"], s["path"])


class Organism(unittest.TestCase):
    def test_graph_is_valid_and_covers_all_capabilities(self):
        self.assertTrue(organism.check_graph())

    def test_dependents_cascade(self):
        self.assertIn("immune", organism.dependents("blood"))
        self.assertIn("liver", organism.dependents("blood"))      # via immune
        self.assertEqual(organism.dependents("liver"), set())      # leaf organ
        self.assertEqual(len(organism.dependents("skeleton")), len(organism.ORGANS) - 2)  # all but dna + itself

    def test_impaired_reports_missing_dependency(self):
        v = {o: ("alive", "") for o in organism.ORGANS}
        v["nerves"] = ("absent", "")
        imp = organism.impaired(v)
        self.assertEqual(imp["brain"], {"nerves"})
        self.assertEqual(imp["reflex"], {"nerves"})
        self.assertNotIn("skin", imp)

    def test_organism_doc_up_to_date(self):
        sys.path.insert(0, str(ROOT / "tools"))
        from build_organism_doc import render
        self.assertEqual((ROOT / "docs/ORGANISM.md").read_text(encoding="utf-8"), render(),
                         "run python tools/build_organism_doc.py")

    def test_mermaid(self):
        g = organism.mermaid()
        self.assertTrue(g.startswith("graph TD"))
        self.assertIn("nerves --> brain", g)


class Profiles(unittest.TestCase):
    def test_profile_components_exist_in_stack(self):
        repos = {s["repo"] for s in STACK}
        for name, p in PROFILES.items():
            for title, layer, comps, how in p["steps"]:
                for c in comps:
                    self.assertIn(c, repos, f"{name}: {title}")
                self.assertTrue(how)

    def test_lab_profile_is_only_audit_layer_tools(self):
        self.assertTrue(all(step[1] == "audit" for step in PROFILES["lab"]["steps"]))


class CLI(unittest.TestCase):
    def test_help_lists_all_commands(self):
        r = aureon("--help")
        for c in ("caps", "body", "rf", "rescue", "analyst", "hidguard", "mesh", "audit", "plan", "fetch"):
            self.assertIn(c, r.stdout)

    def test_caps(self):
        r = aureon("caps")
        self.assertEqual(r.returncode, 0)
        self.assertIn("53 capabilities from 790 projects", r.stdout)
        r = aureon("caps", "wireless-watch")
        self.assertIn("kalibrate-rtl", r.stdout)
        self.assertEqual(aureon("caps", "nope").returncode, 2)

    def test_plans(self):
        for p in PROFILES:
            r = aureon("plan", p)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn(" 1. [", r.stdout)

    def test_components_filter(self):
        r = aureon("components", "--layer", "defend", "--platform", "android")
        self.assertIn("mvt-project/mvt", r.stdout)

    def test_audit_json(self):
        r = aureon("audit", "--json")
        rep = json.loads(r.stdout)
        self.assertIn("results", rep)
        self.assertTrue(all(x["status"] in ("PASS", "WARN", "FAIL", "INFO", "SKIP") for x in rep["results"]))

    def test_body_json_and_fail(self):
        r = aureon("body", "--json")
        v = json.loads(r.stdout)
        self.assertEqual(set(v), set(organism.ORGANS))
        r = aureon("body", "--fail", "heart")
        self.assertIn("Brain", r.stdout)


if __name__ == "__main__":
    unittest.main()
