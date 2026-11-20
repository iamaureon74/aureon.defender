package org.aureon.defender;

public final class Rules {
    private Rules() {}
    public static String classify(boolean camera, boolean microphone, boolean location, boolean sms) {
        if (sms && microphone) return "Review granted SMS and microphone access; verify the app needs both.";
        if (camera && microphone && location) return "Review granted camera, microphone and location access.";
        return "";
    }
    public static String scope() {
        return "Permission combinations are review prompts, not malware verdicts. Files on shared storage that match a rule or your blocklist are deleted automatically; Android/, hidden and firmware folders are never touched. Android does not let an ordinary app uninstall other apps silently, read their private data, or intercept traffic without root or a VPN.";
    }
    /** Assistants and on-device AI known to keep a wake-word or ambient-audio model running. */
    public static final String[][] LISTENERS = {
        {"com.google.android.googlequicksearchbox","Google Assistant / 'Hey Google' wake word"},
        {"com.google.android.apps.googleassistant","Google Assistant"},
        {"com.google.android.as","Android System Intelligence (on-device AI: Now Playing, Live Caption, smart replies)"},
        {"com.google.android.as.oss","Private Compute Services (on-device AI)"},
        {"com.google.android.apps.bard","Gemini assistant"},
        {"com.samsung.android.bixby.agent","Bixby voice / 'Hi Bixby' wake word"},
        {"com.samsung.android.bixby.wakeup","Bixby wake-up"},
        {"com.amazon.dee.app","Amazon Alexa"},
        {"com.microsoft.cortana","Cortana"},
        {"com.huawei.vassistant","Celia / Huawei voice assistant"},
        {"com.miui.voiceassist","Xiao Ai voice assistant"},
        {"com.oplus.ai.assistant","Breeno / OPPO voice assistant"}
    };
    public static String listener(String pkg){
        for(String[] l:LISTENERS)if(l[0].equals(pkg))return l[1];
        return "";
    }
}
