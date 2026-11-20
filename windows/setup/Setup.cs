using System;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Security.Cryptography;
using System.Diagnostics;
using System.Drawing;
using System.Windows.Forms;
using System.Threading.Tasks;
[assembly: AssemblyTitle("aureon.defender Setup")]
[assembly: AssemblyVersion("0.4.8.0")]
[assembly: AssemblyFileVersion("0.4.8.0")]
internal static class Setup {
    // Filled by the build from the exact published ZIP.
    const string PayloadDigest="__PAYLOAD_SHA256__";
    static string Extract(string target) {
        Directory.CreateDirectory(target);
        string root=Path.GetFullPath(target).TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar;
        using(var stream=Assembly.GetExecutingAssembly().GetManifestResourceStream("Payload")) {
            using(var hash=SHA256.Create()) {
                string actual=BitConverter.ToString(hash.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
                if(actual!=PayloadDigest)throw new InvalidDataException("The installer payload did not match its integrity check.");
            }
        }
        using(var stream=Assembly.GetExecutingAssembly().GetManifestResourceStream("Payload"))
        using(var zip=new ZipArchive(stream,ZipArchiveMode.Read)) {
            long total=0;
            foreach(var entry in zip.Entries) {
                total+=entry.Length;if(total>600L*1024*1024)throw new InvalidDataException("Unexpected payload size.");
                string dest=Path.GetFullPath(Path.Combine(root,entry.FullName.Replace('/',Path.DirectorySeparatorChar)));
                if(!dest.StartsWith(root,StringComparison.OrdinalIgnoreCase))throw new InvalidDataException("Invalid archive path.");
                if(entry.FullName.EndsWith("/")||entry.FullName.EndsWith("\\")){Directory.CreateDirectory(dest);continue;}
                Directory.CreateDirectory(Path.GetDirectoryName(dest));
                using(var source=entry.Open())using(var output=new FileStream(dest,FileMode.CreateNew,FileAccess.Write))source.CopyTo(output);
            }
        }
        string exe=Path.Combine(root,"aureon.defender","aureon.defender.exe");
        if(!File.Exists(exe))throw new InvalidDataException("Application missing from payload.");
        return exe;
    }
    [STAThread] static int Main(string[] args) {
        if(args.Length==1&&args[0].StartsWith("/verify=",StringComparison.OrdinalIgnoreCase)) {
            string target=Path.GetFullPath(args[0].Substring(8));
            try {string exe=Extract(target);File.WriteAllText(Path.Combine(target,"verification.json"),"{\"payload_verified\":true,\"application_present\":true,\"installation_performed\":false}");return 0;}
            catch(Exception ex){File.WriteAllText(Path.Combine(target,"verification-error.txt"),ex.Message);return 1;}
        }
        Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
        var form=new Form {Text="aureon.defender Setup",ClientSize=new Size(480,240),StartPosition=FormStartPosition.CenterScreen,FormBorderStyle=FormBorderStyle.FixedDialog,MaximizeBox=false,BackColor=Color.FromArgb(13,16,18),ForeColor=Color.FromArgb(241,243,242)};
        try{form.Icon=Icon.ExtractAssociatedIcon(Application.ExecutablePath);}catch{}
        var heading=new Label {Text="aureon.defender",Font=new Font("Segoe UI",24),Location=new Point(28,24),AutoSize=true};
        var status=new Label {Text="Preparing your installation…",Location=new Point(30,88),Size=new Size(420,62),Font=new Font("Segoe UI",11)};
        var progress=new ProgressBar {Location=new Point(30,168),Size=new Size(420,8),Style=ProgressBarStyle.Marquee};
        var note=new Label {Text="Windows will ask you to approve the machine installation.",Location=new Point(30,192),Size=new Size(420,32),ForeColor=Color.FromArgb(217,255,112),Font=new Font("Segoe UI",9)};
        form.Controls.AddRange(new Control[]{heading,status,progress,note});
        bool working=true;int result=1;form.FormClosing+=(s,e)=>{if(working)e.Cancel=true;};
        form.Shown+=async(s,e)=> {
            try {
                string stage=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"Aureon","Installers",Guid.NewGuid().ToString("N"));
                string exe=await Task.Run(()=>Extract(stage));
                status.Text="Starting installation. Approve the Windows administrator prompt to continue.";
                var start=new ProcessStartInfo(exe,"install") {UseShellExecute=true,WorkingDirectory=Path.GetDirectoryName(exe)};
                using(var child=Process.Start(start)){await Task.Run(()=>child.WaitForExit());if(child.ExitCode!=0)throw new Exception("The application installer did not finish. No success is claimed. See the Aureon log or try the portable ZIP.");}
                result=0;working=false;form.Close();
            } catch(Exception ex){working=false;progress.Style=ProgressBarStyle.Blocks;status.Text="Installation did not complete.";note.Text="Your download remains available to retry.";MessageBox.Show(form,ex.Message,"aureon.defender Setup",MessageBoxButtons.OK,MessageBoxIcon.Information);form.Close();}
        };
        Application.Run(form);return result;
    }
}
