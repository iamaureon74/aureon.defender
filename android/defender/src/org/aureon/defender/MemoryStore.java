package org.aureon.defender;

import java.io.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.zip.*;

/**
 * Native fold-memory for Android (same idea as aureon.fold-memory, no Python needed). Plain java.io, no Android
 * imports, so it is unit-tested on a desktop JVM.
 *
 *  - files are cut where the bytes say (gear rolling hash, 2 KiB min / 8 KiB average / 64 KiB max), so an edit
 *    only changes nearby bites; every bite is named by its SHA-256 and stored once, deflated when that helps.
 *  - every path keeps its versions (newest first). A version only comes back if each bite and the whole file
 *    still match their fingerprints; otherwise restore refuses and nothing half-written is left.
 *  - index.tsv is rewritten atomically; chunks/ and files/ only ever gain content until prune + gc.
 */
public final class MemoryStore {
    public static final int MIN = 2048, AVG_MASK = (1 << 13) - 1, MAX = 65536;
    private static final long[] GEAR = new long[256];
    static { long x = 0x9E3779B97F4A7C15L; for (int i = 0; i < 256; i++) { x ^= x << 13; x ^= x >>> 7; x ^= x << 17; GEAR[i] = x; } }

    public static final class Version { public final String sha; public final long size, mtime, held; Version(String s, long z, long m, long h) { sha = s; size = z; mtime = m; held = h; } }

    private final File root, chunks, manifests, index;
    private final Map<String, List<Version>> paths = new TreeMap<>();

    public MemoryStore(File root) throws IOException {
        this.root = root; chunks = new File(root, "chunks"); manifests = new File(root, "files"); index = new File(root, "index.tsv");
        if (!chunks.isDirectory() && !chunks.mkdirs()) throw new IOException("cannot create memory store");
        if (!manifests.isDirectory() && !manifests.mkdirs()) throw new IOException("cannot create memory store");
        load();
    }

    // ---------------- index ----------------
    private void load() throws IOException {
        if (!index.exists()) return;
        try (BufferedReader r = new BufferedReader(new InputStreamReader(new FileInputStream(index), "UTF-8"))) {
            String line;
            while ((line = r.readLine()) != null) {
                String[] f = line.split("\t");
                if (f.length != 5 || !f[1].matches("[0-9a-f]{64}")) continue;
                paths.computeIfAbsent(unescape(f[0]), k -> new ArrayList<>()).add(new Version(f[1], Long.parseLong(f[2]), Long.parseLong(f[3]), Long.parseLong(f[4])));
            }
        }
    }

