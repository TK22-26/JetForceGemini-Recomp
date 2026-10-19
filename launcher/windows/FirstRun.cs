using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;

namespace JfgLauncher
{
    internal static class FirstRun
    {
        internal static string Root
        {
            get {
                string forwarded = Environment.GetEnvironmentVariable("JFG_DATA_ROOT");
                if (!String.IsNullOrWhiteSpace(forwarded)) return LocalSetup.FullPath(forwarded);
                string launcher = Environment.GetEnvironmentVariable("JFG_LAUNCHER_EXE");
                if (String.IsNullOrWhiteSpace(launcher)) launcher = Assembly.GetExecutingAssembly().Location;
                string directory = Path.GetDirectoryName(LocalSetup.FullPath(launcher));
                string location = Path.Combine(directory, "storage-location.txt");
                if (File.Exists(location)) {
                    string selected = File.ReadAllText(location).TrimEnd('\r', '\n');
                    if (String.IsNullOrWhiteSpace(selected)) throw new InvalidDataException("The data folder setting is empty.");
                    return LocalSetup.FullPath(Path.IsPathRooted(selected) ? selected : Path.Combine(directory, selected));
                }
                return File.Exists(Path.Combine(directory, "portable.txt"))
                    ? Path.Combine(directory, "userdata")
                    : Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "JFGRecomp");
            }
        }

        internal static byte[] SetupScript()
        {
            using (Stream input = Assembly.GetExecutingAssembly().GetManifestResourceStream("JfgLauncher.Setup.ps1"))
            {
                if (input == null) throw new InvalidDataException("The launcher setup component is missing. Download the launcher again.");
                using (MemoryStream output = new MemoryStream()) { input.CopyTo(output); return output.ToArray(); }
            }
        }

        internal static ProcessStartInfo StartInfo(string rom, string directory)
        {
            string selectedRom = LocalSetup.FullPath(rom);
            string setupRoot = LocalSetup.FullPath(directory);
            Directory.CreateDirectory(setupRoot);
            string script = Path.Combine(setupRoot, "Setup.ps1");
            // Always restore the installer from this executable's embedded resource.
            File.WriteAllBytes(script, SetupScript());
            ProcessStartInfo info = new ProcessStartInfo();
            info.FileName = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows),
                "System32", "WindowsPowerShell", "v1.0", "powershell.exe");
            info.Arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File " + LocalSetup.Quote(script) +
                " -SourceCommit " + LocalSetup.Quote(BuildInfo.SourceCommit) + " -RomPath " + LocalSetup.Quote(selectedRom);
            info.WorkingDirectory = setupRoot;
            info.UseShellExecute = false;
            info.EnvironmentVariables["JFG_DATA_ROOT"] = Root;
            info.CreateNoWindow = true;
            info.RedirectStandardOutput = true;
            info.RedirectStandardError = true;
            return info;
        }
    }
}
