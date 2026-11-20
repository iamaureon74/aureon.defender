package org.aureon.defender;

import android.app.*;
import android.content.*;
import android.os.*;
import java.io.*;
import java.util.*;

/**
 * Silent memory on Android: photos, pictures and documents kept on the phone with their earlier versions.
 * Runs inside the existing 15-minute audit; folds at most once an hour (scaled by the hardware budget), only
 * when charging or above 40% battery, not when hot or in battery saver, and only with at least 10% free space.
 * Capped at 15% of free space. Needs "all files access" (the same one-time switch the shield uses).
 *
 * Ransomware undo: before a changed file is folded, its new bytes are compared with the version held. Five or
 * more plain files turning into encrypted-looking bytes (or vanishing next to an encrypted name.ext.* twin) in one
 * pass is treated as an attack: those files are put back from memory and the encrypted copies deleted.
 */
public final class Memory {
    private Memory() {}
    static final double ENCRYPTED = 7.2, PLAIN = 6.6;
    static final int ATTACK = 5;

    public static File store(Context c) { return new File(c.getFilesDir(), "memory"); }

    public static List<File> folders() {
        File ext = Environment.getExternalStorageDirectory();
        List<File> out = new ArrayList<>();
        for (String d : new String[]{Environment.DIRECTORY_DCIM, Environment.DIRECTORY_PICTURES, Environment.DIRECTORY_DOCUMENTS}) {
            File f = new File(ext, d); if (f.isDirectory()) out.add(f);
        }
        return out;
    }

    public static synchronized void attempt(Context c) {
        SharedPreferences p = c.getSharedPreferences("guard", 0);
        try {
            if (!p.getBoolean("memory", true) || Build.VERSION.SDK_INT < 30 || !Environment.isExternalStorageManager()) return;
            int[] b = Shield.budget(c);
            double scale = b[0] == 0 ? 1.6 : b[0] == 1 ? 1.0 : 0.75;
            long now = System.currentTimeMillis();
            if (now - p.getLong("memory_last", 0) < (long) (3600_000 * scale)) return;
            String why = whyNot(c, b);
            if (!why.isEmpty()) { p.edit().putString("memory_skipped", why).putLong("memory_last", now - (long) (3000_000 * scale)).apply(); return; }
            Result r = run(store(c), folders(), b[1] * 4, b[0] == 0 ? 256L << 20 : 1L << 30, cap(c), now);
            SharedPreferences.Editor e = p.edit().remove("memory_skipped").putLong("memory_last", now).putInt("memory_files", r.held)
                .putInt("memory_versions", r.versions).putLong("memory_disk", r.disk).putInt("memory_new", r.folded);
            if (!r.restored.isEmpty()) {
                e.putInt("memory_undo_count", r.restored.size()).putLong("memory_undo_t", now);
                notifyUndo(c, r.restored.size());
            }
            e.apply();
        } catch (Exception ex) {
            p.edit().putString("memory_skipped", "error: " + ex.getClass().getSimpleName()).apply();
        }
    }

