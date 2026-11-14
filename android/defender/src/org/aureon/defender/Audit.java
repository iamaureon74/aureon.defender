package org.aureon.defender;

import android.app.KeyguardManager;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.*;
import android.net.*;
import android.os.Build;
import android.os.BatteryManager;
import android.hardware.usb.*;
import android.provider.Settings;
import org.json.*;
import java.io.*;
import java.util.*;

public final class Audit {
    private Audit() {}
    private static boolean granted(PackageInfo p, String permission) {
        if (p.requestedPermissions == null || p.requestedPermissionsFlags == null) return false;
        for(int i=0;i<p.requestedPermissions.length;i++)
            if(permission.equals(p.requestedPermissions[i])) return (p.requestedPermissionsFlags[i]&PackageInfo.REQUESTED_PERMISSION_GRANTED)!=0;
        return false;
    }
    public static synchronized JSONObject run(Context c) throws Exception {
        JSONObject report=new JSONObject(); JSONArray findings=new JSONArray(), apps=new JSONArray(), added=new JSONArray(), removed=new JSONArray(), updated=new JSONArray();
        SharedPreferences prefs=c.getSharedPreferences("guard",0);
        String previous=prefs.getString("packages",null);
        JSONObject oldVersions=new JSONObject(prefs.getString("package_versions","{}")), versions=new JSONObject();
        JSONArray history=new JSONArray(prefs.getString("event_history","[]"));
        Set<String> before=new HashSet<>(), current=new TreeSet<>();
        if(previous!=null) { JSONArray a=new JSONArray(previous);for(int i=0;i<a.length();i++)before.add(a.getString(i)); }
        PackageManager pm=c.getPackageManager();
        for(PackageInfo p:pm.getInstalledPackages(PackageManager.GET_PERMISSIONS)) {
            current.add(p.packageName);
            String version=String.valueOf(p.getLongVersionCode());
            versions.put(p.packageName,version);
            if(previous!=null&&!before.contains(p.packageName))added.put(p.packageName);
            if(oldVersions.has(p.packageName)&&!version.equals(oldVersions.optString(p.packageName)))updated.put(p.packageName);
            // Store review findings only, rather than a full inventory of unrelated apps.
            boolean cam=granted(p,"android.permission.CAMERA"), mic=granted(p,"android.permission.RECORD_AUDIO"),
                loc=granted(p,"android.permission.ACCESS_FINE_LOCATION"), sms=granted(p,"android.permission.READ_SMS");
            String risk=Rules.classify(cam,mic,loc,sms);
            if(!risk.isEmpty())apps.put(new JSONObject().put("package",p.packageName).put("review",risk));
        }
        for(String pkg:before)if(!current.contains(pkg))removed.put(pkg);
        for(String kind:new String[]{"installed","removed","updated"}){
            JSONArray changes=kind.equals("installed")?added:kind.equals("removed")?removed:updated;
            for(int i=0;i<changes.length();i++)history.put(new JSONObject().put("time_ms",System.currentTimeMillis()).put("kind",kind).put("package",changes.getString(i)));
        }
        JSONArray boundedHistory=new JSONArray();for(int i=Math.max(0,history.length()-200);i<history.length();i++)boundedHistory.put(history.get(i));
        KeyguardManager kg=(KeyguardManager)c.getSystemService(Context.KEYGUARD_SERVICE);
        boolean secure=kg!=null&&kg.isDeviceSecure();
        if(!secure)findings.put("No secure screen lock reported. Set a PIN/password in Android settings.");
        String accessibility=Settings.Secure.getString(c.getContentResolver(),Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES);
        if(accessibility!=null&&!accessibility.isEmpty()) findings.put("Accessibility services are enabled. Review services in Android settings; legitimate accessibility tools may need this access.");
        ConnectivityManager cm=(ConnectivityManager)c.getSystemService(Context.CONNECTIVITY_SERVICE);
        Network n=cm.getActiveNetwork(); NetworkCapabilities caps=n==null?null:cm.getNetworkCapabilities(n);
        boolean internet=caps!=null&&caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED);
        JSONArray usb=new JSONArray();
        UsbManager um=(UsbManager)c.getSystemService(Context.USB_SERVICE);
        if(um!=null)for(UsbDevice d:um.getDeviceList().values())usb.put(new JSONObject().put("vendor",d.getVendorId()).put("product",d.getProductId()).put("device_class",d.getDeviceClass()));
        BatteryManager bm=(BatteryManager)c.getSystemService(Context.BATTERY_SERVICE);
        int battery=bm==null?-1:bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY);
        report.put("version",1).put("app_version","0.4.1").put("generated_at_ms",System.currentTimeMillis()).put("battery_percent",battery).put("usb_host_devices",usb)
          .put("device",Build.MODEL).put("android_api",Build.VERSION.SDK_INT).put("secure_lock",secure)
          .put("validated_network",internet).put("visible_package_count",current.size()).put("permission_reviews",apps)
          .put("added_packages",added).put("removed_packages",removed).put("baseline_initialized",previous!=null)
          .put("updated_packages",updated).put("event_history",boundedHistory)
          .put("findings",findings).put("scope",Rules.scope()).put("data_destination","Local app-private storage only; this app has no INTERNET permission.");
        File file=new File(c.getFilesDir(),"report.json"), tmp=new File(c.getFilesDir(),"report.tmp");
        try(FileOutputStream out=new FileOutputStream(tmp)){out.write(report.toString(2).getBytes("UTF-8"));out.getFD().sync();}
        if(!tmp.renameTo(file))throw new IOException("Cannot commit local audit report");
        if(!prefs.edit().putString("packages",new JSONArray(current).toString()).putString("package_versions",versions.toString()).putString("event_history",boundedHistory.toString()).putLong("last_audit",System.currentTimeMillis()).remove("last_error").commit())throw new IOException("Could not persist audit baseline");
        return report;
    }
    public static String latest(Context c) {
        try {ByteArrayOutputStream out=new ByteArrayOutputStream();try(FileInputStream in=c.openFileInput("report.json")) {byte[] b=new byte[4096];int count;while((count=in.read(b))!=-1)out.write(b,0,count);}return out.toString("UTF-8");}
        catch(Exception e){return "No completed audit yet.";}
    }
    public static void attempt(Context c){try{run(c);}catch(Exception e){c.getSharedPreferences("guard",0).edit().putString("last_error",e.getClass().getSimpleName()+": "+e.getMessage()).apply();}}
}
