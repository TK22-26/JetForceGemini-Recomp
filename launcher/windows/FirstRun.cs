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
            get { return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "JFGRecomp"); }
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
            info.CreateNoWindow = true;
            info.RedirectStandardOutput = true;
            info.RedirectStandardError = true;
            return info;
        }
    }
}
