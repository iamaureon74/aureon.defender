"""Hidden branches, content credentials and lossless savings. Pixels must not change."""
import io
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image  # noqa: E402

from aureon_defender import fingerprint  # noqa: E402
from aureon_defender.clean import clean_file  # noqa: E402


def photo(fmt, **kw):
    im = Image.new("RGB", (160, 120))
    im.putdata([((x * 7) % 256, (y * 5) % 256, (x * y) % 256) for y in range(120) for x in range(160)])
    b = io.BytesIO()
    im.save(b, fmt, **kw)
    return b.getvalue(), im


def png_chunk(t, body):
    return struct.pack(">I", len(body)) + t + body + struct.pack(">I", zlib.crc32(t + body) & 0xFFFFFFFF)


class Branches(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_motion_photo_video_and_mpf_are_removed_pixels_identical(self):
        jpg, _ = photo("JPEG", quality=90)
        icc = b"\xff\xe2" + struct.pack(">H", 2 + 14 + 4) + b"ICC_PROFILE\0\x01\x01" + b"abcd"
        mpf = b"\xff\xe2" + struct.pack(">H", 2 + 4 + 8) + b"MPF\0" + b"II*\0\x08\0\0\0"
        video = b"\0\0\0\x18ftypmp42" + b"\0" * 5000
        data = jpg[:2] + icc + mpf + jpg[2:] + video
        f = self.tmp / "PXL_20260101_motion.jpg"
        f.write_bytes(data)
        res = clean_file(f, in_place=True)
        out = f.read_bytes()
        self.assertIn("embedded motion-photo video", res["removed"])
        self.assertIn("multi-picture index (MPF)", res["removed"])
        self.assertIn(b"ICC_PROFILE", out)                       # colour profile kept: no quality loss
        self.assertNotIn(b"ftypmp42", out)
        self.assertTrue(out.endswith(b"\xff\xd9"))
        self.assertLess(len(out), len(data) - 5000)
        self.assertEqual(Image.open(io.BytesIO(out)).convert("RGB").tobytes(), Image.open(io.BytesIO(jpg)).convert("RGB").tobytes())

    def test_png_credentials_vendor_chunks_and_slack_go_pixels_identical(self):
        raw, im = photo("PNG", compress_level=1)
        iend = raw.rindex(b"IEND") - 4
        extra = png_chunk(b"caBX", b"c2pa manifest with device id") + png_chunk(b"tEXt", b"Author\0me") + png_chunk(b"mkBF", b"fireworks")
        data = raw[:iend] + extra + raw[iend:] + b"trailing"
        f = self.tmp / "shot.png"
        f.write_bytes(data)
        res = clean_file(f, in_place=True)
        out = f.read_bytes()
        joined = " ".join(res["removed"])
        self.assertIn("content credentials (C2PA)", joined)
        self.assertIn("mkBF", joined)
        self.assertIn("slack compression", joined)
        self.assertNotIn(b"caBX", out)
        self.assertNotIn(b"trailing", out)
        self.assertLess(len(out), len(raw))                       # smaller than the original image alone
        self.assertEqual(Image.open(io.BytesIO(out)).convert("RGB").tobytes(), im.tobytes())

    def test_mp4_c2pa_box_blanked_size_unchanged(self):
        box = struct.pack(">I", 8 + 16 + 12) + b"uuid" + fingerprint.C2PA_UUID + b"manifest-xyz"
        data = struct.pack(">I", 16) + b"ftypisom" + b"\0" * 4 + box + struct.pack(">I", 8) + b"mdat"
        out, removed = fingerprint.mp4(data)
        self.assertEqual(len(out), len(data))
        self.assertIn("content credentials (C2PA)", removed)
        self.assertNotIn(b"manifest-xyz", out)

    def test_clean_jpeg_without_branches_is_untouched_by_pass(self):
        jpg, _ = photo("JPEG")
        out, removed = fingerprint.jpeg(jpg)
        self.assertEqual(out, jpg)
        self.assertEqual(removed, [])


if __name__ == "__main__":
    unittest.main()
