package org.aureon.defender;
import android.app.job.*;
import android.content.*;

public class AuditJob extends JobService {
    public static void schedule(Context c){
        JobInfo j=new JobInfo.Builder(7301,new ComponentName(c,AuditJob.class)).setPeriodic(15*60*1000).setPersisted(true).build();
        if(c.getSystemService(JobScheduler.class).schedule(j)!=JobScheduler.RESULT_SUCCESS)
            c.getSharedPreferences("guard",0).edit().putString("last_error","Periodic audit scheduling failed").apply();
    }
    public static void cancel(Context c){c.getSystemService(JobScheduler.class).cancel(7301);}
    @Override public boolean onStartJob(JobParameters p){
        if(!getSharedPreferences("guard",0).getBoolean("enabled",false))return false;
        new Thread(()->{Audit.attempt(this);jobFinished(p,false);},"aureon-audit").start();return true;
    }
    @Override public boolean onStopJob(JobParameters p){return true;}
}
