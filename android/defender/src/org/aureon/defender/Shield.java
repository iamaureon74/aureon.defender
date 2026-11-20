package org.aureon.defender;

import android.app.*;
import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.os.*;
import android.provider.DocumentsContract;
import org.json.*;
import java.io.*;
import java.util.*;
import java.util.zip.*;

/**
 * Silent autopilot for shared storage. Runs with every audit (15-minute job, package changes, boot).
 * Something found -> deleted at once, one quiet notification and one log line say what and why.
 * Never touches Android/, hidden system folders or firmware folders (ShieldRules.hardwareNeeds).
 * Reach: with "All files access" it covers the whole shared storage; otherwise only folders you granted.
 */
public final class Shield {
    private Shield() {}

    public static synchronized JSONObject sweep(Context c) {
        SharedPreferences prefs = c.getSharedPreferences("guard", 0);
        int[] b = budget(c);
        long since = prefs.getLong("shield_since", 0), started = System.currentTimeMillis();
        Set<String> blocklist = new HashSet<>(prefs.getStringSet("hashes", Collections.<String>emptySet()));
        int[] n = {0, 0};                                   // checked, removed
        JSONArray log = read(prefs.getString("shield_log", "[]"));
        if (Build.VERSION.SDK_INT >= 30 && Environment.isExternalStorageManager()) {
            File root = Environment.getExternalStorageDirectory();
            ArrayDeque<File> queue = new ArrayDeque<>();
            queue.add(root);
            while (!queue.isEmpty() && n[0] < b[1]) {
                File dir = queue.removeFirst();
                File[] kids = dir.listFiles();
                if (kids == null) continue;
                for (File f : kids) {
                    String rel = root.toURI().relativize(f.toURI()).getPath();
                    if (ShieldRules.hardwareNeeds(rel)) continue;
                    if (f.isDirectory()) { if (queue.size() < 4000) queue.add(f); continue; }
                    if (f.lastModified() < since || n[0] >= b[1]) continue;
                    n[0]++;
                    try (InputStream in = new FileInputStream(f)) {
                        String why = check(f.getName(), f.length(), in, () -> new FileInputStream(f), blocklist, b[2]);
                        if (why.isEmpty() && f.getName().toLowerCase(Locale.ROOT).endsWith(".apk")) why = impostor(c, f);
                        if (!why.isEmpty() && f.delete()) { n[1]++; removed(c, log, f.getName(), why); }
                    } catch (Exception ignored) {}
                }
            }
        }
        for (String t : prefs.getStringSet("guard_trees", Collections.<String>emptySet())) {
            try { tree(c, Uri.parse(t), since, blocklist, b, n, log); } catch (Exception ignored) {}
        }
        JSONArray bounded = new JSONArray();
        for (int i = Math.max(0, log.length() - 100); i < log.length(); i++) bounded.put(log.opt(i));
        prefs.edit().putLong("shield_since", started - 60000).putString("shield_log", bounded.toString())
            .putLong("shield_checked", prefs.getLong("shield_checked", 0) + n[0])
            .putLong("shield_removed", prefs.getLong("shield_removed", 0) + n[1])
            .putString("shield_tier", ShieldRules.tierName(b[0])).putBoolean("shield_quick", b[3] == 1)
            .putLong("shield_last", started).apply();
        JSONObject out = new JSONObject();
        try { out.put("checked", n[0]).put("removed", n[1]).put("tier", ShieldRules.tierName(b[0])).put("max_files", b[1]).put("quick", b[3] == 1); } catch (JSONException ignored) {}
        return out;
    }

    interface Opener { InputStream open() throws IOException; }

    /** Read the head (and ZIP entry names when it is a ZIP); hash only when a blocklist exists and size allows. */
    static String check(String name, long size, InputStream head, Opener again, Set<String> blocklist, int hashMb) throws Exception {
        byte[] buf = new byte[65536];
        int len = 0, r;
        while (len < buf.length && (r = head.read(buf, len, buf.length - len)) > 0) len += r;
        byte[] h = Arrays.copyOf(buf, len);
        List<String> names = new ArrayList<>();
        if (len >= 4 && h[0] == 'P' && h[1] == 'K' && size <= 512L * 1024 * 1024) {
            try (ZipInputStream z = new ZipInputStream(new BufferedInputStream(again.open()))) {
                ZipEntry e; int count = 0;
                while ((e = z.getNextEntry()) != null && count++ < 400) names.add(e.getName());
            } catch (Exception ignored) {}
        }
        String hash = null;
        if (!blocklist.isEmpty() && size <= hashMb * 1024L * 1024L) {
            try (InputStream in = again.open()) { hash = FileChecks.hash(in, hashMb * 1024L * 1024L); }
        }
        return ShieldRules.verdict(name, h, names, hash, blocklist);
    }

