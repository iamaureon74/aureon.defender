"""Quarantine: files are moved into the vault, XOR-scrambled so they can't run or be re-detected,
with metadata to restore them exactly."""
import json
import os
import shutil
import time
import uuid
from pathlib import Path

from .core import data_dir

KEY = bytes(range(37, 37 + 64))


def _xor(src, dst):
    with open(src, "rb") as fi, open(dst, "wb") as fo:
        i = 0
        for chunk in iter(lambda: fi.read(1 << 20), b""):
            fo.write(bytes(b ^ KEY[(i + n) % len(KEY)] for n, b in enumerate(chunk)))
            i += len(chunk)


class Vault:
    def __init__(self, root: Path = None):
        self.root = root or (data_dir() / "quarantine")
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, path, result):
        path = Path(path)
        qid = uuid.uuid4().hex[:12]
        _xor(path, self.root / f"{qid}.bin")
        meta = {"id": qid, "original": str(path), "sha256": result.get("sha256"), "size": result.get("size"),
                "reasons": result.get("reasons", []), "verdict": result.get("verdict"), "t": time.time()}
        (self.root / f"{qid}.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        try:
            os.chmod(path, 0o666)
            path.unlink()
        except OSError:
            (self.root / f"{qid}.bin").unlink(missing_ok=True)
            (self.root / f"{qid}.json").unlink(missing_ok=True)
            raise
        return meta

    def list(self):
        out = []
        for p in sorted(self.root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                out.append(json.loads(p.read_text(encoding="utf-8")))
            except ValueError:
                pass
        return out

    def restore(self, qid, to=None):
        meta = json.loads((self.root / f"{qid}.json").read_text(encoding="utf-8"))
        dst = Path(to or meta["original"])
        if dst.exists():
            dst = dst.with_name(dst.stem + ".restored" + dst.suffix)
        dst.parent.mkdir(parents=True, exist_ok=True)
        _xor(self.root / f"{qid}.bin", dst)
        self.delete(qid)
        return str(dst)

    def delete(self, qid):
        for ext in (".bin", ".json"):
            (self.root / f"{qid}{ext}").unlink(missing_ok=True)

    def purge_older(self, days=30):
        cut = time.time() - days * 86400
        for m in self.list():
            if m["t"] < cut:
                self.delete(m["id"])

    def export(self, qid, dst):
        shutil.copy(self.root / f"{qid}.bin", dst)
