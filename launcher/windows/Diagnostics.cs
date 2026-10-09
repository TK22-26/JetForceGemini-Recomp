using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Win32;

namespace JfgLauncher
{
    internal sealed class SupportChoice
    {
        internal string Path, Label;
        internal bool Failed;
        public override string ToString() { return Label; }
    }

    internal sealed partial class SupportSession
    {
        internal static readonly string[] Files = { "launcher.log", "native.log", "system.log", "build.log", "controller.log", "crash.log", "hang.log", "breadcrumbs.log" };
        internal static bool Owned(string path) { return Regex.IsMatch(System.IO.Path.GetFileName(path), @"\A[0-9]{8}T[0-9]{9}-[0-9a-f]{32}\z") && (File.GetAttributes(path) & FileAttributes.ReparsePoint) == 0; }
        internal static List<SupportChoice> Sessions(string root)
        {
            List<SupportChoice> result = new List<SupportChoice>();
            if (!Directory.Exists(root)) return result;
            string[] paths = Directory.GetDirectories(root); Array.Sort(paths, StringComparer.Ordinal); Array.Reverse(paths);
            foreach (string path in paths) {
                if (!Owned(path)) continue;
                string log = SanitizeFile(System.IO.Path.Combine(path, "launcher.log"));
                string kind = log.Contains("stage=setup\n") ? "Setup" : "Game";
                string stage = "in progress";
                foreach (string line in log.Split('\n')) if (line.StartsWith("stage=", StringComparison.Ordinal)) stage = line.Substring(6);
                bool failed = log.Contains("stage=failed\n") || SanitizeFile(System.IO.Path.Combine(path, "native.log")).Contains("failure=") || File.Exists(System.IO.Path.Combine(path, "crash.log"));
                DateTime utc; string stamp = System.IO.Path.GetFileName(path).Substring(0, 18);
                string when = DateTime.TryParseExact(stamp, "yyyyMMddTHHmmssfff", CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal, out utc) ? utc.ToLocalTime().ToString("g") : stamp;
                result.Add(new SupportChoice { Path = path, Failed = failed, Label = when + "  |  " + kind + "  |  " + stage + (failed ? " (issue)" : "") });
            }
            return result;
        }
        internal static void Prune(string root)
        {
            int failed = 0, other = 0;
            foreach (SupportChoice item in Sessions(root)) {
                // Keep ten failed sessions independently of ten other sessions.
                if ((item.Failed ? ++failed : ++other) <= 10) continue;
                try {
                    foreach (string name in Files) {
                        string path = System.IO.Path.Combine(item.Path, name);
                        if (File.Exists(path) && (File.GetAttributes(path) & FileAttributes.ReparsePoint) == 0) File.Delete(path);
                    }
                    if (Directory.GetFileSystemEntries(item.Path).Length == 0) Directory.Delete(item.Path);
                } catch (IOException) { } catch (UnauthorizedAccessException) { }
            }
        }
        internal void SaveLines(string name, string text)
        {
            StringBuilder safe = new StringBuilder();
            foreach (string line in text.Split('\n')) if (line.Length <= 256 && SafeLine.IsMatch(line.TrimEnd('\r'))) safe.AppendLine(line.TrimEnd('\r'));
            if (safe.Length > MaximumBytes) throw new InvalidDataException("Diagnostic input is too large.");
            File.WriteAllText(System.IO.Path.Combine(DirectoryPath, name), safe.ToString(), new UTF8Encoding(false));
        }
        internal static string Hash(string path)
        {
            using (FileStream file = File.OpenRead(path)) using (SHA256 sha = SHA256.Create())
                return BitConverter.ToString(sha.ComputeHash(file)).Replace("-", "").ToLowerInvariant();
        }
        internal bool RuntimeDetails(string runtime, string profile)
        {
            string digest = Hash(runtime); Write("runtime_sha256=" + digest);
            string manifest = SanitizeFile(runtime + ".support");
            bool matched = manifest.Contains("build_runtime_sha256=" + digest + "\n");
            SaveLines("build.log", matched ? manifest : "build_identity=unavailable\n");
            try {
                StringBuilder settings = new StringBuilder();
                foreach (string line in ControllerProfile.Load(profile).Encode().TrimEnd('\n').Split('\n')) settings.Append("controller_").AppendLine(line);
                SaveLines("controller.log", settings.ToString());
            } catch (Exception) { Write("diagnostic=controller-unavailable"); }
            string helper = System.IO.Path.Combine(System.IO.Path.GetDirectoryName(runtime), "jfg-support-capture.exe");
            return matched && File.Exists(helper) && manifest.Contains("build_capture_sha256=" + Hash(helper) + "\n");
        }
        internal void SystemDetails()
        {
            StringBuilder lines = new StringBuilder("architecture=x64\n");
            lines.Append("cpu_threads=").Append(Environment.ProcessorCount.ToString(CultureInfo.InvariantCulture)).Append('\n');
            try {
                using (RegistryKey key = Registry.LocalMachine.OpenSubKey(@"SOFTWARE\Microsoft\Windows NT\CurrentVersion")) {
                    if (key != null) lines.Append("windows_build=").Append(Convert.ToString(key.GetValue("CurrentBuildNumber"), CultureInfo.InvariantCulture)).Append('.').Append(Convert.ToString(key.GetValue("UBR", 0), CultureInfo.InvariantCulture)).Append('\n');
                }
                using (RegistryKey display = Registry.LocalMachine.OpenSubKey(@"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}")) {
                    int index = 0;
                    if (display != null) foreach (string name in display.GetSubKeyNames()) {
                        if (index >= 8 || !Regex.IsMatch(name, @"\A[0-9]{4}\z")) continue;
                        using (RegistryKey adapter = display.OpenSubKey(name)) {
                            if (adapter == null) continue;
                            Match id = Regex.Match(Convert.ToString(adapter.GetValue("MatchingDeviceId"), CultureInfo.InvariantCulture).ToLowerInvariant(), @"ven_([0-9a-f]{4})&dev_([0-9a-f]{4})");
                            if (!id.Success) continue;
                            lines.Append("gpu=").Append(index++).Append('/').Append(id.Groups[1].Value).Append('/').Append(id.Groups[2].Value).Append('/').Append(Convert.ToString(adapter.GetValue("DriverVersion"), CultureInfo.InvariantCulture)).Append('\n');
                        }
                    }
                    if (index == 0) lines.Append("diagnostic=gpu-unavailable\n");
                }
            } catch (Exception) { lines.Append("diagnostic=system-partial\n"); }
            SaveLines("system.log", lines.ToString());
        }
        internal void SetupLine(string line)
        {
            if (line == null) return;
            ConsoleLine(line);
            // Project known diagnostics to stable codes; never copy arbitrary stderr.
            foreach (KeyValuePair<string, string> item in new Dictionary<string, string> {
                { "0x80370102", "virtualization-unavailable" }, { "0x800701bc", "wsl-kernel-update" },
                { "WSL_E_DISTRO_NOT_FOUND", "wsl-distribution-missing" }, { "Filename too long", "path-too-long" }, { "exceeds the OS max path limit", "path-too-long" },
                { "Permission denied", "permission-denied" }, { "Could not resolve", "dns-failed" },
                { "No space left", "disk-full" }, { "not enough space", "disk-full" },
                { "dpkg-query: no packages found", "linux-packages-missing" },
                { "Failed to fetch", "download-failed" }, { "CMake Error", "cmake-failed" } })
                if (line.IndexOf(item.Key, StringComparison.OrdinalIgnoreCase) >= 0) Write("setup_error=" + item.Value);
            foreach (Match match in Regex.Matches(line, @"\b(?:error|fatal error) (C[0-9]{4}|LNK[0-9]{4}|MSB[0-9]{4})\b", RegexOptions.IgnoreCase))
                Write("compiler_error=" + match.Groups[1].Value.ToLowerInvariant());
        }
        internal async Task<bool> CaptureFreeze(Process game, string runtime)
        {
            Write("capture=requested");
            ProcessStartInfo info = new ProcessStartInfo(System.IO.Path.Combine(System.IO.Path.GetDirectoryName(runtime), "jfg-support-capture.exe"));
            info.Arguments = game.Id.ToString(CultureInfo.InvariantCulture) + " " + game.StartTime.ToUniversalTime().ToFileTimeUtc().ToString(CultureInfo.InvariantCulture);
            info.UseShellExecute = false; info.CreateNoWindow = true; info.RedirectStandardOutput = true; info.RedirectStandardError = true;
            using (Process capture = Process.Start(info)) {
                // Drain only the allowlisted grammar, with a fixed byte/line budget.
                string output = "";
                Task read = Task.Run(delegate { output = ReadSafe(capture.StandardOutput); });
                Task errors = Drain(capture.StandardError);
                bool exited = await Task.Run(delegate { return capture.WaitForExit(12000); });
                if (!exited) { try { capture.Kill(); } catch (InvalidOperationException) { } }
                await Task.WhenAll(read, errors);
                bool complete = exited && capture.ExitCode == 0 && output.Contains("capture=complete\n");
                if (complete || !File.Exists(System.IO.Path.Combine(DirectoryPath, "hang.log"))) SaveLines("hang.log", output);
                Write("capture=" + (complete ? "complete" : exited ? "failed" : "timeout"));
                return complete;
            }
        }
        private static string ReadSafe(StreamReader reader)
        {
            StringBuilder output = new StringBuilder(), line = new StringBuilder();
            bool discard = false; int c;
            while ((c = reader.Read()) != -1) {
                if (c == '\n') {
                    string value = line.ToString().TrimEnd('\r');
                    if (!discard && SafeLine.IsMatch(value) && output.Length + value.Length < MaximumBytes) output.Append(value).Append('\n');
                    discard = false; line.Clear();
                } else if (!discard) { if (line.Length >= 256) { discard = true; line.Clear(); } else line.Append((char)c); }
            }
            return output.ToString();
        }
    }

