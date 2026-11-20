package org.aureon.defender;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.os.*;
import android.graphics.*;
import android.graphics.drawable.GradientDrawable;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.io.*;
import java.text.DateFormat;
import java.util.*;

public class MainActivity extends Activity {
    private int BG,CARD,LINE,TEXT,MUTED,AMBER,GREEN;
    private boolean frost=false;
    private void palette(){frost=prefs().getBoolean("signal_frost",false);
        BG=Color.parseColor(frost?"#f5f6f2":"#0d1012");CARD=Color.parseColor(frost?"#ffffff":"#14191c");LINE=Color.parseColor(frost?"#d6ded7":"#293136");
        TEXT=Color.parseColor(frost?"#13201b":"#f1f3f2");MUTED=Color.parseColor(frost?"#62716b":"#9da8ad");AMBER=Color.parseColor(frost?"#344f1a":"#d9ff70");GREEN=Color.parseColor(frost?"#227858":"#78dcb3");if(prefs().getBoolean("copper",false)){BG=Color.rgb(23,19,17);CARD=Color.rgb(34,28,24);LINE=Color.rgb(65,51,40);TEXT=Color.rgb(245,232,214);MUTED=Color.rgb(185,165,144);AMBER=Color.rgb(230,178,115);GREEN=Color.rgb(169,199,145);}
    }
    private android.view.PointerIcon pointerTheme(){String choice=prefs().getString("pointer_style","system");if(choice.equals("precision"))return android.view.PointerIcon.getSystemIcon(this,android.view.PointerIcon.TYPE_CROSSHAIR);if(choice.equals("lime")){Bitmap b=Bitmap.createBitmap(dp(32),dp(32),Bitmap.Config.ARGB_8888);Canvas c=new Canvas(b);c.scale(dp(32)/32f,dp(32)/32f);Paint p=new Paint(3);Path path=new Path();path.moveTo(3,2);path.lineTo(3,25);path.lineTo(9,19);path.lineTo(14,29);path.lineTo(19,26);path.lineTo(14,17);path.lineTo(24,16);path.close();p.setColor(Color.rgb(16,20,19));c.drawPath(path,p);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(2);p.setColor(Color.rgb(213,249,161));c.drawPath(path,p);return android.view.PointerIcon.create(b,dp(3),dp(2));}return android.view.PointerIcon.getSystemIcon(this,android.view.PointerIcon.TYPE_DEFAULT);}
    private LinearLayout body;
    private ScrollView scroller;
    private String renderedTab="";
    private String tab="Overview";
    private boolean busy=false;
    private android.net.Uri cleanSource;
    private long netTime=0,netRx=0,netTx=0;
    private Handler handler=new Handler();
    private final Runnable updater=new Runnable(){public void run(){if(!busy&&(tab.equals("Overview")||tab.equals("Hardware")))render();handler.postDelayed(this,5000);}};
    private int dp(int x){return (int)(x*getResources().getDisplayMetrics().density+.5f);}
    private android.content.SharedPreferences prefs(){return getSharedPreferences("guard",0);}
    private GradientDrawable box(int color,int radius){GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(radius));d.setStroke(dp(1),LINE);return d;}
    private LinearLayout column(){LinearLayout l=new LinearLayout(this);l.setOrientation(1);return l;}
    private TextView text(LinearLayout parent,String value,int size,int color,boolean bold){TextView t=new TextView(this);t.setText(value);t.setTextSize(size);t.setTextColor(color);t.setFontFeatureSettings("kern");t.setTypeface(Typeface.create("sans-serif",bold?Typeface.BOLD:Typeface.NORMAL));t.setLineSpacing(dp(3),1);parent.addView(t);return t;}
    private void gap(LinearLayout parent,int height){parent.addView(new View(this),new LinearLayout.LayoutParams(1,dp(height)));}
    private LinearLayout card(String eyebrow){LinearLayout c=column();c.setPadding(dp(20),dp(18),dp(20),dp(20));c.setBackground(box(CARD,7));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.bottomMargin=dp(14);body.addView(c,p);if(!eyebrow.isEmpty()){TextView e=text(c,eyebrow.toUpperCase(Locale.ROOT),11,MUTED,true);e.setLetterSpacing(.13f);gap(c,12);}return c;}
    private void button(LinearLayout p,String label,boolean primary,Runnable r){Button b=new Button(this);b.setText(label);b.setAllCaps(false);b.setTextSize(14);b.setTypeface(Typeface.DEFAULT,Typeface.BOLD);b.setTextColor(primary?(frost?Color.WHITE:BG):TEXT);b.setBackground(new android.graphics.drawable.RippleDrawable(android.content.res.ColorStateList.valueOf(frost?0x18344f1a:0x24d9ff70),box(primary?AMBER:CARD,5),null));b.setMinHeight(dp(48));b.setPadding(dp(16),dp(8),dp(16),dp(8));LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,dp(50));lp.topMargin=dp(10);p.addView(b,lp);b.setOnClickListener(v->r.run());}
    private JSONObject report(){try{return new JSONObject(Audit.latest(this));}catch(Exception e){return new JSONObject();}}
    private boolean running(){ActivityManager am=(ActivityManager)getSystemService(ACTIVITY_SERVICE);for(ActivityManager.RunningServiceInfo s:am.getRunningServices(100))if(s.service.getClassName().equals(GuardService.class.getName())&&s.foreground)return true;return false;}
    @Override public void onCreate(Bundle state){super.onCreate(state);getWindow().setStatusBarColor(BG);getWindow().setNavigationBarColor(BG);render();if(Build.VERSION.SDK_INT>=33&&checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},10);}
    private void render(){
        final int previousScroll=scroller!=null&&tab.equals(renderedTab)?scroller.getScrollY():0;renderedTab=tab;
        palette();getWindow().setStatusBarColor(BG);getWindow().setNavigationBarColor(BG);
        getWindow().getDecorView().setSystemUiVisibility(frost?View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR:0);
        LinearLayout root=column();root.setBackgroundColor(BG);root.setPadding(0,dp(8),0,0);
        root.setTag("aureon-root");
        root.setOnApplyWindowInsetsListener((v,insets)->{android.graphics.Insets i=insets.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.displayCutout());
            v.setPadding(i.left,Math.max(i.top,dp(8)),i.right,i.bottom);return insets;});
        LinearLayout header=new LinearLayout(this);header.setGravity(Gravity.CENTER_VERTICAL);header.setPadding(dp(20),dp(10),dp(20),dp(10));header.setMinimumHeight(dp(66));header.setTag("aureon-header");
        ImageView logo=new ImageView(this);logo.setImageResource(R.drawable.logo);logo.setContentDescription("Aureon shield");header.addView(logo,new LinearLayout.LayoutParams(dp(36),dp(36)));
        LinearLayout names=column();names.setPadding(dp(10),0,dp(8),0);
        TextView wordmark=text(names,"aureon.defender",17,TEXT,true);wordmark.setPadding(0,0,0,0);wordmark.setSingleLine(true);wordmark.setEllipsize(android.text.TextUtils.TruncateAt.END);
        TextView subtitle=text(names,"SIGNAL / LOCAL SECURITY",8,MUTED,false);subtitle.setPadding(0,dp(3),0,0);subtitle.setLetterSpacing(.12f);subtitle.setSingleLine(true);subtitle.setEllipsize(android.text.TextUtils.TruncateAt.END);
        header.addView(names,new LinearLayout.LayoutParams(0,-2,1));
        TextView local=new TextView(this);local.setText("LOCAL");local.setTextSize(10);local.setTextColor(GREEN);local.setPadding(dp(10),dp(6),dp(10),dp(6));local.setBackground(box(CARD,7));header.addView(local);root.addView(header);
        String dockChoice=prefs().getString("nav_position","bottom");boolean side=(dockChoice.equals("left")||dockChoice.equals("right")||(dockChoice.equals("auto")&&getResources().getConfiguration().screenWidthDp>=600))&&getResources().getConfiguration().screenWidthDp>=360&&getResources().getConfiguration().screenHeightDp>=450;boolean right=dockChoice.equals("right");
        FrameLayout contentHost=new FrameLayout(this);contentHost.setClipChildren(false);contentHost.setClipToPadding(false);
        ScrollView scroll=new ScrollView(this);scroller=scroll;scroll.setFillViewport(true);scroll.setClipToPadding(false);scroll.setPadding(side&&!right?dp(90):0,0,side&&right?dp(90):0,side?0:dp(100));
        body=column();body.setPadding(dp(22),dp(18),dp(22),dp(18));scroll.addView(body);contentHost.addView(scroll,new FrameLayout.LayoutParams(-1,-1));root.addView(contentHost,new LinearLayout.LayoutParams(-1,0,1));
        JSONObject r=report();
        if(tab.equals("Overview"))overview(r);else if(tab.equals("Apps"))apps(r);else if(tab.equals("Hardware"))hardware(r);else if(tab.equals("Activity"))activity(r);else tools();
        LinearLayout nav=new LinearLayout(this);nav.setTag("aureon-floating-nav");nav.setPadding(dp(6),dp(6),dp(6),dp(6));nav.setGravity(Gravity.CENTER_VERTICAL);nav.setOrientation(side?LinearLayout.VERTICAL:LinearLayout.HORIZONTAL);nav.setBackground(box(CARD,28));nav.setElevation(dp(12));nav.setClipToOutline(true);
        for(String name:new String[]{"Overview","Apps","Hardware","Activity","Tools"}){
            boolean selected=name.equals(tab);LinearLayout item=column();item.setGravity(Gravity.CENTER);item.setMinimumHeight(dp(56));item.setContentDescription(name);item.setClickable(true);item.setFocusable(true);
            if(selected)item.setBackground(box(frost?Color.rgb(231,240,217):Color.rgb(31,41,26),22));
            View symbol=new TabSymbol(this,name,selected?AMBER:MUTED);item.addView(symbol,new LinearLayout.LayoutParams(dp(20),dp(20)));
            TextView n=new TextView(this);n.setText(name);n.setGravity(Gravity.CENTER);n.setTextSize(prefs().getBoolean("nav_large",false)?12:10);n.setPadding(0,dp(4),0,0);n.setTextColor(selected?AMBER:MUTED);n.setTypeface(Typeface.DEFAULT,selected?Typeface.BOLD:Typeface.NORMAL);item.addView(n,new LinearLayout.LayoutParams(-1,-2));
            nav.addView(item,side?new LinearLayout.LayoutParams(dp(68),dp(58)):new LinearLayout.LayoutParams(0,dp(56),1));item.setOnClickListener(v->{tab=name;render();if(!prefs().getBoolean("signal_reduced",false)&&android.animation.ValueAnimator.areAnimatorsEnabled()){body.setAlpha(0f);body.setTranslationY(dp(6));body.animate().alpha(1f).translationY(0f).setDuration(160).start();}});
        }
        FrameLayout.LayoutParams dock=side?new FrameLayout.LayoutParams(dp(80),-2,(right?Gravity.RIGHT:Gravity.LEFT)|Gravity.CENTER_VERTICAL):new FrameLayout.LayoutParams(-1,-2,Gravity.BOTTOM);dock.setMargins(dp(side?8:16),dp(8),dp(side?8:16),dp(12));contentHost.addView(nav,dock);
        root.setPointerIcon(pointerTheme());setContentView(root);root.requestApplyInsets();scroll.post(()->scroll.scrollTo(0,previousScroll));
    }
    private static class TabSymbol extends View {
        private final String name;private final Paint pen=new Paint(Paint.ANTI_ALIAS_FLAG);
        TabSymbol(Context c,String name,int color){super(c);this.name=name;pen.setColor(color);pen.setStyle(Paint.Style.STROKE);pen.setStrokeWidth(1.5f);pen.setStrokeCap(Paint.Cap.ROUND);}
        @Override protected void onDraw(Canvas canvas){super.onDraw(canvas);canvas.save();canvas.scale(getWidth()/24f,getHeight()/24f);
            if(name.equals("Overview")||name.equals("Apps")){for(int x:new int[]{4,14})for(int y:new int[]{4,14})canvas.drawRoundRect(x,y,x+6,y+6,1,1,pen);}
            else if(name.equals("Hardware")){canvas.drawRoundRect(6,6,18,18,2,2,pen);for(int k:new int[]{9,15}){canvas.drawLine(k,2,k,6,pen);canvas.drawLine(k,18,k,22,pen);canvas.drawLine(2,k,6,k,pen);canvas.drawLine(18,k,22,k,pen);}}
            else if(name.equals("Activity")){Path path=new Path();path.moveTo(2,12);path.lineTo(7,12);path.lineTo(10,5);path.lineTo(14,19);path.lineTo(17,12);path.lineTo(22,12);canvas.drawPath(path,pen);}
            else{canvas.drawCircle(6,12,1,pen);canvas.drawCircle(12,12,1,pen);canvas.drawCircle(18,12,1,pen);}
            canvas.restore();}

    }
    private void overview(JSONObject r){
        boolean active=running();SharedPreferences g=prefs();
        boolean allFiles=Build.VERSION.SDK_INT>=30&&Environment.isExternalStorageManager();
        int guarded=g.getStringSet("guard_trees",Collections.<String>emptySet()).size();
        boolean on=active&&(allFiles||guarded>0);
        TextView eye=text(body,on?"AUTOPILOT · ON, SILENT":active?"MONITORING · NEEDS ONE SWITCH":"YOUR PHONE, AT A GLANCE",11,on?GREEN:AMBER,true);eye.setLetterSpacing(.14f);gap(body,14);
        LinearLayout hero=new LinearLayout(this);hero.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout words=column();TextView h=text(words,"quiet guard.\nnothing to approve.",32,TEXT,false);h.setLetterSpacing(-.02f);gap(words,10);
        text(words,"finds it, removes it, tells you why. leaves what your phone needs.",14,MUTED,false);
        hero.addView(words,new LinearLayout.LayoutParams(0,-2,1));
        Orbit orbit=new Orbit(this,AMBER,LINE,BG,!g.getBoolean("signal_reduced",false)&&android.animation.ValueAnimator.areAnimatorsEnabled());orbit.setContentDescription(on?"protection active":"protection waiting");
        LinearLayout.LayoutParams op=new LinearLayout.LayoutParams(dp(118),dp(118));op.leftMargin=dp(10);hero.addView(orbit,op);body.addView(hero);gap(body,22);
        LinearLayout ap=card("Autopilot");
        LinearLayout nums=new LinearLayout(this);
        stat(nums,String.valueOf(g.getLong("shield_removed",0)),"removed automatically");stat(nums,String.valueOf(g.getLong("shield_checked",0)),"files checked");ap.addView(nums);gap(ap,12);
        int[] bud=Shield.budget(this);
        row(ap,"Tuned to this phone",ShieldRules.tierName(bud[0])+(bud[3]==1?" · gentle (hot, low or saving battery)":"")+" · "+bud[1]+" files per pass");
        row(ap,"Reach",allFiles?"all shared storage":guarded>0?guarded+" granted folder"+(guarded>1?"s":""):"not yet granted");
        row(ap,"Kept safe","Android/, hidden and firmware folders");
        row(ap,"Last pass",date(g.getLong("shield_last",0)));
        if(!allFiles){gap(ap,4);text(ap,"Android needs one switch before anything can be removed for you. After that it runs on its own.",13,MUTED,false);
            button(ap,"Allow all files access (one time)",true,()->{try{startActivity(new Intent(android.provider.Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,android.net.Uri.parse("package:"+getPackageName())));}catch(RuntimeException e){startActivity(new Intent(android.provider.Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION));}});
            button(ap,"Or guard one folder",false,()->startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE),45));}
        if(!active)button(ap,"Start protection",allFiles,()->toggle(true));
        JSONArray log;try{log=new JSONArray(g.getString("shield_log","[]"));}catch(JSONException e){log=new JSONArray();}
        if(log.length()>0){LinearLayout l=card("Removed recently");for(int i=log.length()-1;i>=Math.max(0,log.length()-5);i--){JSONObject x=log.optJSONObject(i);if(x==null)continue;text(l,x.optString("title"),15,TEXT,true);text(l,x.optString("detail")+" · "+date(x.optLong("t")),12,MUTED,false);gap(l,10);}}
        LinearLayout mem=card("Memory");
        long memLast=g.getLong("memory_last",0);String memSkip=g.getString("memory_skipped","");
        text(mem,!allFiles?"waiting for all files access":memSkip.isEmpty()?(memLast==0?"starting on the next pass":"kept"):"waiting: "+memSkip,18,TEXT,true);gap(mem,6);
        text(mem,"photos, pictures and documents stay on this phone with their earlier versions. identical bytes are stored once. if files start being encrypted, they are put back on their own.",13,MUTED,false);
        row(mem,"Files held",String.valueOf(g.getInt("memory_files",0)));row(mem,"Earlier versions",String.valueOf(g.getInt("memory_versions",0)));
        row(mem,"Space used",String.format(Locale.ROOT,"%.1f MB",g.getLong("memory_disk",0)/1048576.0));row(mem,"Last kept",date(memLast));
        if(g.getInt("memory_undo_count",0)>0)row(mem,"Ransomware undo",g.getInt("memory_undo_count",0)+" files put back · "+date(g.getLong("memory_undo_t",0)));
        for(String changed:Memory.recentlyChanged(this,3)){final String path=changed;button(mem,"Keep earlier "+new java.io.File(path).getName(),false,()->new Thread(()->{String msg;try{msg="Saved as "+Memory.keepEarlier(this,path).getName()+" next to the file. The current one was not touched.";}catch(Exception e){msg="Could not put it back: "+e.getMessage();}final String m=msg;runOnUiThread(()->{new AlertDialog.Builder(this).setMessage(m).setPositiveButton("OK",null).show();});}).start());}
        LinearLayout status=card("Protection");text(status,active?"Local watch is running":"Local watch is paused",18,TEXT,true);gap(status,6);text(status,"Checks run every 15 minutes, after app installs and at start-up, with or without a connection.",14,MUTED,false);
        button(status,busy?"Checking…":"Check now",!allFiles&&active?false:true,()->audit());if(active)button(status,"Pause protection",false,()->toggle(false));
        LinearLayout health=card("Device posture");row(health,"Screen lock",r.has("secure_lock")?(r.optBoolean("secure_lock")?"Secure lock set":"Needs review"):"Not checked");row(health,"Connection",r.has("validated_network")?(r.optBoolean("validated_network")?"Internet validated":"Offline / unvalidated"):"Not checked");row(health,"Last audit",date(r.optLong("generated_at_ms",0)));
        String error=g.getString("last_error","");if(!error.isEmpty()){LinearLayout err=card("Needs attention");text(err,error,14,AMBER,false);}
        text(body,"Quiet, not hidden. Android shows one low monitoring notification. It cannot uninstall other apps silently; those stay as review prompts.",12,MUTED,false);
    }
    /** Living shield: a sweep that circles the ring, two satellites, a breathing core. One 42 s loop (7 sweeps, 3 and 2 orbits, 10 breaths) so it never jumps; runs only while attached. */
    private static class Orbit extends View {
        private final Paint ring=new Paint(Paint.ANTI_ALIAS_FLAG),sweep=new Paint(Paint.ANTI_ALIAS_FLAG),dot=new Paint(Paint.ANTI_ALIAS_FLAG),glow=new Paint(Paint.ANTI_ALIAS_FLAG),core=new Paint(Paint.ANTI_ALIAS_FLAG),pen=new Paint(Paint.ANTI_ALIAS_FLAG);
        private final int accent,line,bg;private final boolean motion;private float t;private android.animation.ValueAnimator anim;
        Orbit(Context c,int accent,int line,int bg,boolean motion){super(c);this.accent=accent;this.line=line;this.bg=bg;this.motion=motion;
            ring.setStyle(Paint.Style.STROKE);ring.setColor(line);ring.setStrokeWidth(2f);sweep.setStyle(Paint.Style.STROKE);sweep.setStrokeCap(Paint.Cap.ROUND);
            dot.setColor(accent);glow.setColor(accent);pen.setColor(accent);pen.setStyle(Paint.Style.STROKE);pen.setStrokeJoin(Paint.Join.ROUND);pen.setStrokeCap(Paint.Cap.ROUND);setLayerType(LAYER_TYPE_HARDWARE,null);}
        @Override protected void onAttachedToWindow(){super.onAttachedToWindow();if(!motion)return;anim=android.animation.ValueAnimator.ofFloat(0f,1f);anim.setDuration(42000);anim.setRepeatCount(android.animation.ValueAnimator.INFINITE);anim.setInterpolator(new android.view.animation.LinearInterpolator());anim.addUpdateListener(a->{t=(float)a.getAnimatedValue();invalidate();});anim.start();}
        @Override protected void onDetachedFromWindow(){if(anim!=null)anim.cancel();super.onDetachedFromWindow();}
        @Override protected void onDraw(Canvas cv){float w=getWidth(),h=getHeight(),cx=w/2,cy=h/2,r=Math.min(w,h)/2-3,inner=r*0.72f;
            cv.drawCircle(cx,cy,r,ring);cv.drawCircle(cx,cy,inner,ring);
            float sweepDeg=(t*7f*360f)%360f;sweep.setStrokeWidth(r*0.12f);
            sweep.setShader(new SweepGradient(cx,cy,new int[]{Color.TRANSPARENT,Color.TRANSPARENT,(accent&0x00ffffff)|0x55000000,accent},new float[]{0f,.7f,.97f,1f}));
            cv.save();cv.rotate(sweepDeg-90,cx,cy);cv.drawArc(cx-r+r*0.06f,cy-r+r*0.06f,cx+r-r*0.06f,cy+r-r*0.06f,0,359,false,sweep);cv.restore();
            double a1=t*Math.PI*2*3-Math.PI/2,a2=-t*Math.PI*2*2;
            float x1=cx+(float)Math.cos(a1)*r*0.9f,y1=cy+(float)Math.sin(a1)*r*0.9f;glow.setShader(new RadialGradient(x1,y1,r*0.16f,(accent&0x00ffffff)|0x66000000,Color.TRANSPARENT,Shader.TileMode.CLAMP));cv.drawCircle(x1,y1,r*0.16f,glow);cv.drawCircle(x1,y1,r*0.045f,dot);
            dot.setAlpha(170);cv.drawCircle(cx+(float)Math.cos(a2)*inner,cy+(float)Math.sin(a2)*inner,r*0.025f,dot);dot.setAlpha(255);
            float breathe=1f+0.045f*(float)Math.sin(t*Math.PI*2*10),cr=r*0.36f*breathe;
            core.setShader(new RadialGradient(cx,cy,cr,(accent&0x00ffffff)|0x30000000,bg,Shader.TileMode.CLAMP));cv.drawCircle(cx,cy,cr,core);
            float s=r*0.30f/12f;cv.save();cv.translate(cx-12*s,cy-12*s);cv.scale(s,s);pen.setStrokeWidth(1.6f);
            Path p=new Path();p.moveTo(12,2);p.lineTo(4,5);p.lineTo(4,12);p.cubicTo(4,17,12,22,12,22);p.cubicTo(12,22,20,17,20,12);p.lineTo(20,5);p.close();cv.drawPath(p,pen);
            Path a=new Path();a.moveTo(8,15);a.lineTo(12,7);a.lineTo(16,15);a.moveTo(10,12);a.lineTo(14,12);cv.drawPath(a,pen);cv.restore();}
    }
    private void stat(LinearLayout row,String value,String label){LinearLayout s=column();s.setBackground(box(CARD,7));s.setPadding(dp(16),dp(16),dp(12),dp(16));text(s,value,30,TEXT,true);text(s,label,12,MUTED,false);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,-1,1);p.rightMargin=dp(8);row.addView(s,p);}
    private void row(LinearLayout c,String label,String value){LinearLayout l=new LinearLayout(this);l.setPadding(0,dp(8),0,dp(8));TextView a=new TextView(this);a.setText(label);a.setTextColor(MUTED);a.setTextSize(13);l.addView(a,new LinearLayout.LayoutParams(0,-2,1));TextView b=new TextView(this);b.setText(value);b.setTextColor(TEXT);b.setTextSize(13);b.setGravity(Gravity.END);l.addView(b,new LinearLayout.LayoutParams(0,-2,1));c.addView(l);}
    private void title(String name,String sub){text(body,name,34,TEXT,false);gap(body,8);text(body,sub,14,MUTED,false);gap(body,24);}
    private String date(long value){return value==0?"Not checked":DateFormat.getDateTimeInstance(DateFormat.SHORT,DateFormat.SHORT).format(new Date(value));}
    private void apps(JSONObject r){title("Access, in perspective.","Review access with context. Permission combinations alone do not prove malware.");
        LinearLayout action=card("Your controls");button(action,"Review Android app permissions",true,()->startActivity(new Intent(android.provider.Settings.ACTION_MANAGE_APPLICATIONS_SETTINGS)));button(action,"Review accessibility services",false,()->startActivity(new Intent(android.provider.Settings.ACTION_ACCESSIBILITY_SETTINGS)));
        button(action,prefs().getBoolean("show_packages",false)?"Show permission reviews":"Show visible installed apps and versions",false,()->{prefs().edit().putBoolean("show_packages",!prefs().getBoolean("show_packages",false)).apply();render();});
        if(prefs().getBoolean("show_packages",false)){JSONArray installed=r.optJSONArray("installed_apps");if(installed==null){text(body,"Run a new audit to collect installed app inventory.",14,MUTED,false);return;}int limit=Math.min(installed.length(),prefs().getInt("package_limit",100));text(body,"Showing "+limit+" of "+installed.length()+" apps visible to Android. Names/versions are inventory, not malware verdicts.",13,MUTED,false);for(int i=0;i<limit;i++){JSONObject app=installed.optJSONObject(i);if(app!=null){LinearLayout a=card(app.optBoolean("system")?"System package":"Installed app");text(a,app.optString("name"),17,TEXT,true);text(a,app.optString("package")+"\nVersion "+app.optString("version"),12,MUTED,false);}}if(limit<installed.length())button(body,"Show next 100 apps",false,()->{prefs().edit().putInt("package_limit",limit+100).apply();render();});return;}
        JSONArray list=r.optJSONArray("permission_reviews");if(list==null||list.length()==0){LinearLayout c=card("Permission reviews");text(c,r.has("generated_at_ms")?"No selected permission combinations found in this audit.":"Run an audit to review granted permissions.",15,TEXT,false);return;}
        for(int i=0;i<list.length();i++){JSONObject a=list.optJSONObject(i);if(a==null)continue;LinearLayout c=card("Review, not a verdict");text(c,a.optString("package"),16,TEXT,true);gap(c,8);text(c,a.optString("review"),14,MUTED,false);final String pkg=a.optString("package");button(c,"Open app details",false,()->startActivity(new Intent(android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS,android.net.Uri.parse("package:"+pkg))));}
    }
    private void hardware(JSONObject r){title("This device. Precisely scoped.","Local, API-reported specs for this device. Unsupported sensors stay unavailable.");LinearLayout c=card("This device");row(c,"Model",Build.MODEL);row(c,"Android API",String.valueOf(Build.VERSION.SDK_INT));android.os.BatteryManager bm=(android.os.BatteryManager)getSystemService(BATTERY_SERVICE);int capacity=bm==null?-1:bm.getIntProperty(android.os.BatteryManager.BATTERY_PROPERTY_CAPACITY);row(c,"Battery charge",capacity>=0&&capacity<=100?capacity+"%":"Unavailable");
        text(c,"Android reports whole percentage points; fractional charge is unavailable. This estimates remaining charge, not battery health.",12,MUTED,false);
        Intent battery=registerReceiver(null,new IntentFilter(Intent.ACTION_BATTERY_CHANGED));if(battery!=null){row(c,"Battery temperature",(battery.getIntExtra("temperature",0)/10.0)+" °C (reported)");row(c,"Voltage",battery.getIntExtra("voltage",0)+" mV (reported)");}
        long now=SystemClock.elapsedRealtime(),rx=android.net.TrafficStats.getTotalRxBytes(),tx=android.net.TrafficStats.getTotalTxBytes();
        if(netTime>0&&now>netTime&&rx>=netRx&&tx>=netTx){double seconds=(now-netTime)/1000.0;row(c,"Download traffic",String.format(java.util.Locale.ROOT,"%.2f Mbps",(rx-netRx)*8/seconds/1000000));row(c,"Upload traffic",String.format(java.util.Locale.ROOT,"%.2f Mbps",(tx-netTx)*8/seconds/1000000));}else row(c,"Network traffic","Sampling; leave Hardware open briefly");netTime=now;netRx=rx;netTx=tx;
        text(c,"Observed aggregate network byte rates. Not an internet speed test, advertised link rate or guaranteed capacity; VPN/interface accounting may differ.",12,MUTED,false);row(c,"Secure lock",r.has("secure_lock")?String.valueOf(r.optBoolean("secure_lock")):"Not checked");
        JSONObject hw=r.optJSONObject("hardware");LinearLayout specs=card("Adaptive hardware specifications");if(hw==null){text(specs,"Run an audit to collect this device’s reported specifications.",14,MUTED,false);}else{row(specs,"Manufacturer",hw.optString("manufacturer","Unavailable"));row(specs,"SoC / CPU",hw.optString("soc","Unavailable"));row(specs,"Logical processors",String.valueOf(hw.optInt("logical_processors")));row(specs,"RAM",String.format(java.util.Locale.ROOT,"%.1f GiB total · %.1f GiB available",hw.optLong("ram_total_bytes")/1073741824.0,hw.optLong("ram_available_bytes")/1073741824.0));row(specs,"Data volume",String.format(java.util.Locale.ROOT,"%.1f GiB total · %.1f GiB available",hw.optLong("data_volume_total_bytes")/1073741824.0,hw.optLong("data_volume_available_bytes")/1073741824.0));row(specs,"Display",hw.optInt("display_width_px")+" × "+hw.optInt("display_height_px")+" px · "+hw.optInt("density_dpi")+" dpi (app display metrics)");row(specs,"Security patch",hw.optString("security_patch","Unavailable"));JSONObject gpu=hw.optJSONObject("gpu");if(gpu!=null){row(specs,"GPU renderer",gpu.optString("renderer","Unavailable"));row(specs,"GPU vendor",gpu.optString("vendor","Unavailable"));row(specs,"Graphics API",gpu.optString("api","Unavailable"));}row(specs,"Thermal severity",String.valueOf(hw.optInt("thermal_status_code",-1)));text(specs,hw.optString("thermal_scope")+"\n\n"+hw.optString("sensor_limits"),12,MUTED,false);}
        JSONArray usb=r.optJSONArray("usb_host_devices");LinearLayout u=card("USB host devices");if(usb==null||usb.length()==0)text(u,"No USB host devices observed. A laptop connected for debugging is not a USB peripheral on this phone.",14,MUTED,false);else for(int i=0;i<usb.length();i++){JSONObject d=usb.optJSONObject(i);row(u,"USB device",d.optInt("vendor")+":"+d.optInt("product"));}
        LinearLayout limits=card("Platform boundary");text(limits,"Windows uses Defender, process monitoring and system file access. Android isolates apps. This app cannot quarantine another app's private files, inspect arbitrary processes, map building wiring or protect every nearby device.",14,MUTED,false);button(limits,"Open security settings",false,()->startActivity(new Intent(android.provider.Settings.ACTION_SECURITY_SETTINGS)));
    }
    private void activity(JSONObject r){title("Changes, kept in context.","The latest local observations. App changes can be legitimate updates or removals.");LinearLayout c=card("Latest audit");row(c,"Checked",date(r.optLong("generated_at_ms",0)));row(c,"Initial baseline",r.has("baseline_initialized")?(r.optBoolean("baseline_initialized")?"Already established":"Created this audit"):"Not checked");
        for(String key:new String[]{"added_packages","removed_packages","updated_packages","findings"}){LinearLayout l=card(key.replace('_',' '));JSONArray a=r.optJSONArray(key);if(a==null||a.length()==0)text(l,"None in the latest audit.",14,MUTED,false);else for(int i=0;i<a.length();i++){text(l,a.optString(i),14,TEXT,false);gap(l,8);}}
        JSONArray history=r.optJSONArray("event_history");LinearLayout log=card("Recent app changes");
        if(history==null||history.length()==0)text(log,"No changes recorded yet. Updates will remain here across later audits.",14,MUTED,false);
        else for(int i=history.length()-1;i>=Math.max(0,history.length()-20);i--){JSONObject event=history.optJSONObject(i);if(event!=null){text(log,event.optString("kind")+" · "+event.optString("package"),13,TEXT,false);text(log,date(event.optLong("time_ms",0)),11,MUTED,false);gap(log,10);}}
        button(c,"Export local report",false,()->{Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/json").putExtra(Intent.EXTRA_TITLE,"aureon-phone-report.json");startActivityForResult(i,44);});
    }
    private void tools(){title("Less noise. Useful tools.","Useful checks, with honest boundaries.");LinearLayout scan=card("Offline file check");text(scan,"Check a selected file",19,TEXT,true);gap(scan,8);text(scan,"Calculate SHA-256 and compare with a blocklist you import. No hash match is not a clean verdict. Files stay on this phone.",14,MUTED,false);button(scan,"Choose a file to check",true,()->pick(41));button(scan,"Import trusted SHA-256 blocklist",false,()->pick(42));button(scan,"Guard a folder automatically",false,()->startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE),45));
        text(scan,"Android permits only folders you explicitly grant. A guarded folder is checked on every pass against built-in rules and your imported list; matches are deleted automatically. It is not Windows Defender or system-wide antivirus.",12,MUTED,false);
        button(scan,"Create metadata-clean image copy",false,()->startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("image/*"),46));
        text(scan,"JPEG/PNG only, up to 24 megapixels. Creates a new PNG without copying source EXIF/XMP/comments and keeps the original. Visible names, watermarks and all fingerprints cannot be guaranteed removed.",12,MUTED,false);text(scan,prefs().getString("file_result","No file checked yet."),13,MUTED,false);
        LinearLayout style=card("Your Aureon interface");text(style,frost?"Frost":"Signal",22,TEXT,false);gap(style,8);text(style,"Choose a clear light surface or quiet ink and lime. These preferences affect Aureon only.",14,MUTED,false);
        button(style,prefs().getBoolean("copper",false)?"Return to Signal / Frost":"Use Copper warm theme",false,()->{prefs().edit().putBoolean("copper",!prefs().getBoolean("copper",false)).apply();render();});
        text(style,"External mouse pointer (Aureon only)",17,TEXT,true);for(String pointer:new String[]{"system","lime","precision"}){final String choice=pointer;button(style,"Pointer: "+pointer,false,()->{prefs().edit().putString("pointer_style",choice).apply();render();});}
        text(style,"Navigation placement",17,TEXT,true);
        for(String position:new String[]{"auto","bottom","left","right"}){final String choice=position;button(style,(prefs().getString("nav_position","bottom").equals(choice)?"✓ ":"")+"Dock: "+choice,false,()->{prefs().edit().putString("nav_position",choice).apply();render();});}
        text(style,"Side docks reserve content space. On very narrow or short windows they fall back to bottom navigation to preserve access. Auto uses a rail on tablets.",12,MUTED,false);
        button(style,prefs().getBoolean("nav_large",false)?"Use compact navigation labels":"Use larger navigation labels",false,()->{prefs().edit().putBoolean("nav_large",!prefs().getBoolean("nav_large",false)).apply();render();});
        button(style,"Internet speed test in browser",false,()->new AlertDialog.Builder(this).setTitle("Open Cloudflare speed test?").setMessage("This opens an external website and transfers test data. It uses your connection and Cloudflare's service/privacy rules. Aureon does not upload files.").setPositiveButton("Open test",(d,w)->startActivity(new Intent(Intent.ACTION_VIEW,android.net.Uri.parse("https://speed.cloudflare.com/")))).setNegativeButton("Cancel",null).show());
        button(style,frost?"Use Signal dark":"Use Frost light",false,()->{prefs().edit().putBoolean("signal_frost",!frost).apply();render();});
        button(style,prefs().getBoolean("signal_reduced",false)?"Enable subtle transitions":"Reduce interface motion",false,()->{prefs().edit().putBoolean("signal_reduced",!prefs().getBoolean("signal_reduced",false)).apply();render();});
        LinearLayout scope=card("Feature parity");text(scope,"Available: app permission review, package changes, local file hash checks, device vitals, USB host inventory, local reports and background audits.\n\nWindows-only here: system-wide Defender/YARA scans, quarantine, process/firewall enforcement, persistence monitoring, clipboard monitoring and Studio desktop changes.\n\nPi reports and electrical telemetry remain on the Windows dashboard. No shared-device transport has been configured.",14,MUTED,false);
    }
    private void pick(int request){startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*"),request);}
    private void toggle(boolean enable){prefs().edit().putBoolean("enabled",enable).apply();if(enable){AuditJob.schedule(this);try{startForegroundService(new Intent(this,GuardService.class));}catch(RuntimeException e){prefs().edit().putString("last_error",e.toString()).apply();}audit();}else{AuditJob.cancel(this);stopService(new Intent(this,GuardService.class));render();}}
    private void audit(){if(busy)return;busy=true;render();new Thread(()->{Audit.attempt(this);runOnUiThread(()->{busy=false;render();});},"aureon-manual-audit").start();}
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(result!=RESULT_OK||data==null||data.getData()==null)return;final android.net.Uri uri=data.getData();if(request==46){cleanSource=uri;startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("image/png").putExtra(Intent.EXTRA_TITLE,"aureon-clean-copy.png"),47);return;}new Thread(()->{String message;try{
        if(request==47){if(cleanSource==null)throw new IOException("Choose the source image again");message=LocalTools.cleanImage(this,cleanSource,uri);cleanSource=null;}
        else if(request==45){try{getContentResolver().takePersistableUriPermission(uri,Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION);}catch(SecurityException ignored){}
            Set<String> trees=new HashSet<>(prefs().getStringSet("guard_trees",Collections.<String>emptySet()));trees.add(uri.toString());prefs().edit().putStringSet("guard_trees",trees).putLong("shield_since",0).apply();
            JSONObject res=Shield.sweep(this);message="This folder is now guarded automatically.\n"+res.optInt("checked")+" checked, "+res.optInt("removed")+" removed just now. New files are checked on every pass and anything found is deleted without asking. Android/ and hidden folders are never touched.";}
        else if(request==44){try(OutputStream out=getContentResolver().openOutputStream(uri)){if(out==null)throw new IOException("Cannot open export");out.write(Audit.latest(this).getBytes("UTF-8"));}message="Report exported to your selected location.";}
        else if(request==42){Set<String> hashes;try(InputStream in=getContentResolver().openInputStream(uri)){hashes=FileChecks.blocklist(in);}prefs().edit().putStringSet("hashes",hashes).apply();message="Imported "+hashes.size()+" operator-supplied hashes. Their source is not independently verified.";}
        else {String hex;try(InputStream in=getContentResolver().openInputStream(uri)){hex=FileChecks.hash(in,256L*1024*1024);}boolean match=prefs().getStringSet("hashes",Collections.emptySet()).contains(hex);message=(match?"MATCH in imported blocklist. Review the source and avoid opening the file.":"No imported blocklist match. This does not establish safety.")+"\n\nSHA-256\n"+hex;}

        }catch(Exception e){message="Check failed: "+e.getMessage();}prefs().edit().putString("file_result",message).apply();final String toast=message;runOnUiThread(()->{render();Toast.makeText(this,toast,Toast.LENGTH_LONG).show();});},"aureon-file-check").start();}
    @Override public void onResume(){super.onResume();
        if(prefs().getBoolean("enabled",false)&&!running()){
            AuditJob.schedule(this);
            try{startForegroundService(new Intent(this,GuardService.class));}
            catch(RuntimeException e){prefs().edit().putString("last_error",e.toString()).apply();}
        }
        handler.removeCallbacks(updater);handler.postDelayed(updater,400);}
    @Override public void onPause(){handler.removeCallbacks(updater);super.onPause();}
}
