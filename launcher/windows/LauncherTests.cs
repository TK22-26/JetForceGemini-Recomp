using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Text;
using System.Windows.Forms;

namespace JfgLauncher
{
    internal static class LauncherTests
    {
        private static int checks;
        private static void Check(bool pass, string description)
        {
            if (!pass) throw new Exception(description);
            checks++;
        }
        private static void Reject(Action action, string description)
        {
            try { action(); } catch (InvalidDataException) { checks++; return; }
            throw new Exception(description);
        }
        private static byte[] Fixture()
        {
            byte[] data = new byte[32];
            data[0] = 0x80; data[1] = 0x37; data[2] = 0x12; data[3] = 0x40;
            return data;
        }
        private static byte[] Pe()
        {
            byte[] data = new byte[128];
            data[0] = (byte)'M'; data[1] = (byte)'Z'; data[60] = 80;
            data[80] = (byte)'P'; data[81] = (byte)'E'; data[84] = 0x64; data[85] = 0x86;
            return data;
        }

        [STAThread]
        private static int Main(string[] args)
        {
            if (args.Length > 0 && args[0] == "--echo")
            {
                for (int i = 1; i < args.Length; i++) Console.WriteLine(Convert.ToBase64String(Encoding.UTF8.GetBytes(args[i])));
                return 0;
            }
            string directory = Path.Combine(Path.GetTempPath(), "jfg-launcher-fixture-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            try
            {
                byte[] fixture = Fixture();
                string hash = LocalSetup.Digest(new MemoryStream(fixture));
                LocalSetup.ValidateRom(new MemoryStream(fixture), fixture.Length, hash);
                checks++;
                Reject(delegate { LocalSetup.ValidateRom(new MemoryStream(fixture), 33, hash); }, "wrong size accepted");
                Reject(delegate { LocalSetup.ValidateRom(new MemoryStream(fixture), fixture.Length, new string('0', 40)); }, "wrong hash accepted");
                fixture[0] = 0x37;
                Reject(delegate { LocalSetup.ValidateRom(new MemoryStream(fixture), fixture.Length, hash); }, "wrong byte order accepted");
                string wrongRom = Path.Combine(directory, "synthetic.z64");
                File.WriteAllBytes(wrongRom, Fixture());
                Reject(delegate { using (LocalSetup.OpenVerifiedRom(wrongRom)) { } }, "production validation accepted synthetic ROM");
                Reject(delegate { LocalSetup.FullPath("bad\npath"); }, "newline path accepted");
                Reject(delegate { LocalSetup.FullPath(@"\\server\share\file"); }, "network path accepted");
                Reject(delegate { LocalSetup.ValidateRuntime(Path.Combine(directory, "jfg.exe")); }, "host shell accepted");
                string game = Path.Combine(directory, "jfg-native-boot.exe");
                File.WriteAllBytes(game, Pe());
                Reject(delegate { LocalSetup.ValidateRuntime(game); }, "missing libraries accepted");
                foreach (string name in new string[] {"SDL2.dll", "dxcompiler.dll", "dxil.dll"}) File.WriteAllBytes(Path.Combine(directory, name), Pe());
                Check(LocalSetup.ValidateRuntime(game) == game, "complete structural build rejected");
                byte[] badPe = Pe(); badPe[85] = 0;
                File.WriteAllBytes(Path.Combine(directory, "SDL2.dll"), badPe);
                Reject(delegate { LocalSetup.ValidateRuntime(game); }, "non-x64 library accepted");
                File.WriteAllBytes(game, new byte[2]);
                Reject(delegate { LocalSetup.ValidateRuntime(game); }, "truncated executable accepted");
                Settings settings = new Settings { RuntimePath = "Synthetic build & Unicode \u00e9", RomPath = "Selected synthetic ROM" };
                LocalSetup.SaveSettings(directory, settings);
                Settings loaded = LocalSetup.LoadSettings(directory);
                Check(loaded.RuntimePath == settings.RuntimePath && loaded.RomPath == settings.RomPath, "settings round trip failed");
                settings.RomPath = "Updated selection";
                LocalSetup.SaveSettings(directory, settings);
                Check(LocalSetup.LoadSettings(directory).RomPath == settings.RomPath, "atomic replacement failed");
                string flash = Path.Combine(directory, "jfg.flash");
                File.WriteAllText(flash, "synthetic saved data");
                LocalSetup.SaveSettings(directory, settings);
                Check(File.ReadAllText(flash) == "synthetic saved data", "settings overwrote save data");
                File.WriteAllText(Path.Combine(directory, "launcher.json"), "broken");
                Check(LocalSetup.LoadSettings(directory).RuntimePath == "", "malformed settings not recovered");
                Environment.SetEnvironmentVariable("JFG_PHASE9_INPUT_RECORD", "must-not-inherit");
                ProcessStartInfo start = LocalSetup.StartInfo(game, wrongRom, directory);
                Check(!start.UseShellExecute && start.CreateNoWindow, "launch uses shell or console");
                Check(!start.EnvironmentVariables.ContainsKey("JFG_PHASE9_INPUT_RECORD"), "diagnostic environment inherited");
                Check(start.WorkingDirectory == directory && start.Arguments.EndsWith(" --play"), "incorrect game launch plan");
                Check(start.Arguments.Contains(LocalSetup.Quote(flash)), "save path not isolated");
                Check(!LocalSetup.FriendlyError(new IOException("PRIVATE-PATH-CANARY")).Contains("PRIVATE-PATH-CANARY"), "exception discloses path");
                string[] samples = {"", "plain", "spaces here", "ampersand & dollar $ percent %", "a\"b", @"trailing\", "\u00e9 unicode", "back\\\"quote"};
                ProcessStartInfo echo = new ProcessStartInfo();
                echo.FileName = System.Reflection.Assembly.GetExecutingAssembly().Location;
                echo.UseShellExecute = false; echo.CreateNoWindow = true; echo.RedirectStandardOutput = true;
                echo.Arguments = "--echo";
                foreach (string sample in samples) echo.Arguments += " " + LocalSetup.Quote(sample);
                using (Process child = Process.Start(echo))
                {
                    foreach (string sample in samples)
                        Check(child.StandardOutput.ReadLine() == Convert.ToBase64String(Encoding.UTF8.GetBytes(sample)), "Windows argument round trip failed");
                    child.WaitForExit();
                    Check(child.ExitCode == 0, "echo process failed");
                }
                Application.EnableVisualStyles();
                string sourceFixture = Path.Combine(directory, "source with spaces");
                Directory.CreateDirectory(Path.Combine(sourceFixture, "scripts"));
                File.WriteAllText(Path.Combine(sourceFixture, "CMakeLists.txt"), "# fixture");
                File.WriteAllText(Path.Combine(sourceFixture, "scripts", "build_from_rom.py"), "# fixture");
                string nested = Path.Combine(sourceFixture, "build", "launcher");
                Directory.CreateDirectory(nested);
                Check(LocalSetup.FindSourceRoot(nested) == sourceFixture, "source root discovery failed");
                ProcessStartInfo buildPlan = LocalSetup.BuildStartInfo(sourceFixture, Path.Combine(directory, "local rom.z64"));
                Check(!buildPlan.UseShellExecute && buildPlan.CreateNoWindow && buildPlan.RedirectStandardOutput && buildPlan.RedirectStandardError,
                    "build process must use redirected argument-safe execution");
                Check(buildPlan.WorkingDirectory == sourceFixture && buildPlan.Arguments.Contains(" --rom "), "build inputs missing");
                Reject(delegate { LocalSetup.BuildStartInfo(directory, "rom.z64"); }, "unrelated source folder accepted");
                using (LauncherWindow window = new LauncherWindow())
                {
                    // Realize controls without putting a test window on the user's desktop.
                    window.StartPosition = FormStartPosition.Manual;
                    window.Location = new Point(-32000, -32000);
                    window.ShowInTaskbar = false;
                    window.Show();
                    Application.DoEvents();
                    using (Bitmap preview = new Bitmap(window.Width, window.Height))
                    {
                        window.DrawToBitmap(preview, new Rectangle(Point.Empty, window.Size));
                        System.Collections.Generic.HashSet<int> colors = new System.Collections.Generic.HashSet<int>();
                        for (int y = 40; y < preview.Height - 20; y += 4)
                            for (int x = 20; x < preview.Width - 20; x += 4)
                                colors.Add(preview.GetPixel(x, y).ToArgb());
                        Check(colors.Count > 10, "UI rendered an empty surface");
                        if (args.Length == 1) preview.Save(args[0], System.Drawing.Imaging.ImageFormat.Png);
                    }
                    Check(window.Text == "JFG Launcher Preview", "UI construction failed");
                    window.Close();
                }
                Console.WriteLine("Launcher checks passed: " + checks);
                return 0;
            }
            catch (Exception error) { Console.Error.WriteLine(error.GetType().Name + ": " + error.Message); return 1; }
            finally
            {
                // This path is an explicitly created disposable fixture, never a user profile.
                string full = Path.GetFullPath(directory);
                if (full.StartsWith(Path.GetFullPath(Path.GetTempPath()), StringComparison.OrdinalIgnoreCase) &&
                    Path.GetFileName(full).StartsWith("jfg-launcher-fixture-", StringComparison.Ordinal))
                    Directory.Delete(full, true);
            }
        }
    }
}