    private static void tree(Context c, Uri tree, long since, Set<String> blocklist, int[] b, int[] n, JSONArray log) throws Exception {
        ContentResolver cr = c.getContentResolver();
        ArrayDeque<String> queue = new ArrayDeque<>();
        queue.add(DocumentsContract.getTreeDocumentId(tree));
        String[] cols = {DocumentsContract.Document.COLUMN_DOCUMENT_ID, DocumentsContract.Document.COLUMN_DISPLAY_NAME,
            DocumentsContract.Document.COLUMN_MIME_TYPE, DocumentsContract.Document.COLUMN_SIZE, DocumentsContract.Document.COLUMN_LAST_MODIFIED};
        int folders = 0;
        while (!queue.isEmpty() && n[0] < b[1] && folders++ < 2000) {
            try (Cursor cur = cr.query(DocumentsContract.buildChildDocumentsUriUsingTree(tree, queue.removeFirst()), cols, null, null, null)) {
                if (cur == null) continue;
                while (cur.moveToNext() && n[0] < b[1]) {
                    String id = cur.getString(0), name = cur.getString(1), mime = cur.getString(2);
                    if (name == null || name.startsWith(".")) continue;
                    if (DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)) { if (!name.equalsIgnoreCase("Android") && queue.size() < 2000) queue.add(id); continue; }
                    if (!cur.isNull(4) && cur.getLong(4) < since) continue;
                    n[0]++;
                    final Uri doc = DocumentsContract.buildDocumentUriUsingTree(tree, id);
                    try (InputStream in = cr.openInputStream(doc)) {
                        String why = check(name, cur.isNull(3) ? 0 : cur.getLong(3), in, () -> cr.openInputStream(doc), blocklist, b[2]);
                        if (!why.isEmpty() && DocumentsContract.deleteDocument(cr, doc)) { n[1]++; removed(c, log, name, why); }
                    } catch (Exception ignored) {}
                }
            }
        }
    }

    /** An installer that claims an installed app's package name but carries a different signing certificate. */
    static String impostor(Context c, File apk) {
        try {
            android.content.pm.PackageManager pm = c.getPackageManager();
            int flags = android.content.pm.PackageManager.GET_SIGNING_CERTIFICATES;
            android.content.pm.PackageInfo file = pm.getPackageArchiveInfo(apk.getAbsolutePath(), flags);
            if (file == null || file.packageName == null || file.signingInfo == null) return "";
            android.content.pm.PackageInfo have;
            try { have = pm.getPackageInfo(file.packageName, flags); } catch (android.content.pm.PackageManager.NameNotFoundException e) { return ""; }
            if (have.signingInfo == null) return "";
            Set<String> mine = new HashSet<>(), theirs = new HashSet<>();
            for (android.content.pm.Signature sg : have.signingInfo.getApkContentsSigners()) mine.add(sg.toCharsString());
            for (android.content.pm.Signature sg : file.signingInfo.getApkContentsSigners()) theirs.add(sg.toCharsString());
            if (have.signingInfo.hasPastSigningCertificates())
                for (android.content.pm.Signature sg : have.signingInfo.getSigningCertificateHistory()) mine.add(sg.toCharsString());
            for (String t : theirs) if (mine.contains(t)) return "";
            String label = String.valueOf(pm.getApplicationLabel(have.applicationInfo));
            return "an installer pretending to be " + label + " but signed by someone else (tampered or fake copy)";
        } catch (Exception e) { return ""; }
    }

    static int[] budget(Context c) {
        ActivityManager am = (ActivityManager) c.getSystemService(Context.ACTIVITY_SERVICE);
        ActivityManager.MemoryInfo m = new ActivityManager.MemoryInfo();
        if (am != null) am.getMemoryInfo(m);
        BatteryManager bm = (BatteryManager) c.getSystemService(Context.BATTERY_SERVICE);
        PowerManager pm = (PowerManager) c.getSystemService(Context.POWER_SERVICE);
        int pct = bm == null ? -1 : bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY);
        return ShieldRules.budget(Runtime.getRuntime().availableProcessors(), m.totalMem / 1073741824.0, pct,
            bm != null && bm.isCharging(), pm == null ? 0 : pm.getCurrentThermalStatus(), pm != null && pm.isPowerSaveMode());
    }

    private static void removed(Context c, JSONArray log, String name, String why) {
        try { log.put(new JSONObject().put("t", System.currentTimeMillis()).put("title", "removed " + name).put("detail", why)); } catch (JSONException ignored) {}
        NotificationManager nm = c.getSystemService(NotificationManager.class);
        if (nm == null) return;
        NotificationChannel ch = new NotificationChannel("removed", "Removed threats", NotificationManager.IMPORTANCE_LOW);
        ch.setSound(null, null); ch.enableVibration(false); nm.createNotificationChannel(ch);
        PendingIntent open = PendingIntent.getActivity(c, 2, new Intent(c, MainActivity.class), PendingIntent.FLAG_IMMUTABLE);
        nm.notify(("removed" + name).hashCode(), new Notification.Builder(c, "removed").setSmallIcon(android.R.drawable.ic_lock_lock)
            .setContentTitle("removed " + name).setContentText(why).setStyle(new Notification.BigTextStyle().bigText(why))
            .setContentIntent(open).setAutoCancel(true).setOnlyAlertOnce(true).build());
    }

    private static JSONArray read(String s) { try { return new JSONArray(s); } catch (JSONException e) { return new JSONArray(); } }
}
