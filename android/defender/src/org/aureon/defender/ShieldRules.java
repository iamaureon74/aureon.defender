package org.aureon.defender;

import java.util.*;

/**
 * Plain detection rules for files on shared storage and the hardware budget. No Android imports, no AI,
 * no network: the same input always gives the same answer, so it is unit-tested on a desktop JVM.
 */
public final class ShieldRules {
    private ShieldRules() {}

    static final Set<String> LURE = new HashSet<>(Arrays.asList("pdf","doc","docx","xls","xlsx","ppt","pptx","txt","jpg","jpeg","png","gif","webp","heic","mp4","mov","mp3","m4a","zip","csv"));
    static final Set<String> EXEC = new HashSet<>(Arrays.asList("apk","apks","xapk","exe","scr","com","pif","bat","cmd","js","vbs","ps1","sh","jar","dex","so","bin","elf","msi","hta","lnk"));

    /** Folders under shared storage that apps and the OS depend on: never touched. */
    public static boolean hardwareNeeds(String relativePath) {
        String p = relativePath.replace('\\', '/').toLowerCase(Locale.ROOT);
        while (p.startsWith("/")) p = p.substring(1);
        return p.startsWith("android/") || p.equals("android") || p.startsWith(".") || p.contains("/.thumbnails")
            || p.startsWith("lost.dir") || p.startsWith("firmware") || p.contains("/firmware/");
    }

    /**
     * A reason to remove the file, or "" when it is fine.
     * @param name      display name
     * @param head      first bytes (up to 64 KiB is enough)
     * @param zipNames  entry names when the file is a ZIP container (may be empty)
     * @param hash      lower-case SHA-256, or null when not computed
     * @param blocklist imported SHA-256 list
     */
    public static String verdict(String name, byte[] head, Collection<String> zipNames, String hash, Set<String> blocklist) {
        String low = name.toLowerCase(Locale.ROOT);
        if (hash != null && blocklist != null && blocklist.contains(hash)) return "matches a known-bad SHA-256 in your blocklist";
        if (name.indexOf('‮') >= 0) return "the name uses a right-to-left trick to fake its file type";
        String[] parts = low.split("\\.");
        String ext = parts.length > 1 ? parts[parts.length - 1] : "";
        if (parts.length >= 3 && EXEC.contains(ext) && LURE.contains(parts[parts.length - 2]))
            return "double extension: looks like ." + parts[parts.length - 2] + " but is ." + ext;
        if (low.matches(".*\\s{5,}\\.\\w+$")) return "a long run of spaces hides the real file type";
        boolean zip = head.length >= 4 && head[0] == 'P' && head[1] == 'K' && head[2] == 3 && head[3] == 4;
        boolean apkInside = zip && zipNames.contains("AndroidManifest.xml") && zipNames.contains("classes.dex");
        if (apkInside && !ext.startsWith("apk") && !ext.equals("xapk") && !ext.equals("zip") && !ext.equals("jar"))
            return "an Android app disguised as ." + (ext.isEmpty() ? "a file with no type" : ext);
        boolean elf = head.length >= 4 && head[0] == 0x7f && head[1] == 'E' && head[2] == 'L' && head[3] == 'F';
        boolean mz = head.length >= 2 && head[0] == 'M' && head[1] == 'Z';
        if ((elf || mz) && LURE.contains(ext)) return "a program disguised as ." + ext;
        if (elf && ext.isEmpty() && low.matches(".*(invoice|receipt|photo|document|scan|statement).*")) return "a program disguised as a document";
        if (zip && ext.equals("zip")) {
            for (String n : zipNames) {
                String e = n.toLowerCase(Locale.ROOT);
                String[] q = e.split("\\.");
                if (q.length >= 3 && EXEC.contains(q[q.length - 1]) && LURE.contains(q[q.length - 2]))
                    return "the archive hides a program behind a double extension: " + n;
            }
        }
        return "";
    }

    /** {tier, maxFiles, hashLimitMb, quick} from measured hardware. Same arithmetic as hwguard.budget on desktop. */
    public static int[] budget(int cores, double ramGb, int batteryPercent, boolean charging, int thermalStatus, boolean powerSave) {
        double capacity = Math.min(Math.max(1, cores) / 8.0, 1.5) * 0.5 + Math.min((ramGb <= 0 ? 3 : ramGb) / 8.0, 1.5) * 0.5;
        int tier = capacity < 0.45 ? 0 : capacity < 0.95 ? 1 : 2;
        int maxFiles = (int) Math.min(8000, Math.max(800, Math.round(3000 * capacity)));
        int hashMb = tier == 0 ? 64 : 256;
        // Hot, nearly empty or in battery saver: still check new arrivals, but only a quarter of the usual sweep.
        boolean quick = thermalStatus >= 3 || powerSave || (batteryPercent >= 0 && batteryPercent < 15 && !charging);
        if (quick) { maxFiles = Math.max(200, maxFiles / 4); hashMb = Math.min(hashMb, 32); }
        return new int[]{tier, maxFiles, hashMb, quick ? 1 : 0};
    }

    public static String tierName(int tier) { return tier == 0 ? "light" : tier == 1 ? "balanced" : "full"; }
}
