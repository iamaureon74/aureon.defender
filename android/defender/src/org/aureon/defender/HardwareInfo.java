package org.aureon.defender;
import android.content.*;
import android.app.ActivityManager;
import android.os.*;
import android.opengl.*;
import org.json.*;

/** Local API-reported capabilities. Missing/private hardware sensors are never invented. */
public final class HardwareInfo {
 private HardwareInfo() {}
 public static JSONObject collect(Context c) throws Exception {
  JSONObject result=new JSONObject();
  result.put("manufacturer",Build.MANUFACTURER).put("model",Build.MODEL).put("soc",Build.SOC_MANUFACTURER+" "+Build.SOC_MODEL).put("abis",new JSONArray(java.util.Arrays.asList(Build.SUPPORTED_ABIS))).put("logical_processors",Runtime.getRuntime().availableProcessors()).put("security_patch",Build.VERSION.SECURITY_PATCH);
  ActivityManager am=(ActivityManager)c.getSystemService(Context.ACTIVITY_SERVICE);ActivityManager.MemoryInfo memory=new ActivityManager.MemoryInfo();am.getMemoryInfo(memory);result.put("ram_total_bytes",memory.totalMem).put("ram_available_bytes",memory.availMem);
  StatFs storage=new StatFs(c.getFilesDir().getAbsolutePath());result.put("data_volume_total_bytes",storage.getTotalBytes()).put("data_volume_available_bytes",storage.getAvailableBytes());
  android.util.DisplayMetrics dm=c.getResources().getDisplayMetrics();result.put("display_width_px",dm.widthPixels).put("display_height_px",dm.heightPixels).put("density_dpi",dm.densityDpi);
  PowerManager pm=(PowerManager)c.getSystemService(Context.POWER_SERVICE);result.put("thermal_status_code",pm==null?-1:pm.getCurrentThermalStatus()).put("thermal_scope","OS mitigation severity, not CPU/GPU temperature. A zero status does not prove every sensor is supported.");
  result.put("gpu",gpu()).put("sensor_limits","CPU/GPU die temperatures, fan RPM, battery charge caps and firmware-level security controls are not exposed uniformly to ordinary Android apps.").put("source","Android Build, ActivityManager, StatFs, display metrics, PowerManager and EGL/GLES driver strings; local observations, not hardware attestation.");
  return result;
 }
 private static JSONObject gpu() {
  JSONObject result=new JSONObject();EGLDisplay display=EGL14.EGL_NO_DISPLAY;EGLContext context=EGL14.EGL_NO_CONTEXT;EGLSurface surface=EGL14.EGL_NO_SURFACE;
  try{
   display=EGL14.eglGetDisplay(EGL14.EGL_DEFAULT_DISPLAY);int[] versions=new int[2];if(!EGL14.eglInitialize(display,versions,0,versions,1))throw new Exception("EGL unavailable");
   EGLConfig[] configs=new EGLConfig[1];int[] count=new int[1];int[] attributes={EGL14.EGL_RENDERABLE_TYPE,4,EGL14.EGL_SURFACE_TYPE,EGL14.EGL_PBUFFER_BIT,EGL14.EGL_RED_SIZE,8,EGL14.EGL_GREEN_SIZE,8,EGL14.EGL_BLUE_SIZE,8,EGL14.EGL_NONE};
   if(!EGL14.eglChooseConfig(display,attributes,0,configs,0,1,count,0)||count[0]==0)throw new Exception("No compatible EGL configuration");
   context=EGL14.eglCreateContext(display,configs[0],EGL14.EGL_NO_CONTEXT,new int[]{EGL14.EGL_CONTEXT_CLIENT_VERSION,2,EGL14.EGL_NONE},0);
   surface=EGL14.eglCreatePbufferSurface(display,configs[0],new int[]{EGL14.EGL_WIDTH,1,EGL14.EGL_HEIGHT,1,EGL14.EGL_NONE},0);
   if(!EGL14.eglMakeCurrent(display,surface,surface,context))throw new Exception("GPU context unavailable");
   result.put("renderer",GLES20.glGetString(GLES20.GL_RENDERER)).put("vendor",GLES20.glGetString(GLES20.GL_VENDOR)).put("api",GLES20.glGetString(GLES20.GL_VERSION)).put("status","driver_reported");
  }catch(Exception ex){try{result.put("status","unavailable").put("reason",ex.getMessage());}catch(Exception ignored){}}
  finally{if(display!=EGL14.EGL_NO_DISPLAY){EGL14.eglMakeCurrent(display,EGL14.EGL_NO_SURFACE,EGL14.EGL_NO_SURFACE,EGL14.EGL_NO_CONTEXT);if(surface!=EGL14.EGL_NO_SURFACE)EGL14.eglDestroySurface(display,surface);if(context!=EGL14.EGL_NO_CONTEXT)EGL14.eglDestroyContext(display,context);EGL14.eglTerminate(display);}}
  return result;
 }
}
