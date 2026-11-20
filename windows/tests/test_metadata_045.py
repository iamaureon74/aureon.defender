"""0.4.5 metadata removal: orientation kept, new formats, files still decode, no tags remain."""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("AUREON_DATA", tempfile.mkdtemp())

from aureon_defender import clean, media_strip as ms  # noqa: E402

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")


def probe_tags(path):
    out = subprocess.run([FFPROBE, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
                         capture_output=True, text=True, timeout=60)
    if out.returncode:
        raise AssertionError("ffprobe failed: " + out.stderr)
    j = json.loads(out.stdout)
    tags = dict(j["format"].get("tags", {}))
    for st in j.get("streams", []):
        tags.update(st.get("tags", {}))
    return {k.lower(): v for k, v in tags.items()}


def decodes(path):
    r = subprocess.run([FFMPEG, "-v", "error", "-i", str(path), "-f", "null", "-"], capture_output=True, text=True, timeout=120)
    return r.returncode == 0 and not r.stderr.strip()


class Photos(unittest.TestCase):
    def test_jpeg_keeps_orientation_drops_gps(self):
        from PIL import Image
        im = Image.new("RGB", (40, 20), "red")
        exif = Image.Exif()
        exif[0x0112] = 6
        exif[0x010F] = "SecretCamCo"
        exif[0x0110] = "Model X serial 123"
        buf = io.BytesIO()
        im.save(buf, "JPEG", exif=exif.tobytes())
        d = Path(tempfile.mkdtemp())
        f = d / "p.jpg"
        f.write_bytes(buf.getvalue())
        res = clean.clean_file(f)
        out = Path(res["written"]).read_bytes()
        self.assertNotIn(b"SecretCamCo", out)
        self.assertNotIn(b"serial", out)
        self.assertEqual(ms.jpeg_orientation(out), 6)
        with Image.open(res["written"]) as im2:
            self.assertEqual(im2.getexif().get(0x0112), 6)
            self.assertEqual(dict(im2.getexif()), {0x0112: 6})

    def test_svg(self):
        d = Path(tempfile.mkdtemp())
        f = d / "a.svg"
        f.write_text('<svg xmlns="http://www.w3.org/2000/svg" inkscape:export-filename="C:\\Users\\alice\\x.png">'
                     '<!-- by alice --><metadata><rdf:RDF>alice</rdf:RDF></metadata><rect width="1" height="1"/></svg>')
        out = Path(clean.clean_file(f)["written"]).read_text()
        self.assertNotIn("alice", out)
        self.assertIn("<rect", out)

    def test_heic_without_plugin_is_explained_not_crash(self):
        d = Path(tempfile.mkdtemp())
        f = d / "a.heic"
        f.write_bytes(b"\0\0\0\x18ftypheic" + b"\0" * 64)
        with self.assertRaises(ValueError):
            clean.clean_file(f)
        with self.assertRaises(ValueError):
            clean.clean_file(f, in_place=True)


class Documents(unittest.TestCase):
    def test_docx_dates_rsids_accounts(self):
        d = Path(tempfile.mkdtemp())
        f = d / "a.docx"
        with zipfile.ZipFile(f, "w") as z:
            z.writestr("docProps/core.xml", '<cp:coreProperties><dc:creator>Alice</dc:creator>'
                       '<dcterms:created xsi:type="dcterms:W3CDTF">2024-05-01T10:11:12Z</dcterms:created></cp:coreProperties>')
            z.writestr("docProps/app.xml", "<Properties><TotalTime>731</TotalTime><Company>Acme</Company></Properties>")
            z.writestr("word/document.xml", '<w:document><w:p w:rsidR="00AB12CD" w:rsidRDefault="00AB12CD"/></w:document>')
            z.writestr("word/settings.xml", '<w:settings><w:rsids><w:rsidRoot w:val="00AB12CD"/></w:rsids></w:settings>')
            z.writestr("word/people.xml", '<w:people><w:presenceInfo w:providerId="AD" w:userId="alice@corp.example"/></w:people>')
        res = clean.clean_file(f)
        with zipfile.ZipFile(res["written"]) as z:
            blob = b"".join(z.read(n) for n in z.namelist())
        for leak in (b"Alice", b"2024-05-01", b"731", b"Acme", b"00AB12CD", b"alice@corp"):
            self.assertNotIn(leak, blob)

    def test_pdf_dates_hex_and_id(self):
        d = Path(tempfile.mkdtemp())
        f = d / "a.pdf"
        body = (b"%PDF-1.4\n1 0 obj<</Author(Alice)/CreationDate(D:20240501)/Producer<416C696365>>>endobj\n"
                b"trailer<</ID[<0123456789ABCDEF><0123456789ABCDEF>]>>\n%%EOF")
        f.write_bytes(body)
        out = Path(clean.clean_file(f)["written"]).read_bytes()
        self.assertEqual(len(out), len(body))                         # offsets preserved
        for leak in (b"Alice", b"20240501", b"416C696365", b"0123456789ABCDEF"):
            self.assertNotIn(leak, out)

    def test_encrypted_pdf_id_kept(self):
        data = b"<</Encrypt 5 0 R/ID[<AB><AB>]>>"
        self.assertEqual(ms.pdf_extras(data)[0], data)


class Archives(unittest.TestCase):
    def test_zip_times_and_comment(self):
        d = Path(tempfile.mkdtemp())
        f = d / "a.zip"
        with zipfile.ZipFile(f, "w") as z:
            z.comment = b"made by alice"
            zi = zipfile.ZipInfo("x.txt", date_time=(2024, 5, 1, 10, 11, 12))
            z.writestr(zi, "hello")
        res = clean.clean_file(f)
        with zipfile.ZipFile(res["written"]) as z:
            self.assertEqual(z.comment, b"")
            self.assertEqual(z.infolist()[0].date_time, (1980, 1, 1, 0, 0, 0))
            self.assertEqual(z.read("x.txt"), b"hello")


class Audio(unittest.TestCase):
    def test_mp3_ape(self):
        ape = b"APETAGEX" + (2000).to_bytes(4, "little") + (32).to_bytes(4, "little") + (0).to_bytes(4, "little") \
            + (0).to_bytes(4, "little") + b"\0" * 8
        data = b"\xff\xfb\x90\x00" + b"\0" * 100 + ape
        out, removed = ms.strip_apev2(data)
        self.assertEqual(out, data[:-32])
        self.assertEqual(removed, ["APE tags"])

    def test_ogg_crc_reference(self):
        # Ogg CRC of a known page header (all-zero CRC field) must match libogg's polynomial
        self.assertEqual(ms.ogg_crc(b""), 0)
        self.assertEqual(ms.ogg_crc(b"\x01"), 0x04C11DB7)


@unittest.skipUnless(FFMPEG and FFPROBE, "ffmpeg not installed")
class RealMedia(unittest.TestCase):
    def make(self, name, *args):
        d = Path(tempfile.mkdtemp())
        f = d / name
        cmd = [FFMPEG, "-v", "error", "-y", *args, "-metadata", "artist=Alice Secret", "-metadata", "comment=GPS 51.5,-0.1",
               "-metadata", "title=Private", str(f)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode:
            self.skipTest("ffmpeg can't encode " + name + ": " + r.stderr[-200:])
        self.assertIn("alice secret", {v.lower() for v in probe_tags(f).values()})
        return f

    def check(self, f):
        res = clean.clean_file(f)
        out = Path(res["written"])
        vals = " ".join(probe_tags(out).values()).lower()
        self.assertNotIn("alice", vals)
        self.assertNotIn("gps", vals)
        self.assertTrue(decodes(out), "cleaned file no longer decodes")
        return res

    def test_ogg_vorbis(self):
        self.check(self.make("a.ogg", "-f", "lavfi", "-i", "sine=d=1", "-c:a", "libvorbis"))

    def test_opus(self):
        self.check(self.make("a.opus", "-f", "lavfi", "-i", "sine=d=1", "-c:a", "libopus"))

    def test_aiff(self):
        self.check(self.make("a.aiff", "-f", "lavfi", "-i", "sine=d=1", "-write_id3v2", "1"))

    def test_mkv(self):
        self.check(self.make("a.mkv", "-f", "lavfi", "-i", "testsrc=d=1:s=64x48", "-f", "lavfi", "-i", "sine=d=1",
                             "-shortest", "-c:v", "mpeg4", "-c:a", "aac"))

    def test_webm(self):
        self.check(self.make("a.webm", "-f", "lavfi", "-i", "testsrc=d=1:s=64x48", "-c:v", "libvpx", "-b:v", "100k"))

    def test_mp4_and_timestamps(self):
        f = self.make("a.mp4", "-f", "lavfi", "-i", "testsrc=d=1:s=64x48", "-c:v", "mpeg4",
                      "-metadata", "creation_time=2024-05-01T10:11:12Z")
        res = self.check(f)
        tags = probe_tags(res["written"])
        self.assertNotIn("2024-05-01", " ".join(tags.values()))

    def test_flac_and_mp3(self):
        self.check(self.make("a.flac", "-f", "lavfi", "-i", "sine=d=1"))
        self.check(self.make("a.mp3", "-f", "lavfi", "-i", "sine=d=1"))


class EngineAutoClean(unittest.TestCase):
    def test_replace_mode_keeps_private_backup(self):
        os.environ["AUREON_DATA"] = tempfile.mkdtemp()
        from aureon_defender.engine import Engine
        e = Engine()
        e.s["auto_clean_mode"] = "replace"
        home = Path(tempfile.mkdtemp())
        dl = home / "Downloads"
        dl.mkdir()
        f = dl / "s.svg"
        f.write_text('<svg><!-- alice --><rect/></svg>')
        e.auto_clean(f)
        self.assertNotIn("alice", f.read_text())
        backups = list((home / "AppData/Local/Aureon/originals").iterdir())
        self.assertEqual(len(backups), 1)
        self.assertIn("alice", backups[0].read_text())
        self.assertFalse(list(dl.glob("*.clean*")))

    def test_backups_expire_without_daily_report(self):
        os.environ["AUREON_DATA"] = tempfile.mkdtemp()
        from aureon_defender.engine import Engine
        e = Engine()
        self.assertIn("backups", [t[0] for t in e.tasks])
        home = Path(tempfile.mkdtemp())
        b = home / "originals"
        b.mkdir()
        old = b / "old.jpg"
        old.write_text("x")
        os.utime(old, (0, 0))
        fresh = b / "new.jpg"
        fresh.write_text("y")
        from unittest import mock
        with mock.patch("aureon_defender.core.expand_all", return_value=[b]):
            e.purge_clean_backups()
        self.assertFalse(old.exists())
        self.assertTrue(fresh.exists())

    def test_settings_reject_bad_mode(self):
        from aureon_defender.core import Settings
        s = Settings(Path(tempfile.mkdtemp()) / "s.json")
        self.assertEqual(s.save({"auto_clean_mode": "shred"})["auto_clean_mode"], "replace")   # rejected: default stays
        self.assertEqual(s.save({"auto_clean_mode": "copy"})["auto_clean_mode"], "copy")
        self.assertEqual(s.save({"clean_backup_days": 0})["clean_backup_days"], 7)


if __name__ == "__main__":
    unittest.main()
