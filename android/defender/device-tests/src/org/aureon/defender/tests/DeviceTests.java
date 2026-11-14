package org.aureon.defender.tests;
import android.app.*;
import android.content.*;
import android.os.Bundle;
import android.net.Uri;
import org.aureon.defender.*;
import org.json.*;
import java.util.*;

public class DeviceTests extends Instrumentation {
 private int passed=0;
 public void onCreate(Bundle args){super.onCreate(args);start();}
 private void check(boolean ok,String why){if(!ok)throw new AssertionError(why);passed++;}
 private void input(MainActivity activity,int request,String fixture) throws Exception {
  java.lang.reflect.Method m=MainActivity.class.getDeclaredMethod("onActivityResult",int.class,int.class,Intent.class);m.setAccessible(true);
  getTargetContext().getSharedPreferences("guard",0).edit().remove("file_result").commit();
  runOnMainSync(()->{try{m.invoke(activity,request,Activity.RESULT_OK,new Intent().setData(Uri.parse("content://org.aureon.defender.tests.fixtures/"+fixture)));}catch(Exception e){throw new RuntimeException(e);}});
  long until=System.currentTimeMillis()+6000;
  while(!getTargetContext().getSharedPreferences("guard",0).contains("file_result")&&System.currentTimeMillis()<until)Thread.sleep(50);
 }
 public void onStart(){
  Bundle result=new Bundle();SharedPreferences p=getTargetContext().getSharedPreferences("guard",0);
  boolean hadHashes=p.contains("hashes");Set<String> oldHashes=new HashSet<>(p.getStringSet("hashes",Collections.emptySet()));String oldResult=p.getString("file_result",null);
  try{
   JSONObject r=Audit.run(getTargetContext());check(r.getInt("visible_package_count")>0,"No package visibility");
   check(r.getString("device").equals(android.os.Build.MODEL),"Device mismatch");
   check(r.has("usb_host_devices")&&r.has("secure_lock"),"Missing posture fields");
   int history=r.getJSONArray("event_history").length();JSONObject second=Audit.run(getTargetContext());
   check(second.getJSONArray("event_history").length()>=history,"History lost on repeat audit");
   MainActivity activity=(MainActivity)startActivitySync(new Intent(getTargetContext(),MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
   check(activity!=null,"Activity launch failed");
   waitForIdleSync();
   runOnMainSync(()->{
    android.view.View decor=activity.getWindow().getDecorView();
    android.view.View header=decor.findViewWithTag("aureon-header"),dock=decor.findViewWithTag("aureon-floating-nav");
    android.graphics.Insets safe=decor.getRootWindowInsets().getInsets(android.view.WindowInsets.Type.systemBars()|android.view.WindowInsets.Type.displayCutout());
    android.graphics.Rect bounds=activity.getWindowManager().getCurrentWindowMetrics().getBounds();
    int[] h=new int[2],d=new int[2];header.getLocationOnScreen(h);dock.getLocationOnScreen(d);
    check(header.getHeight()>0&&h[1]>=safe.top,"Header overlaps status bar/cutout");
    check(d[0]>0&&d[0]+dock.getWidth()<bounds.width(),"Floating dock missing side margins");
    check(d[1]+dock.getHeight()<=bounds.height()-safe.bottom,"Dock overlaps gesture/navigation area");
   });
   for(String tab:new String[]{"Overview","Apps","Hardware","Activity","Tools"}){
    runOnMainSync(()->{
     android.widget.LinearLayout dock=activity.getWindow().getDecorView().findViewWithTag("aureon-floating-nav");
     for(int i=0;i<dock.getChildCount();i++){android.view.View child=dock.getChildAt(i);if(tab.contentEquals(child.getContentDescription())){child.performClick();break;}}
    });
    waitForIdleSync();java.lang.reflect.Field field=MainActivity.class.getDeclaredField("tab");field.setAccessible(true);
    check(tab.equals(field.get(activity)),"Navigation failed: "+tab);
   }
   input(activity,42,"hashes");check(p.getString("file_result","").startsWith("Imported 1"),"Content URI blocklist import failed");
   input(activity,41,"abc");check(p.getString("file_result","").startsWith("MATCH"),"Selected-file known hash did not match");
   input(activity,42,"invalid");check(p.getString("file_result","").startsWith("Check failed"),"Invalid import not rejected");
   check(p.getStringSet("hashes",Collections.emptySet()).size()==1,"Invalid import replaced good blocklist");
   check(Audit.latest(getTargetContext()).contains("generated_at_ms"),"Local report unreadable");
   input(activity,44,"export");
   java.io.ByteArrayOutputStream exported=new java.io.ByteArrayOutputStream();
   try(java.io.InputStream in=getTargetContext().getContentResolver().openInputStream(Uri.parse("content://org.aureon.defender.tests.fixtures/export"))){byte[] b=new byte[4096];int n;while((n=in.read(b))!=-1)exported.write(b,0,n);}
   check(new JSONObject(exported.toString("UTF-8")).getInt("visible_package_count")>0,"Exported report invalid");
   result.putString("summary",passed+" on-device assertions passed");finish(Activity.RESULT_OK,result);
  }catch(Throwable e){result.putString("failure",e.toString());result.putInt("passed",passed);finish(Activity.RESULT_CANCELED,result);}
  finally{SharedPreferences.Editor edit=p.edit();if(hadHashes)edit.putStringSet("hashes",oldHashes);else edit.remove("hashes");if(oldResult==null)edit.remove("file_result");else edit.putString("file_result",oldResult);edit.commit();}
 }
}