    internal sealed class SupportWindow : ApplicationWindow
    {
        internal SupportWindow(string root, string destination, string active)
        {
            Text = "Create support report"; ClientSize = new Size(650, 180); StartPosition = FormStartPosition.CenterParent; Font = new Font("Segoe UI", 10);
            ComboBox sessions = new ComboBox { Left = 16, Top = 45, Width = 618, DropDownStyle = ComboBoxStyle.DropDownList };
            List<SupportChoice> choices = SupportSession.Sessions(root);
            int selected = -1;
            for (int i = 0; i < choices.Count; ++i) { sessions.Items.Add(choices[i]); if (selected < 0 && choices[i].Failed) selected = i; }
            if (active != null) for (int i = 0; i < choices.Count; ++i) if (choices[i].Path == active) selected = i;
            if (choices.Count > 0) sessions.SelectedIndex = selected < 0 ? 0 : selected;
            Controls.Add(new Label { Left = 16, Top = 15, Width = 618, Text = "Choose the session where the problem happened (local time)." }); Controls.Add(sessions);
            Controls.Add(new Label { Left = 16, Top = 85, Width = 618, Height = 40, Text = "For a freeze, use Capture freeze in the launcher before closing the game.\nReview the ZIP, then attach it to your GitHub issue." });
            Button export = new Button { Left = 445, Top = 135, Width = 190, Height = 30, Text = "Create ZIP", Enabled = choices.Count > 0 };
            export.Click += delegate {
                try { string zip = SupportSession.ExportSelected(root, ((SupportChoice)sessions.SelectedItem).Path, destination);
                    Process.Start(new ProcessStartInfo("explorer.exe", "/select," + LocalSetup.Quote(zip)) { UseShellExecute = false }); DialogResult = DialogResult.OK; Close();
                } catch (Exception error) { MessageBox.Show(this, LocalSetup.FriendlyError(error), Text); }
            };
            Controls.Add(export);
        }
    }
}
