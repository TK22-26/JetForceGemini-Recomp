using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace JfgLauncher
{
// Setup and diagnostic services for the native frontend. No launcher window.
internal static class FrontendBridge
{
    private sealed class Owner : IWin32Window
    {
        public IntPtr Handle { get; private set; }
        internal Owner(IntPtr h)
        {
            Handle = h;
        }
    }
    private static string root;
    private static void State(string message)
    {
        // Several independent tool processes may report status. Each write is atomic.
        try
        {
            Write("frontend-status.txt", message.Replace("\r", "").Replace("\n", " ") + "\n");
        }
        catch (IOException)
        {
        }
        catch (UnauthorizedAccessException)
        {
        }
    }
    private static string Read(string name)
    {
        string path = Path.Combine(root, name);
        if (!File.Exists(path))
            return "";
        if (new FileInfo(path).Length > 65536)
            throw new InvalidDataException("The saved frontend setting is too large.");
        return File.ReadAllText(path, Encoding.UTF8).TrimEnd('\r', '\n');
    }
    private static void Write(string name, string value)
    {
        string path = Path.Combine(root, name),
               temporary = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
        try
        {
            File.WriteAllText(temporary, value, new UTF8Encoding(false));
            if (File.Exists(path))
                File.Replace(temporary, path, null);
            else
                File.Move(temporary, path);
        }
        finally
        {
            if (File.Exists(temporary))
                File.Delete(temporary);
        }
    }
    internal static void CheckRuntimeProtocol(string game, int timeout)
    {
        using (var check = new Process())
        {
            check.StartInfo = new ProcessStartInfo(
                game, "--frontend-version") { UseShellExecute = false, CreateNoWindow = true,
                                              RedirectStandardOutput = true, RedirectStandardError = true };
            check.Start();
            var stdout = check.StandardOutput.ReadToEndAsync();
            var stderr = check.StandardError.ReadToEndAsync();
            if (!check.WaitForExit(timeout))
            {
                try
                {
                    check.Kill();
                }
                catch (InvalidOperationException)
                {
                }
                throw new InvalidDataException(
                    "The game build did not answer the launcher. Run setup to rebuild it.");
            }
            if (!Task.WaitAll(new Task[] { stdout, stderr }, timeout) || check.ExitCode != 0 ||
                stdout.Result.Trim() != "jfg-frontend-1")
                throw new InvalidDataException(
                    "This game build predates the unified frontend. Run setup to rebuild it.");
        }
    }
    private static async Task<int> Execute(string action, IntPtr owner)
    {
        if (action == "controllers")
        {
            using (var f = new ControllerWindow(root)) f.ShowDialog(new Owner(owner));
            return 0;
        }
        if (action == "audio")
        {
            using (var f = new FrontendAudio(root)) f.ShowDialog(new Owner(owner));
            return 0;
        }
        if (action == "support")
        {
            using (var f = new SupportWindow(SupportSession.Root,
                                             Path.Combine(FirstRun.Root, "support-exports"), null))
                f.ShowDialog(new Owner(owner));
            return 0;
        }
        if (action == "map" || action == "inventory")
        {
            var folder = Path.Combine(LocalSetup.NavigationProfile(root), "maps");
            var sessions = Directory.Exists(folder) ? Directory.GetDirectories(folder) : new string[0];
            if (sessions.Length == 0)
                throw new InvalidDataException(
                    "Start a Navigation mod session to export map and inventory data.");
            Array.Sort(sessions, StringComparer.Ordinal);
            if (action == "map")
                Application.Run(new NavigationMapWindow(sessions[sessions.Length - 1]));
            else
                Application.Run(new InventoryWindow(sessions[sessions.Length - 1]));
            return 0;
        }
        if (action == "init")
        {
            var settings = LocalSetup.LoadSettings(root);
            if (!File.Exists(Path.Combine(root, "frontend-rom.txt")))
                Write("frontend-rom.txt", settings.RomPath ?? "");
            if (!File.Exists(Path.Combine(root, "frontend-runtime.txt")))
                Write(
                    "frontend-runtime.txt",
                    LocalSetup.PreferredRuntime(AppDomain.CurrentDomain.BaseDirectory, settings.RuntimePath));
            if (!File.Exists(ControllerProfile.FileName(root)))
                new ControllerProfile().Save(root);
            State("Ready. Select your ROM and play, or run setup to build the game.");
            return 0;
        }
        string rom = LocalSetup.FullPath(Read("frontend-rom.txt"));
        State("Verifying your ROM...");
        using (var verified = await Task.Run(delegate { return LocalSetup.OpenVerifiedRom(rom); }))
        {
            using (var support = new FrontendSupport(action == "play" ? "launch" : action))
            {
                if (action == "setup")
                {
                    string built = null;
                    using (var process = new Process())
                    {
                        process.StartInfo = FirstRun.StartInfo(
                            rom, Path.Combine(FirstRun.Root, "setup", BuildInfo.SourceCommit));
                        process.OutputDataReceived += delegate(object sender, DataReceivedEventArgs e)
                        {
                            if (e.Data == null)
                                return;
                            support.Session.SetupLine(e.Data);
                            if (e.Data.StartsWith("Built: ", StringComparison.Ordinal))
                                built = e.Data.Substring(7);
                            State(e.Data);
                        };
                        process.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs e)
                        {
                            support.Session.SetupLine(e.Data);
                        };
                        process.Start();
                        process.BeginOutputReadLine();
                        process.BeginErrorReadLine();
                        await Task.Run(delegate { process.WaitForExit(); });
                        support.Session.Exit(process.ExitCode);
                        if (process.ExitCode == 3010)
                        {
                            State("Restart Windows, then run setup again. Progress is preserved.");
                            return 3010;
                        }
                        if (process.ExitCode != 0 || built == null)
                            throw new IOException("Setup stopped. Open the support report for details.");
                    }
                    string runtime = LocalSetup.ValidateRuntime(built);
                    Write("frontend-runtime.txt", runtime);
                    LocalSetup.SaveSettings(root, new Settings { RomPath = rom, RuntimePath = runtime });
                    State("Build ready. Click Play.");
                    return 0;
                }
                string game = LocalSetup.ValidateRuntime(Read("frontend-runtime.txt"));
                CheckRuntimeProtocol(game, 10000);
                LocalSetup.SaveSettings(root, new Settings { RomPath = rom, RuntimePath = game });
                using (var process = new Process())
                {
                    bool mods = Read("frontend-mods.txt") == "1";
                    process.StartInfo = mods ? LocalSetup.NavigationStartInfo(game, rom, root)
                                             : LocalSetup.StartInfo(game, rom, root);
                    process.StartInfo.EnvironmentVariables["JFG_CONTROLLER_CONFIG"] =
                        ControllerProfile.FileName(root);
                    process.StartInfo.EnvironmentVariables["JFG_MASTER_VOLUME_CONFIG"] =
                        AudioPreferences.FileName(root);
                    process.StartInfo.EnvironmentVariables["JFG_FRONTEND_PARENT"] =
                        owner.ToInt64().ToString(System.Globalization.CultureInfo.InvariantCulture);
                    process.StartInfo.EnvironmentVariables["JFG_SUPPORT_LOG"] = support.Session.NativePath;
                    try
                    {
                        support.Session.RuntimeDetails(game, root);
                    }
                    catch (IOException)
                    {
                    }
                    process.Start();
                    var stdout = support.Session.Drain(process.StandardOutput);
                    var stderr = support.Session.Drain(process.StandardError);
                    State("Playing. F11 fullscreen. Esc settings.");
                    await Task.Run(delegate { process.WaitForExit(); });
                    await Task.WhenAll(stdout, stderr);
                    support.Session.Exit(process.ExitCode);
                    State(process.ExitCode == 0 ? "Game stopped. Your saves are ready for next time."
                                                : "Game exited unexpectedly. Open Tools > Support report.");
                    return process.ExitCode;
                }
            }
        }
    }
    private sealed class FrontendSupport : IDisposable
    {
        internal readonly SupportSession Session;
        internal FrontendSupport(string action)
        {
            Session = new SupportSession(SupportSession.Root, action);
        }
        public void Dispose()
        {
            Session.Finish();
        }
    }
    internal static bool TryRun(string[] args)
    {
        if (args.Length != 4 || args[0] != "--frontend-worker")
            return false;
        try
        {
            root = LocalSetup.FullPath(args[2]);
            Directory.CreateDirectory(root);
            long handle;
            if (!Int64.TryParse(args[3], out handle))
                throw new InvalidDataException("Invalid frontend owner.");
            if (Array.IndexOf(
                    new[] { "init", "setup", "play", "controllers", "audio", "support", "map", "inventory" },
                    args[1]) < 0)
                throw new InvalidDataException("Unknown frontend action.");
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Environment.ExitCode = Execute(args[1], new IntPtr(handle)).GetAwaiter().GetResult();
        }
        catch (Exception error)
        {
            if (root != null)
                State(LocalSetup.FriendlyError(error));
            Environment.ExitCode = 1;
        }
        return true;
    }
}
internal sealed class FrontendAudio : Form
{
    internal FrontendAudio(string root)
    {
        Text = "Audio";
        ClientSize = new Size(440, 155);
        Font = new Font("Segoe UI", 11);
        StartPosition = FormStartPosition.CenterParent;
        var settings = AudioPreferences.Load(root);
        var value =
            new Label { Left = 24, Top = 15, Width = 390, Text = "Master volume: " + settings.Volume + "%" };
        var volume = new TrackBar { Left = 20,
                                    Top = 45,
                                    Width = 390,
                                    Minimum = 0,
                                    Maximum = 100,
                                    TickFrequency = 10,
                                    Value = settings.Volume };
        var mute =
            new CheckBox { Left = 24, Top = 108, Width = 170, Text = "Mute", Checked = settings.Muted };
        Controls.Add(value);
        Controls.Add(volume);
        Controls.Add(mute);
        EventHandler save = delegate
        {
            try
            {
                new AudioPreferences { Volume = volume.Value, Muted = mute.Checked }.Save(root);
                value.Text = "Master volume: " + volume.Value + "%";
            }
            catch (Exception e)
            {
                value.Text = LocalSetup.FriendlyError(e);
            }
        };
        volume.ValueChanged += save;
        mute.CheckedChanged += save;
    }
}
}
