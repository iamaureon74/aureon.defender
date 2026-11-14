# Sets the desktop wallpaper on every monitor through IDesktopWallpaper (Windows 8+), which redraws immediately.
# The older SystemParametersInfo route can update the registry without Explorer repainting, leaving a black desktop.
#   powershell -File wallpaper.ps1 -Path C:\x.jpg -Position Fill
param([Parameter(Mandatory)][string]$Path, [ValidateSet("Center","Tile","Stretch","Fit","Fill","Span")][string]$Position = "Fill")
$ErrorActionPreference = "Stop"
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
[ComImport, Guid("B92B56A9-8B55-4E14-9A89-0199BBB6F93B"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IDesktopWallpaper {
    void SetWallpaper([MarshalAs(UnmanagedType.LPWStr)] string monitorID, [MarshalAs(UnmanagedType.LPWStr)] string wallpaper);
    [return: MarshalAs(UnmanagedType.LPWStr)] string GetWallpaper([MarshalAs(UnmanagedType.LPWStr)] string monitorID);
    [return: MarshalAs(UnmanagedType.LPWStr)] string GetMonitorDevicePathAt(uint monitorIndex);
    uint GetMonitorDevicePathCount();
    void GetMonitorRECT([MarshalAs(UnmanagedType.LPWStr)] string monitorID, out RECT displayRect);
    void SetBackgroundColor(uint color);
    uint GetBackgroundColor();
    void SetPosition(int position);
    int GetPosition();
    void SetSlideshow(IntPtr items);
    IntPtr GetSlideshow();
    void SetSlideshowOptions(int options, uint slideshowTick);
    void GetSlideshowOptions(out int options, out uint slideshowTick);
    void AdvanceSlideshow([MarshalAs(UnmanagedType.LPWStr)] string monitorID, int direction);
    int GetStatus();
    bool Enable(bool enable);
}
[StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
[ComImport, Guid("C2CF3110-460E-4fc1-B9D0-8A1C0C9CC4BD")] public class DesktopWallpaperClass { }
public static class AureonWallpaper {
    public static string Set(string path, int position) {
        var w = (IDesktopWallpaper)new DesktopWallpaperClass();
        w.Enable(true);
        w.SetPosition(position);
        // null = every attached monitor. Iterating device paths can hit a remembered-but-detached monitor (0x80070002).
        w.SetWallpaper(null, path);
        return path;
    }
}
"@
$pos = @{Center=0; Tile=1; Stretch=2; Fit=3; Fill=4; Span=5}[$Position]
[AureonWallpaper]::Set((Resolve-Path $Path).Path, $pos)
