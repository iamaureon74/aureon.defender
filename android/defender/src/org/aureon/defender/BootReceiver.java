package org.aureon.defender;
import android.content.*;
public class BootReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context c,Intent i){
        if(!c.getSharedPreferences("guard",0).getBoolean("enabled",false))return;
        AuditJob.schedule(c);
        try{c.startForegroundService(new Intent(c,GuardService.class));}
        catch(RuntimeException e){c.getSharedPreferences("guard",0).edit().putBoolean("service_running",false).putString("last_error","Android prevented background start; reopen the app. Periodic audits remain scheduled.").apply();}
    }
}
