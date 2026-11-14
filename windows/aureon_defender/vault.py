"""Password vault on this PC, encrypted twice over:

  1. a key derived from your PIN (PBKDF2-SHA256, 600,000 rounds, random salt), mixed into
  2. Windows DPAPI, which binds the data to your Windows account on this machine.

Copying the vault file to another PC, or to another Windows account, gives nothing; on this account it still needs
the PIN. Nothing is ever sent anywhere. Wrong PINs are counted and slowed down.
"""
import base64
import ctypes
import hashlib
import json
import os
import secrets
import time
from ctypes import wintypes
from pathlib import Path

from .core import user_dir

ROUNDS = 600_000


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data):
    buf = ctypes.create_string_buffer(data, len(data))
    return _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf


def _dpapi(data, entropy, protect):
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    src, _a = _blob(data)
    ent, _b = _blob(entropy)
    out = _Blob()
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    args = (ctypes.byref(src), "aureon vault" if protect else None, ctypes.byref(ent), None, None, 0x1, ctypes.byref(out))
    if not fn(*args):                                   # 0x1 = CRYPTPROTECT_UI_FORBIDDEN
        raise PermissionError("wrong PIN, or the vault belongs to another Windows account")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)


class Vault:
    def __init__(self, path=None):
        self.path = Path(path or (user_dir() / "vault.aureon"))

    def exists(self):
        return self.path.exists()

    def _key(self, pin, salt):
        return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, ROUNDS)

    def _read(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def create(self, pin):
        if len(pin) < 4:
            raise ValueError("use at least 4 characters")
        if self.exists():
            raise ValueError("a vault already exists")
        self._write(pin, [], secrets.token_bytes(16))

    def _write(self, pin, entries, salt):
        blob = _dpapi(json.dumps(entries).encode("utf-8"), self._key(pin, salt), True)
        state = {"v": 1, "salt": base64.b64encode(salt).decode(), "blob": base64.b64encode(blob).decode(), "fails": 0, "locked_until": 0}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state), encoding="utf-8")
        os.replace(tmp, self.path)

    def open(self, pin):
        st = self._read()
        if time.time() < st.get("locked_until", 0):
            raise PermissionError(f"too many wrong PINs; try again in {int(st['locked_until'] - time.time())} s")
        salt = base64.b64decode(st["salt"])
        try:
            data = _dpapi(base64.b64decode(st["blob"]), self._key(pin, salt), False)
        except PermissionError:
            st["fails"] = st.get("fails", 0) + 1
            if st["fails"] >= 5:
                st["locked_until"] = time.time() + 30 * 2 ** min(st["fails"] - 5, 6)   # 30 s, doubling
            self.path.write_text(json.dumps(st), encoding="utf-8")
            raise
        if st.get("fails"):
            st["fails"] = 0
            self.path.write_text(json.dumps(st), encoding="utf-8")
        return json.loads(data), salt

    def list(self, pin):
        entries, _ = self.open(pin)
        return [{k: v for k, v in e.items() if k != "password"} | {"id": e["id"]} for e in entries]

    def reveal(self, pin, eid):
        entries, _ = self.open(pin)
        return next((e["password"] for e in entries if e["id"] == eid), None)

    def add(self, pin, site, username, password, note=""):
        entries, salt = self.open(pin)
        e = {"id": secrets.token_hex(6), "site": site, "username": username, "password": password, "note": note, "t": time.time()}
        entries.append(e)
        self._write(pin, entries, salt)
        return e["id"]

    def delete(self, pin, eid):
        entries, salt = self.open(pin)
        self._write(pin, [e for e in entries if e["id"] != eid], salt)

    def import_csv(self, pin, text):
        """Chrome / Edge / Brave / Firefox / Bitwarden CSV exports: name/url, username, password columns."""
        import csv
        import io
        rows = list(csv.DictReader(io.StringIO(text)))
        entries, salt = self.open(pin)
        n = 0
        for r in rows:
            low = {k.lower().strip(): v for k, v in r.items() if k}
            pw = low.get("password") or low.get("login_password")
            if not pw:
                continue
            entries.append({"id": secrets.token_hex(6), "site": low.get("url") or low.get("name") or low.get("login_uri") or "",
                            "username": low.get("username") or low.get("login_username") or "", "password": pw, "note": "", "t": time.time()})
            n += 1
        self._write(pin, entries, salt)
        return n

    def change_pin(self, old, new):
        entries, _ = self.open(old)
        if len(new) < 4:
            raise ValueError("use at least 4 characters")
        self._write(new, entries, secrets.token_bytes(16))


def generate(length=20):
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789-_.!@#%"
    return "".join(secrets.choice(alphabet) for _ in range(length))
