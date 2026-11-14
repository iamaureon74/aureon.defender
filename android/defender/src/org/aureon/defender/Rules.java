package org.aureon.defender;

public final class Rules {
    private Rules() {}
    public static String classify(boolean camera, boolean microphone, boolean location, boolean sms) {
        if (sms && microphone) return "Review granted SMS and microphone access; verify the app needs both.";
        if (camera && microphone && location) return "Review granted camera, microphone and location access.";
        return "";
    }
    public static String scope() {
        return "Permission combinations are review prompts, not malware verdicts. Android limits visibility into other apps, USB hardware and network traffic. No root access, VPN interception or automatic removal.";
    }
}
