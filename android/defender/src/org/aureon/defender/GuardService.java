package org.aureon.defender;

import android.app.*;
import android.content.*;
import android.os.*;
import java.util.concurrent.*;

public class GuardService extends Service {
    private ScheduledExecutorService worker;
    private BroadcastReceiver packages;
    @Override public void onCreate(){
        super.onCreate();
        NotificationManager nm=getSystemService(NotificationManager.class);
        NotificationChannel channel=new NotificationChannel("guard","Local protection status",NotificationManager.IMPORTANCE_LOW);
        channel.setSound(null,null);channel.enableVibration(false);nm.createNotificationChannel(channel);
        PendingIntent open=PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class),PendingIntent.FLAG_IMMUTABLE);
        Intent stop=new Intent(this,GuardService.class).setAction("STOP");
        PendingIntent stopping=PendingIntent.getService(this,1,stop,PendingIntent.FLAG_IMMUTABLE);
        Notification note=new Notification.Builder(this,"guard").setContentTitle("Aureon Defender monitoring")
            .setContentText("Local security checks · tap to review").setSmallIcon(android.R.drawable.ic_lock_lock)
            .setContentIntent(open).setOngoing(true).setOnlyAlertOnce(true)
            .addAction(new Notification.Action.Builder(null,"Stop",stopping).build()).build();
        if(Build.VERSION.SDK_INT>=34)startForeground(1,note,android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        else startForeground(1,note);
        worker=Executors.newSingleThreadScheduledExecutor();
        worker.scheduleWithFixedDelay(()->Audit.attempt(this),0,15,TimeUnit.MINUTES);
        packages=new BroadcastReceiver(){@Override public void onReceive(Context c,Intent i){if(worker!=null&&!worker.isShutdown())worker.execute(()->Audit.attempt(c));}};
        IntentFilter f=new IntentFilter();f.addAction(Intent.ACTION_PACKAGE_ADDED);f.addAction(Intent.ACTION_PACKAGE_REMOVED);f.addAction(Intent.ACTION_PACKAGE_REPLACED);f.addDataScheme("package");
        if(Build.VERSION.SDK_INT>=33)registerReceiver(packages,f,Context.RECEIVER_NOT_EXPORTED);
        else registerReceiver(packages,f);
        getSharedPreferences("guard",0).edit().putBoolean("service_running",true).apply();
    }
    @Override public int onStartCommand(Intent i,int flags,int id){
        if(i!=null&&"STOP".equals(i.getAction())){
            getSharedPreferences("guard",0).edit().putBoolean("enabled",false).apply();
            AuditJob.cancel(this);stopForeground(STOP_FOREGROUND_REMOVE);stopSelf();return START_NOT_STICKY;
        }
        return START_STICKY;
    }
    @Override public void onDestroy(){
        getSharedPreferences("guard",0).edit().putBoolean("service_running",false).apply();
        if(worker!=null)worker.shutdownNow();if(packages!=null)unregisterReceiver(packages);super.onDestroy();
    }
    @Override public IBinder onBind(Intent i){return null;}
}