    static String whyNot(Context c, int[] b) {
        BatteryManager bm = (BatteryManager) c.getSystemService(Context.BATTERY_SERVICE);
        int pct = bm == null ? 100 : bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY);
        if (bm != null && !bm.isCharging() && pct >= 0 && pct < 40) return "on battery below 40%";
        if (b[3] == 1) return "phone is hot or saving battery";
        StatFs s = new StatFs(c.getFilesDir().getAbsolutePath());
        if (s.getAvailableBytes() < Math.max(2L << 30, s.getTotalBytes() / 10)) return "less than 10% of storage is free";
        return "";
    }

    static long cap(Context c) {
        StatFs s = new StatFs(c.getFilesDir().getAbsolutePath());
        return (long) ((s.getAvailableBytes() + size(store(c))) * 0.15);
    }

    public static final class Result { public int folded, held, versions; public long disk; public final List<String> restored = new ArrayList<>(); }

    /** The whole pass, Android-free so it is tested on a desktop JVM. */
    public static Result run(File storeDir, List<File> roots, int maxFiles, long maxBytes, long capBytes, long now) throws Exception {
        MemoryStore m = new MemoryStore(storeDir);
        Result r = new Result();
        List<File[]> suspects = new ArrayList<>();          // {file, victim}
        Set<String> seen = new HashSet<>();
        int n = 0;
        ArrayDeque<File> q = new ArrayDeque<>(roots);
        while (!q.isEmpty() && n < maxFiles) {
            File[] kids = q.removeFirst().listFiles();
            if (kids == null) continue;
            for (File f : kids) {
                if (f.getName().startsWith(".")) continue;
                if (f.isDirectory()) { q.add(f); continue; }
                if (f.length() > maxBytes || n >= maxFiles) continue;
                n++;
                String path = f.getAbsolutePath(); seen.add(path);
                if (m.unchanged(path, f.length(), f.lastModified())) continue;
                List<MemoryStore.Version> held = m.versions(path);
                if (!held.isEmpty() && looksEncrypted(f) && MemoryStore.entropy(m.head(held.get(0).sha, 65536)) < PLAIN) { suspects.add(new File[]{f, f}); continue; }
                try (InputStream in = new FileInputStream(f)) { if ("new".equals(m.fold(path, in, f.length(), f.lastModified(), now))) r.folded++; }
                catch (IOException ignored) {}
            }
        }
        for (String path : m.paths()) {                      // held files that vanished next to an encrypted twin
            File f = new File(path);
            if (seen.contains(path) || f.exists() || f.getParentFile() == null || !under(path, roots)) continue;
            File[] twins = f.getParentFile().listFiles((d, name) -> name.startsWith(f.getName() + "."));
            if (twins != null) for (File t : twins) if (looksEncrypted(t)) { suspects.add(new File[]{f, t}); break; }
        }
        if (suspects.size() >= ATTACK) {
            for (File[] s : suspects) {
                List<MemoryStore.Version> v = m.versions(s[0].getAbsolutePath());
                if (v.isEmpty()) continue;
                try { m.restore(v.get(0).sha, s[0]); if (s[1] != s[0]) s[1].delete(); r.restored.add(s[0].getAbsolutePath()); } catch (Exception ignored) {}
            }
        } else {
            for (File[] s : suspects) if (s[0] == s[1]) try (InputStream in = new FileInputStream(s[0])) { if ("new".equals(m.fold(s[0].getAbsolutePath(), in, s[0].length(), s[0].lastModified(), now))) r.folded++; } catch (IOException ignored) {}
        }
        m.save();
        for (int keep : new int[]{10, 5, 2}) { if (m.diskBytes() <= capBytes) break; m.prune(keep); }
        r.held = m.paths().size(); r.versions = m.oldVersions(); r.disk = m.diskBytes();
        return r;
    }

    static boolean looksEncrypted(File f) {
        try (InputStream in = new FileInputStream(f)) { byte[] b = new byte[65536]; int n = in.read(b); return n >= 256 && MemoryStore.entropy(Arrays.copyOf(b, n)) >= ENCRYPTED; }
        catch (IOException e) { return false; }
    }

    static boolean under(String path, List<File> roots) { for (File r : roots) if (path.startsWith(r.getAbsolutePath() + File.separator)) return true; return false; }

    /** Save the version before the newest as "name (earlier).ext" beside the file. The current file is not touched. */
    public static File keepEarlier(Context c, String path) throws Exception {
        MemoryStore m = new MemoryStore(store(c));
        List<MemoryStore.Version> v = m.versions(path);
        if (v.size() < 2) throw new IOException("no earlier version held");
        File f = new File(path); String name = f.getName(); int dot = name.lastIndexOf('.');
        File out = new File(f.getParentFile(), dot > 0 ? name.substring(0, dot) + " (earlier)" + name.substring(dot) : name + " (earlier)");
        m.restore(v.get(1).sha, out);
        return out;
    }

    public static List<String> recentlyChanged(Context c, int limit) {
        try {
            MemoryStore m = new MemoryStore(store(c));
            List<String> out = new ArrayList<>(); List<long[]> order = new ArrayList<>(); List<String> names = new ArrayList<>();
            for (String p : m.paths()) { List<MemoryStore.Version> v = m.versions(p); if (v.size() >= 2) { names.add(p); order.add(new long[]{v.get(0).held, names.size() - 1}); } }
            order.sort((a, b2) -> Long.compare(b2[0], a[0]));
            for (int i = 0; i < Math.min(limit, order.size()); i++) out.add(names.get((int) order.get(i)[1]));
            return out;
        } catch (Exception e) { return Collections.emptyList(); }
    }

    private static void notifyUndo(Context c, int n) {
        NotificationManager nm = c.getSystemService(NotificationManager.class);
        if (nm == null) return;
        NotificationChannel ch = new NotificationChannel("removed", "Removed threats", NotificationManager.IMPORTANCE_LOW);
        ch.setSound(null, null); nm.createNotificationChannel(ch);
        nm.notify(7302, new Notification.Builder(c, "removed").setSmallIcon(android.R.drawable.ic_lock_lock)
            .setContentTitle("put back " + n + " file" + (n == 1 ? "" : "s") + " from memory")
            .setContentText("they were being encrypted. the versions from before were restored and checked.")
            .setContentIntent(PendingIntent.getActivity(c, 3, new Intent(c, MainActivity.class), PendingIntent.FLAG_IMMUTABLE)).setAutoCancel(true).build());
    }

    private static long size(File f) { if (f.isFile()) return f.length(); long s = 0; File[] k = f.listFiles(); if (k != null) for (File x : k) s += size(x); return s; }
}