    public void save() throws IOException {
        File tmp = new File(root, "index.tmp");
        try (Writer w = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(tmp), "UTF-8"))) {
            for (Map.Entry<String, List<Version>> e : paths.entrySet())
                for (Version v : e.getValue()) w.write(escape(e.getKey()) + "\t" + v.sha + "\t" + v.size + "\t" + v.mtime + "\t" + v.held + "\n");
        }
        if (!tmp.renameTo(index)) { if (!index.delete() || !tmp.renameTo(index)) throw new IOException("cannot commit memory index"); }
    }

    private static String escape(String s) { return s.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n"); }
    private static String unescape(String s) { StringBuilder b = new StringBuilder(); for (int i = 0; i < s.length(); i++) { char c = s.charAt(i); if (c == '\\' && i + 1 < s.length()) { char n = s.charAt(++i); b.append(n == 't' ? '\t' : n == 'n' ? '\n' : n); } else b.append(c); } return b.toString(); }

    public List<Version> versions(String path) { List<Version> v = paths.get(path); return v == null ? Collections.<Version>emptyList() : Collections.unmodifiableList(v); }
    public Set<String> paths() { return Collections.unmodifiableSet(paths.keySet()); }

    /** true when the newest held version at `path` has this size and date (no read needed). */
    public boolean unchanged(String path, long size, long mtime) { List<Version> v = paths.get(path); return v != null && !v.isEmpty() && v.get(0).size == size && v.get(0).mtime == mtime; }

    // ---------------- folding ----------------
    /** Fold one file. Returns "new", "same" (bytes identical to the newest version) or "unchanged". */
    public String fold(String path, InputStream in, long size, long mtime, long now) throws Exception {
        if (unchanged(path, size, mtime)) return "unchanged";
        MessageDigest whole = MessageDigest.getInstance("SHA-256");
        List<String> list = new ArrayList<>();
        byte[] buf = new byte[MAX], b = new byte[65536];
        int len = 0, n; long h = 0, total = 0;
        BufferedInputStream bin = new BufferedInputStream(in, 65536);
        while ((n = bin.read(b)) > 0) {
            whole.update(b, 0, n); total += n;
            for (int i = 0; i < n; i++) {
                buf[len++] = b[i];
                h = (h << 1) + GEAR[b[i] & 255];
                if ((len >= MIN && (h & AVG_MASK) == 0) || len == MAX) { list.add(putChunk(buf, len)); len = 0; h = 0; }
            }
        }
        if (len > 0) list.add(putChunk(buf, len));
        String sha = hex(whole.digest());
        File man = new File(manifests, sha);
        if (!man.exists()) { File t = new File(manifests, sha + ".tmp"); try (Writer w = new OutputStreamWriter(new FileOutputStream(t), "UTF-8")) { w.write(total + "\n"); for (String c : list) w.write(c + "\n"); } if (!t.renameTo(man)) throw new IOException("manifest"); }
        List<Version> v = paths.computeIfAbsent(path, k -> new ArrayList<>());
        if (!v.isEmpty() && v.get(0).sha.equals(sha)) { v.set(0, new Version(sha, total, mtime, v.get(0).held)); return "same"; }
        v.add(0, new Version(sha, total, mtime, now));
        return "new";
    }

    private String putChunk(byte[] buf, int len) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-256"); md.update(buf, 0, len);
        String sha = hex(md.digest());
        File dir = new File(chunks, sha.substring(0, 2)), f = new File(dir, sha);
        if (f.exists()) return sha;
        if (!dir.isDirectory() && !dir.mkdirs()) throw new IOException("chunk folder");
        Deflater d = new Deflater(6); d.setInput(buf, 0, len); d.finish();
        byte[] out = new byte[len + 64]; int z = d.deflate(out); boolean packed = d.finished() && z < len; d.end();
        File t = new File(dir, sha + ".tmp");
        try (OutputStream o = new FileOutputStream(t)) { o.write(packed ? 'Z' : 'R'); if (packed) o.write(out, 0, z); else o.write(buf, 0, len); }
        if (!t.renameTo(f)) throw new IOException("chunk commit");
        return sha;
    }

    // ---------------- reading ----------------
    /** Write version `sha` to dest, checking every bite and the whole file first. Throws and leaves dest untouched on a mismatch. */
    public void restore(String sha, File dest) throws Exception {
        File man = new File(manifests, sha);
        if (!man.exists()) throw new IOException("not held: " + sha);
        File tmp = new File(dest.getParentFile(), "." + dest.getName() + ".aureon-restore");
        MessageDigest whole = MessageDigest.getInstance("SHA-256");
        try (BufferedReader r = new BufferedReader(new InputStreamReader(new FileInputStream(man), "UTF-8")); OutputStream o = new BufferedOutputStream(new FileOutputStream(tmp))) {
            r.readLine();
            String c;
            while ((c = r.readLine()) != null) { byte[] data = chunk(c); whole.update(data); o.write(data); }
        } catch (Exception e) { tmp.delete(); throw e; }
        if (!hex(whole.digest()).equals(sha)) { tmp.delete(); throw new IOException("refused: fingerprint does not match"); }
        if (!tmp.renameTo(dest)) { if (!dest.delete() || !tmp.renameTo(dest)) { tmp.delete(); throw new IOException("cannot write " + dest); } }
    }

    /** First bytes of a held version (for the encrypted-or-not check). */
    public byte[] head(String sha, int max) throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        try (BufferedReader r = new BufferedReader(new InputStreamReader(new FileInputStream(new File(manifests, sha)), "UTF-8"))) {
            r.readLine(); String c;
            while (out.size() < max && (c = r.readLine()) != null) out.write(chunk(c));
        }
        byte[] b = out.toByteArray(); return b.length > max ? Arrays.copyOf(b, max) : b;
    }

    private byte[] chunk(String sha) throws Exception {
        File f = new File(new File(chunks, sha.substring(0, 2)), sha);
        byte[] raw; try (InputStream in = new FileInputStream(f)) { raw = readAll(in); }
        byte[] data;
        if (raw.length > 0 && raw[0] == 'Z') try { Inflater inf = new Inflater(); inf.setInput(raw, 1, raw.length - 1); ByteArrayOutputStream o = new ByteArrayOutputStream(); byte[] b = new byte[65536]; while (!inf.finished()) { int n = inf.inflate(b); if (n == 0 && (inf.needsInput() || inf.needsDictionary())) break; o.write(b, 0, n); } inf.end(); data = o.toByteArray(); } catch (DataFormatException e) { throw new IOException("refused: a stored bite is damaged"); }
        else data = Arrays.copyOfRange(raw, 1, raw.length);
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        if (!hex(md.digest(data)).equals(sha)) throw new IOException("refused: a stored bite is damaged");
        return data;
    }

    // ---------------- space ----------------
    /** Keep the newest `keep` versions per path, then delete bites nothing points at. Returns bytes freed. */
    public long prune(int keep) throws Exception {
        for (List<Version> v : paths.values()) while (v.size() > Math.max(1, keep)) v.remove(v.size() - 1);
        save();
        Set<String> liveFiles = new HashSet<>(), liveChunks = new HashSet<>();
        for (List<Version> v : paths.values()) for (Version x : v) liveFiles.add(x.sha);
        long freed = 0;
        File[] mans = manifests.listFiles();
        if (mans != null) for (File m : mans) {
            if (liveFiles.contains(m.getName())) { try (BufferedReader r = new BufferedReader(new InputStreamReader(new FileInputStream(m), "UTF-8"))) { r.readLine(); String c; while ((c = r.readLine()) != null) liveChunks.add(c); } }
            else { freed += m.length(); m.delete(); }
        }
        File[] dirs = chunks.listFiles();
        if (dirs != null) for (File d : dirs) { File[] fs = d.listFiles(); if (fs != null) for (File f : fs) if (!liveChunks.contains(f.getName())) { freed += f.length(); f.delete(); } }
        return freed;
    }

    public long diskBytes() { return size(root); }
    public int oldVersions() { int n = 0; for (List<Version> v : paths.values()) n += Math.max(0, v.size() - 1); return n; }
    private static long size(File f) { if (f.isFile()) return f.length(); long s = 0; File[] k = f.listFiles(); if (k != null) for (File x : k) s += size(x); return s; }

    public static double entropy(byte[] b) { if (b.length == 0) return 0; int[] c = new int[256]; for (byte x : b) c[x & 255]++; double e = 0; for (int k : c) if (k > 0) { double p = (double) k / b.length; e -= p * Math.log(p) / Math.log(2); } return e; }
    static String hex(byte[] d) { StringBuilder s = new StringBuilder(); for (byte x : d) s.append(String.format(Locale.ROOT, "%02x", x & 255)); return s.toString(); }
    static byte[] readAll(InputStream in) throws IOException { ByteArrayOutputStream o = new ByteArrayOutputStream(); byte[] b = new byte[65536]; int n; while ((n = in.read(b)) > 0) o.write(b, 0, n); return o.toByteArray(); }
}
