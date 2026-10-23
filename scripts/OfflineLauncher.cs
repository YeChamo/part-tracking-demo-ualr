// Offline packaging wrapper only. The embedded application and runtime are unchanged.
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Windows.Forms;

internal static class OfflineLauncher
{
    private const string Prefix = "PartTrackingDemoUALR/";
    private static readonly string LogPath = Path.Combine(Path.GetTempPath(), "UALR-offline-" + Guid.NewGuid().ToString("N") + ".log");
    private static readonly string[] Required = {
        "PartTrackingUALR.exe", "_runtime/python311.dll", "_runtime/vcruntime140.dll",
        "_runtime/vcruntime140_1.dll", "_runtime/ucrtbase.dll", "_runtime/base_library.zip",
        "_runtime/PySide6/QtCore.pyd", "_runtime/torch/lib/torch_cpu.dll",
        "_runtime/onnxruntime/capi/onnxruntime_pybind11_state.pyd",
        "models/yolox_nano.onnx", "models/yolox_nano.onnx.data", "models/yolox_s.onnx",
        "models/color/distilV4_student.onnx"
    };

    [STAThread]
    private static int Main(string[] args)
    {
        bool extractOnly = Array.IndexOf(args, "--extract-only") >= 0;
        try {
            Dictionary<string,string> manifest = ReadManifest();
            string destination = Path.Combine(Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location), "PartTrackingDemoUALR-" + manifest["version"]);
            for (int i=0; i<args.Length; i++) {
                if (args[i] == "--extract-only") continue;
                if (args[i] == "--destination" && i+1 < args.Length) destination = args[++i];
                else throw new ArgumentException("Use --extract-only and optionally --destination <new folder>.");
            }
            destination = Path.GetFullPath(destination);
            Log("Destination: " + destination);
            if (extractOnly) { Install(manifest, destination, null); return 0; }
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            using (LauncherForm form = new LauncherForm(manifest, destination)) Application.Run(form);
            return 0;
        } catch (Exception error) {
            Log(error.ToString());
            if (!extractOnly) MessageBox.Show(error.Message + "\n\nDetails: " + LogPath, "UALR demo setup", MessageBoxButtons.OK, MessageBoxIcon.Error);
            Console.Error.WriteLine(error.Message + "\nLog: " + LogPath);
            return 1;
        }
    }

    private static void Log(string message)
    {
        try { File.AppendAllText(LogPath, DateTime.Now.ToString("s") + " " + message + Environment.NewLine); } catch { }
    }

    private static Dictionary<string,string> ReadManifest()
    {
        Dictionary<string,string> result = new Dictionary<string,string>(StringComparer.Ordinal);
        using (Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("UALR.Manifest")) {
            if (stream == null) throw new InvalidDataException("Embedded package manifest is missing.");
            using (StreamReader reader = new StreamReader(stream, Encoding.UTF8)) {
                string line;
                while ((line = reader.ReadLine()) != null) {
                    int separator = line.IndexOf('=');
                    if (separator > 0) result.Add(line.Substring(0,separator), line.Substring(separator+1));
                }
            }
        }
        if (!result.ContainsKey("version") || !Regex.IsMatch(result["version"], @"^[0-9]+\.[0-9]+\.[0-9]+[a-zA-Z0-9.-]*$")) throw new InvalidDataException("Invalid package version.");
        foreach (string key in new string[] {"archive_sha256", "python_sha256", "exe_sha256"})
            if (!result.ContainsKey(key) || !Regex.IsMatch(result[key], "^[0-9a-f]{64}$")) throw new InvalidDataException("Invalid package checksum.");
        long length;
        if (!result.ContainsKey("archive_bytes") || !Int64.TryParse(result["archive_bytes"], out length) || length <= 0) throw new InvalidDataException("Invalid package size.");
        return result;
    }

    private static string Hash(Stream stream)
    {
        using (SHA256 hash = SHA256.Create()) return BitConverter.ToString(hash.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
    }

    private static FileStream OpenShared(string path)
    {
        for (int attempt=0; ; attempt++) {
            try { return new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.ReadWrite | FileShare.Delete); }
            catch (IOException) { if (attempt >= 3) throw; System.Threading.Thread.Sleep(200); }
        }
    }

    private static string ReadSharedText(string path)
    {
        using (StreamReader reader = new StreamReader(OpenShared(path))) return reader.ReadToEnd();
    }

    private static bool CoreReady(string folder, Dictionary<string,string> manifest)
    {
        foreach (string name in Required) {
            string file = Path.Combine(folder, name.Replace('/',Path.DirectorySeparatorChar));
            if (!File.Exists(file) || new FileInfo(file).Length == 0) return false;
        }
        using (FileStream stream = OpenShared(Path.Combine(folder,"_runtime","python311.dll")))
            if (Hash(stream) != manifest["python_sha256"]) return false;
        using (FileStream stream = OpenShared(Path.Combine(folder,"PartTrackingUALR.exe")))
            if (Hash(stream) != manifest["exe_sha256"]) return false;
        return true;
    }

    private static string SafeTarget(string root, string name)
    {
        string normalized = name.Replace('\\','/');
        if (!normalized.StartsWith(Prefix,StringComparison.Ordinal) || normalized.IndexOf(':') >= 0 || normalized.IndexOf('\0') >= 0)
            throw new InvalidDataException("Unsafe package entry: " + name);
        string relative = normalized.Substring(Prefix.Length);
        foreach (string part in relative.Split('/')) {
            if (part == ".." || part == "." || part.EndsWith(" ",StringComparison.Ordinal) || part.EndsWith(".",StringComparison.Ordinal))
                throw new InvalidDataException("Unsafe package path: " + name);
        }
        string target = Path.GetFullPath(Path.Combine(root,relative.Replace('/',Path.DirectorySeparatorChar)));
        string boundary = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        if (!target.StartsWith(boundary,StringComparison.OrdinalIgnoreCase) && !String.Equals(target,Path.GetFullPath(root),StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Package entry leaves its destination.");
        return target;
    }

    private static void Install(Dictionary<string,string> manifest, string destination, Action<int,string> progress)
    {
        string stamp = Path.Combine(destination,".ualr-offline.sha256");
        if (Directory.Exists(destination)) {
            if (File.Exists(stamp) && ReadSharedText(stamp).Trim() == manifest["archive_sha256"] && CoreReady(destination,manifest)) {
                Log("Verified cached installation."); return;
            }
            throw new IOException("The destination already exists and cannot be verified. Your files were preserved. Rename that folder or use --destination with a new folder: " + destination);
        }
        string parent = Path.GetDirectoryName(destination);
        if (String.IsNullOrEmpty(parent)) throw new IOException("Choose a new folder inside a writable directory.");
        Directory.CreateDirectory(parent);
        string staging = destination + ".staging-" + Guid.NewGuid().ToString("N");
        bool created = false;
        try {
            using (Stream payload = Assembly.GetExecutingAssembly().GetManifestResourceStream("UALR.PortableZip")) {
                if (payload == null || payload.Length != Int64.Parse(manifest["archive_bytes"])) throw new InvalidDataException("Embedded demo package is incomplete.");
                if (progress != null) progress(0,"Checking the complete offline package…");
                if (Hash(payload) != manifest["archive_sha256"]) throw new InvalidDataException("Embedded demo package failed its SHA-256 check.");
                payload.Position = 0;
                using (ZipArchive archive = new ZipArchive(payload,ZipArchiveMode.Read,true)) {
                    long total = 0;
                    foreach (ZipArchiveEntry entry in archive.Entries) {
                        SafeTarget(staging,entry.FullName);
                        if (((entry.ExternalAttributes >> 16) & 0xF000) == 0xA000) throw new InvalidDataException("Package symlinks are not supported.");
                        total = checked(total + entry.Length);
                    }
                    Directory.CreateDirectory(staging); created = true;
                    long copied = 0; int lastPercent = -1;
                    byte[] buffer = new byte[131072];
                    foreach (ZipArchiveEntry entry in archive.Entries) {
                        string target = SafeTarget(staging,entry.FullName);
                        if (entry.FullName.EndsWith("/",StringComparison.Ordinal)) { Directory.CreateDirectory(target); continue; }
                        Directory.CreateDirectory(Path.GetDirectoryName(target));
                        using (Stream input = entry.Open())
                        using (FileStream output = new FileStream(target,FileMode.CreateNew,FileAccess.Write,FileShare.None)) {
                            int count;
                            while ((count = input.Read(buffer,0,buffer.Length)) > 0) {
                                output.Write(buffer,0,count); copied += count;
                                int percent = total == 0 ? 0 : (int)(copied * 100 / total);
                                if (progress != null && percent != lastPercent) { lastPercent=percent; progress(percent,"Preparing the demo and its Python runtime… " + percent + "%"); }
                            }
                        }
                    }
                }
            }
            if (!CoreReady(staging,manifest)) throw new InvalidDataException("Extracted demo is missing or has damaged required files.");
            File.WriteAllText(Path.Combine(staging,".ualr-offline.sha256"),manifest["archive_sha256"] + Environment.NewLine,Encoding.ASCII);
            Directory.Move(staging,destination);
            created = false;
            Log("Complete package extracted and verified.");
        } finally {
            // Only remove the fresh GUID staging directory owned by this run.
            if (created && Path.GetFullPath(staging).StartsWith(destination + ".staging-",StringComparison.OrdinalIgnoreCase)) {
                try { Directory.Delete(staging,true); } catch (Exception error) { Log("Staging cleanup: " + error.Message); }
            }
        }
    }

    private sealed class LauncherForm : Form
    {
        private readonly Label status = new Label();
        private readonly ProgressBar progress = new ProgressBar();
        private bool working = true;
        public LauncherForm(Dictionary<string,string> manifest, string destination)
        {
            Text="UALR bottle tracking — offline setup"; ClientSize=new Size(560,145);
            FormBorderStyle=FormBorderStyle.FixedDialog; MaximizeBox=false; StartPosition=FormStartPosition.CenterScreen;
            status.SetBounds(20,20,520,52); status.Text="Preparing the complete demo. First launch can take a minute.";
            progress.SetBounds(20,90,520,24); Controls.Add(status); Controls.Add(progress);
            BackgroundWorker worker = new BackgroundWorker(); worker.WorkerReportsProgress=true;
            worker.DoWork += delegate { Install(manifest,destination,delegate(int value,string message) { worker.ReportProgress(value,message); }); };
            worker.ProgressChanged += delegate(object sender,ProgressChangedEventArgs e) { progress.Value=Math.Max(0,Math.Min(100,e.ProgressPercentage)); status.Text=(string)e.UserState; };
            worker.RunWorkerCompleted += delegate(object sender,RunWorkerCompletedEventArgs e) {
                working=false;
                if (e.Error != null) { Log(e.Error.ToString()); status.Text="Setup could not finish. Your existing files were preserved."; MessageBox.Show(this,e.Error.Message+"\n\nDetails: "+LogPath,"UALR demo setup",MessageBoxButtons.OK,MessageBoxIcon.Error); return; }
                try {
                    Process.Start(new ProcessStartInfo(Path.Combine(destination,"PartTrackingUALR.exe")) { WorkingDirectory=destination, UseShellExecute=false });
                    Close();
                } catch (Exception error) { Log(error.ToString()); status.Text="Demo files are ready, but launch failed."; MessageBox.Show(this,error.Message+"\n\nDetails: "+LogPath,"UALR demo",MessageBoxButtons.OK,MessageBoxIcon.Error); }
            };
            FormClosing += delegate(object sender,FormClosingEventArgs e) { if (working) { e.Cancel=true; status.Text="Please wait while the offline package finishes extracting."; } };
            Shown += delegate { worker.RunWorkerAsync(); };
        }
    }
}
