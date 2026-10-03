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

        private static void LayerTests()
        {
            MapGeometry mesh = new MapGeometry {
                vertices = new float[][] { new float[]{0,0,0}, new float[]{0,0,100}, new float[]{100,0,0},
                    new float[]{0,100,0}, new float[]{0,100,100}, new float[]{100,100,0},
                    new float[]{0,200,0}, new float[]{100,200,0}, new float[]{0,200,100},
                    new float[]{0,0,0}, new float[]{0,100,0}, new float[]{0,0,100} },
                triangles = new MapFace[] { new MapFace {v=new int[]{0,1,2}}, new MapFace {v=new int[]{3,4,5}},
                    new MapFace {v=new int[]{6,7,8}}, new MapFace {v=new int[]{9,10,11}} }
            };
            MapLayers layers = new MapLayers(mesh);
            Check(layers.Floors.Count == 2, "walls and downward ceilings must not be filled as floors");
            float ground;
            Check(layers.Support(new HeightPoint(20,2,20), out ground) && ground == 0, "upper floor incorrectly obscures lower support");
            Check(layers.Support(new HeightPoint(20,102,20), out ground) && ground == 100, "upper floor support missing");
            Check(!layers.Support(new HeightPoint(200,2,200), out ground), "support extends outside triangle");
            FloorFollower follow = new FloorFollower();
            follow.Update(layers, new HeightPoint(20,2,20));
            follow.Update(layers, new HeightPoint(20,150,20));
            Check(follow.Height == 0 && !follow.Grounded, "jump switches to a floor far below airborne player");
            follow.Update(layers, new HeightPoint(20,102,20));
            Check(follow.Height == 100 && follow.Grounded, "landing does not switch floor");
            Check(MapLayers.Clip(layers.Floors[0].Points, -10, 10).Length == 3 &&
                MapLayers.Clip(layers.Floors[1].Points, -10, 10).Length == 0, "lower slice merges stacked floors");
            Check(MapLayers.Clip(layers.Floors[0].Points, 90, 110).Length == 0 &&
                MapLayers.Clip(layers.Floors[1].Points, 90, 110).Length == 3, "upper slice merges stacked floors");
            HeightPoint[] ramp = {new HeightPoint(0,0,0),new HeightPoint(0,0,100),new HeightPoint(100,100,0)};
            HeightPoint[] clipped = MapLayers.Clip(ramp,40,60);
            Check(clipped.Length == 4, "partial ramp should remain a quadrilateral");
            bool lower=false,upper=false; double area=0;
            for(int i=0;i<clipped.Length;i++) {
                HeightPoint p=clipped[i],q=clipped[(i+1)%clipped.Length];
                Check(p.Y >= 39.999f && p.Y <= 60.001f && Math.Abs(p.X-p.Y)<.001f, "ramp intersection misplaced");
                lower |= Math.Abs(p.Y-40)<.001f; upper |= Math.Abs(p.Y-60)<.001f;
                area += p.X*q.Z-q.X*p.Z;
            }
            Check(lower && upper && Math.Abs(Math.Abs(area)/2-1000)<.01, "ramp cross-section area incorrect");
            Check(layers.Low == 0 && layers.High == 100, "height scale includes ceilings or changes with slice");
            Check(layers.Patches.Count == 2 && layers.Patches[0].Color != layers.Patches[1].Color, "stacked floor colors indistinguishable");
            mesh.triangles[0].normal = new float[]{0,-1,0};
            Check(new MapLayers(mesh).Floors.Count == 1, "exported normal ignored");
        }

        [STAThread]
        private static int Main(string[] args)
        {
            if (args.Length > 0 && args[0] == "--echo")
            {
                for (int i = 1; i < args.Length; i++) Console.WriteLine(Convert.ToBase64String(Encoding.UTF8.GetBytes(args[i])));
                return 0;
            }
            if (args.Length > 0 && args[0] == "--crash-fixture")
            {
                Console.Error.WriteLine("PRIVATE-PATH-CANARY local ROM and save contents");
                Console.Error.Write(new string('x', 200000));
                Console.Error.WriteLine();
                Console.Error.WriteLine("JFG-SUPPORT native=running");
                Console.Error.WriteLine("native boot child rejected: exit=0xc0000005");
                return 17;
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
                Check(LocalSetup.PreferredRuntime(directory, "saved runtime") == "saved runtime", "invalid paired build accepted");
                File.WriteAllBytes(game, Pe());
                File.WriteAllBytes(Path.Combine(directory, "SDL2.dll"), Pe());
                Check(LocalSetup.PreferredRuntime(directory, "saved runtime") == game, "paired native build not selected");
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
                Check(start.EnvironmentVariables["JFG_MASTER_VOLUME_CONFIG"] == AudioPreferences.FileName(directory), "audio preferences not forwarded");
                AudioPreferences audio = AudioPreferences.Load(directory);
                Check(audio.Volume == 100 && !audio.Muted, "default audio settings changed");
                audio.Volume = 37; audio.Muted = true; audio.Save(directory);
                audio = AudioPreferences.Load(directory);
                Check(audio.Volume == 37 && audio.Muted, "mute or retained volume did not persist");
                audio.Muted = false; audio.Save(directory);
                Check(AudioPreferences.Load(directory).Volume == 37 && !AudioPreferences.Load(directory).Muted, "unmute lost prior volume");
                Check(AudioPreferences.Parse("version=1\r\nvolume=0\r\nmuted=0\r\n").Volume == 0, "zero volume or CRLF rejected");
                foreach (string invalidAudio in new string[] {
                    "version=1\nvolume=101\nmuted=0\n", "version=1\nvolume=-1\nmuted=0\n",
                    "version=1\nvolume=01\nmuted=0\n", "version=1\nvolume=50\nmuted=2\n",
                    "version=1\nvolume=50\nmuted=0\nextra", new string('x',129) })
                    Reject(delegate { AudioPreferences.Parse(invalidAudio); }, "invalid audio settings accepted");

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
                ControllerProfile controller = new ControllerProfile();
                string repo = LocalSetup.FindSourceRoot(AppDomain.CurrentDomain.BaseDirectory);
                Check(controller.Encode() == File.ReadAllText(Path.Combine(repo, "tests", "fixtures", "controller-default.ini")).Replace("\r\n", "\n"), "C# and native mapping schema differ");
                controller.Device = 2; controller.Bindings[3] = 3; controller.Deadzone = 18000;
                controller.Save(directory);
                ControllerProfile recovered = ControllerProfile.Load(directory);
                Check(recovered.Device == 2 && recovered.Bindings[3] == 3 && recovered.Deadzone == 18000, "controller settings did not persist");
                Check(LocalSetup.StartInfo(game, wrongRom, directory).EnvironmentVariables["JFG_CONTROLLER_CONFIG"] == ControllerProfile.FileName(directory), "controller mapping not forwarded to game");
                string normalProfile = Path.Combine(directory, "profiles", "default");
                Directory.CreateDirectory(normalProfile);
                File.WriteAllText(Path.Combine(normalProfile, "jfg.flash"), "normal campaign");
                File.WriteAllText(Path.Combine(normalProfile, "controller-1.pak"), "normal pak");
                controller.Save(normalProfile);
                ProcessStartInfo modStart = LocalSetup.NavigationStartInfo(game, wrongRom, normalProfile);
                string modProfile = LocalSetup.NavigationProfile(normalProfile);
                Check(modProfile != normalProfile && modStart.Arguments.Contains(LocalSetup.Quote(Path.Combine(modProfile, "jfg.flash"))), "mod shares normal saves");
                Check(File.ReadAllText(Path.Combine(modProfile, "jfg.flash")) == "normal campaign", "mod did not copy initial progress");
                Check(modStart.EnvironmentVariables["JFG_NAVIGATION_MOD"] == "1", "mod not enabled explicitly");
                Check(modStart.EnvironmentVariables["JFG_MASTER_VOLUME_CONFIG"] == AudioPreferences.FileName(normalProfile), "mod must share normal volume settings");
                Check(modStart.EnvironmentVariables["JFG_MOD_OUTPUT"].StartsWith(Path.Combine(modProfile, "maps")), "map export outside mod profile");
                Check(modStart.EnvironmentVariables["JFG_CONTROLLER_CONFIG"] == ControllerProfile.FileName(modProfile), "mod controller profile missing");
                File.WriteAllText(Path.Combine(modProfile, "jfg.flash"), "mod progress");
                ProcessStartInfo secondModStart = LocalSetup.NavigationStartInfo(game, wrongRom, normalProfile);
                Check(File.ReadAllText(Path.Combine(modProfile, "jfg.flash")) == "mod progress", "mod launch overwrites mod progress");
                Check(File.ReadAllText(Path.Combine(normalProfile, "jfg.flash")) == "normal campaign", "mod changed normal campaign");
                Check(secondModStart.EnvironmentVariables["JFG_MOD_OUTPUT"] != modStart.EnvironmentVariables["JFG_MOD_OUTPUT"], "export sessions share stale maps");
                ProcessStartInfo normalStart = LocalSetup.StartInfo(game, wrongRom, normalProfile);
                Check(!normalStart.EnvironmentVariables.ContainsKey("JFG_NAVIGATION_MOD") && !normalStart.EnvironmentVariables.ContainsKey("JFG_MOD_OUTPUT"), "mod enabled for normal launch");
                Reject(delegate { ControllerProfile.Parse(controller.Encode() + "map0=27\n"); }, "duplicate mapping accepted");
                Reject(delegate { ControllerProfile.Parse(controller.Encode().Replace("device=2", "device=4")); }, "bad controller port accepted");
                Reject(delegate { ControllerProfile.Parse(controller.Encode().Replace("map3=3", "map3=99")); }, "bad binding accepted");
                Reject(delegate { ControllerProfile.Parse(controller.Encode().Replace("deadzone=18000", "deadzone=99999")); }, "bad dead zone accepted");
                bool[] buttons = new bool[15]; int[] axes = new int[6];
                buttons[6] = true; Check(ControllerInput.Pressed(buttons, axes) == 6, "Start capture failed");
                buttons[6] = false; axes[3] = -24000; Check(ControllerInput.Pressed(buttons, axes) == 22, "stick direction capture failed");
                string reportRoot = Path.Combine(directory, "reports");
                SupportSession support = new SupportSession(reportRoot, "launch");
                support.Write("mod=navigation-enabled");
                support.Write("mod=PRIVATE-PATH-CANARY");
                support.Error(new IOException("PRIVATE-PATH-CANARY"));
                ProcessStartInfo crashPlan = new ProcessStartInfo(System.Reflection.Assembly.GetExecutingAssembly().Location, "--crash-fixture") {
                    UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true };
                using (Process child = Process.Start(crashPlan)) {
                    var stdout = support.Drain(child.StandardOutput); var stderr = support.Drain(child.StandardError);
                    child.WaitForExit(); System.Threading.Tasks.Task.WaitAll(stdout, stderr); support.Exit(child.ExitCode);
                }
                support.Finish();
                File.WriteAllText(support.NativePath, "native=running\nfailure=runlink/guest-overlay-load\nPRIVATE-PATH-CANARY\nnative_exception=0xc0000005\n");
                File.WriteAllText(Path.Combine(support.DirectoryPath, "jfg.flash"), "SAVE-CONTENTS-CANARY");
                File.WriteAllText(Path.Combine(support.DirectoryPath, "game.z64"), "ROM-CONTENTS-CANARY");
                string zipPath = SupportSession.Export(reportRoot, Path.Combine(directory, "exports"));
                using (FileStream file = File.OpenRead(zipPath))
                using (System.IO.Compression.ZipArchive zip = new System.IO.Compression.ZipArchive(file)) {
                    Check(zip.Entries.Count == 3, "unexpected support archive members");
                    string combined = "";
                    foreach (var entry in zip.Entries) using (StreamReader reader = new StreamReader(entry.Open())) combined += reader.ReadToEnd();
                    Check(!combined.Contains("CANARY") && !combined.Contains(directory), "private contents leaked into support report");
                    Check(combined.Contains("exit=0x00000011") && combined.Contains("native_exit=0xc0000005") && combined.Contains("failure=runlink/guest-overlay-load"), "crash evidence lost");
                    Check(combined.Contains("mod=navigation-enabled"), "mod context lost from support report");
                    Check(combined.Contains("native_exception=0xc0000005") && combined.Contains("omitted="), "exception or omitted count lost");
                }
                for (int i = 0; i < 6000; ++i) support.Write("native=running");
                Check(new FileInfo(Path.Combine(support.DirectoryPath, "launcher.log")).Length <= SupportSession.MaximumBytes, "support log grew without bound");
                for (int i = 0; i < 12; ++i) new SupportSession(reportRoot, "launch");
                Check(Directory.GetDirectories(reportRoot).Length == 11, "report retention should preserve unknown files but prune owned sessions");
                using (ControllerWindow controllerWindow = new ControllerWindow(directory)) {
                    controllerWindow.StartPosition = FormStartPosition.Manual; controllerWindow.Location = new Point(-32000, -32000);
                    controllerWindow.ShowInTaskbar = false; controllerWindow.Show(); Application.DoEvents();
                    using (Bitmap preview = new Bitmap(controllerWindow.Width, controllerWindow.Height)) {
                        controllerWindow.DrawToBitmap(preview, new Rectangle(Point.Empty, controllerWindow.Size));
                        if (args.Length == 1) preview.Save(Path.Combine(Path.GetDirectoryName(args[0]), "controller-preview.png"), System.Drawing.Imaging.ImageFormat.Png);
                    }
                    Check(controllerWindow.Controls.Count != 0, "controller UI did not render"); controllerWindow.Close();
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
                string setupFixture = Path.Combine(directory, "setup with spaces");
                ProcessStartInfo setupPlan = FirstRun.StartInfo(wrongRom, setupFixture);
                Check(!setupPlan.UseShellExecute && setupPlan.RedirectStandardError && setupPlan.RedirectStandardOutput,
                    "setup must use redirected argument-safe execution");
                Check(setupPlan.Arguments.Contains(LocalSetup.Quote(wrongRom)) &&
                    setupPlan.Arguments.Contains(BuildInfo.SourceCommit), "setup lost ROM or immutable revision");
                Check(System.Text.RegularExpressions.Regex.IsMatch(BuildInfo.SourceCommit, "^[0-9a-f]{40}$"), "source is not pinned");
                string installer = Path.Combine(setupFixture, "Setup.ps1");
                File.WriteAllText(installer, "synthetic tamper");
                FirstRun.StartInfo(wrongRom, setupFixture);
                Check(Convert.ToBase64String(File.ReadAllBytes(installer)) == Convert.ToBase64String(FirstRun.SetupScript()),
                    "setup resource was not restored from the executable");
                Reject(delegate { FirstRun.StartInfo("bad\npath", setupFixture); }, "setup accepted malformed ROM path");
                LayerTests();
                string mapDirectory = Path.Combine(directory, "map");
                Directory.CreateDirectory(mapDirectory);
                string meshFixture = "{\"schema\":1,\"level\":21,\"generation\":2,\"vertices\":[[0,0,0],[0,0,100],[100,0,0]],\"triangles\":[{\"v\":[0,1,2]}]}";
                long mapNow = (long)(DateTime.UtcNow - new DateTime(1970,1,1,0,0,0,DateTimeKind.Utc)).TotalMilliseconds;
                string liveFixture = "{\"schema\":1,\"level\":21,\"generation\":2,\"timestamp_ms\":" + mapNow +
                    ",\"update\":1,\"mesh_ready\":true,\"clearing_active\":true,\"player\":{\"position\":[20,0,20]},\"exits\":[{\"position\":[80,0,10],\"destination_code\":123}],\"markers\":[{\"position\":[10,0,80],\"kind\":\"chest\",\"label\":\"Chest\"}]}";
                File.WriteAllText(Path.Combine(mapDirectory, "mesh.json"), meshFixture);
                File.WriteAllText(Path.Combine(mapDirectory, "live.json"), liveFixture);
                MapSnapshot map = MapSnapshot.Load(mapDirectory, null);
                Check(map.IsLive && map.Live.markers.Length == 1 && map.Live.exits.Length == 1, "live map markers missing");
                Check(map.Live.npcs.Length == 0, "legacy maps should have no NPC markers");
                string npcFixture = ",\"npcs\":[{\"position\":[25,0,40],\"kind\":\"npc\",\"label\":\"NPC: Guide\"},{\"position\":[40,0,65],\"kind\":\"tribal\",\"label\":\"Tribal\"}]}";
                liveFixture = liveFixture.Substring(0, liveFixture.Length - 1) + npcFixture;
                File.WriteAllText(Path.Combine(mapDirectory, "live.json"), liveFixture);
                map = MapSnapshot.Load(mapDirectory, map.Mesh);
                Check(map.Live.npcs.Length == 2 && map.Live.npcs[1].kind == "tribal", "NPC and Tribal markers missing");
                File.WriteAllText(Path.Combine(mapDirectory, "live.json"), liveFixture.Replace("[25,0,40]", "[25,0]"));
                Reject(delegate { MapSnapshot.Load(mapDirectory, map.Mesh); }, "malformed NPC position accepted");
                File.WriteAllText(Path.Combine(mapDirectory, "live.json"), liveFixture.Replace("\"kind\":\"npc\"", "\"kind\":\"enemy\""));
                Reject(delegate { MapSnapshot.Load(mapDirectory, map.Mesh); }, "unknown NPC category accepted");
                File.WriteAllText(Path.Combine(mapDirectory, "live.json"), liveFixture.Replace("NPC: Guide", new string('x', 81)));
                Reject(delegate { MapSnapshot.Load(mapDirectory, map.Mesh); }, "oversized NPC label accepted");
                File.WriteAllText(Path.Combine(mapDirectory, "live.json"), liveFixture);
                Check(Object.ReferenceEquals(map.Mesh, MapSnapshot.Load(mapDirectory, map.Mesh).Mesh), "map cache not reused");
                File.WriteAllText(Path.Combine(mapDirectory, "live.json"), liveFixture.Replace("\"generation\":2", "\"generation\":3"));
                Reject(delegate { MapSnapshot.Load(mapDirectory, map.Mesh); }, "map mixed two room generations");
                File.WriteAllText(Path.Combine(mapDirectory, "live.json"), liveFixture.Replace(mapNow.ToString(), "1"));
                Check(!MapSnapshot.Load(mapDirectory, map.Mesh).IsLive, "stale map presented as live");
                File.WriteAllText(Path.Combine(mapDirectory, "live.json"), liveFixture);
                File.WriteAllText(Path.Combine(mapDirectory, "mesh.json"), meshFixture.Replace("[0,1,2]", "[0,1,9]"));
                Reject(delegate { MapSnapshot.Load(mapDirectory, null); }, "invalid map face accepted");
                File.WriteAllText(Path.Combine(mapDirectory, "mesh.json"), meshFixture);
                File.WriteAllText(Path.Combine(mapDirectory, "mesh.json"), meshFixture.Replace("\"v\":[0,1,2]", "\"v\":[0,1,2],\"normal\":[0,1]"));
                Reject(delegate { MapSnapshot.Load(mapDirectory, null); }, "malformed surface normal accepted");
                File.WriteAllText(Path.Combine(mapDirectory, "mesh.json"), meshFixture);
                string progressFixture = @"{""schema"":1,""inventory"":{""known"":true,""character"":1,""red_key"":false,""weapons_mask"":4},""nodes"":[{""address"":2148712448,""position"":[20,0,40],""kind"":""npc"",""label"":""Magnus: Red key"",""action"":""talk"",""status"":""available"",""requirement"":""Talk to Magnus"",""reward"":""Red key"",""requirement_known"":true,""reward_item"":1,""reward_weapon"":-1,""required_weapon"":-1,""spoken"":1,""traversal"":""unknown""}]}";
                string withProgress = liveFixture.Substring(0, liveFixture.Length - 1) + ",\"progression\":" + progressFixture + "}";
                File.WriteAllText(Path.Combine(mapDirectory, "live.json"), withProgress);
                map = MapSnapshot.Load(mapDirectory, map.Mesh);
                Check(map.Live.progression.nodes[0].spoken == 1 && map.Live.progression.nodes[0].status == "available", "spoken NPC incorrectly marked complete");
                Check(map.Live.progression.inventory.Summary.Contains("Red key: missing") && map.Live.progression.inventory.Summary.Contains("Machine gun: owned"), "inventory display incorrect");
                File.WriteAllText(Path.Combine(mapDirectory, "live.json"), withProgress.Replace("\"known\":true", "\"known\":false"));
                Reject(delegate { MapSnapshot.Load(mapDirectory, map.Mesh); }, "unknown inventory accepted ownership");
                File.WriteAllText(Path.Combine(mapDirectory, "live.json"), withProgress.Replace("\"traversal\":\"unknown\"", "\"traversal\":\"open\""));
                Reject(delegate { MapSnapshot.Load(mapDirectory, map.Mesh); }, "unsupported route status accepted");
                File.WriteAllText(Path.Combine(mapDirectory, "live.json"), withProgress);
                MapNpcOffer sampleOffer = new MapNpcOffer { id = "7:0/1:0", kind = "item", reward = "Crowbar", status = "blocked", scope = "any_character",
                    action = 5, item = 21, weapon = -1, flag = -1, destination = -1, consumed_items = new int[] {20},
                    conditions = new MapNpcCondition[] { new MapNpcCondition { domain = "prerequisite", id = 3, description = "Current character payment", state = "missing" } } };
                sampleOffer.Validate();
                Check(sampleOffer.Details.Contains("missing") && sampleOffer.Details.Contains("consumed"), "NPC trade requirement or consumption omitted");
                sampleOffer.conditions[0].state = "complete";
                Reject(delegate { sampleOffer.Validate(); }, "invalid NPC condition accepted");
                sampleOffer.conditions[0].state = "missing";
                sampleOffer.consumed_items = new int[] {27};
                Reject(delegate { sampleOffer.Validate(); }, "invalid NPC payment accepted");
                sampleOffer.consumed_items = new int[] {20};
                MapInteraction npcNode = map.Live.progression.nodes[0];
                npcNode.npc_catalog_known = true; npcNode.offers = new MapNpcOffer[] { sampleOffer };
                map.Live.progression.Validate();
                Check(npcNode.Details.Contains("Crowbar") && npcNode.Details.Contains("NPC offers"), "NPC offer not displayed in inspector");
                npcNode.offers = new MapNpcOffer[] { sampleOffer, sampleOffer };
                Reject(delegate { map.Live.progression.Validate(); }, "duplicate NPC offer accepted");
                npcNode.offers = new MapNpcOffer[] { sampleOffer }; npcNode.npc_catalog_known = false;
                Reject(delegate { map.Live.progression.Validate(); }, "unknown NPC catalog accepted rewards");
                npcNode.npc_catalog_known = true;
                npcNode.label = "NPC: Trader"; npcNode.reward = "Crowbar"; npcNode.status = "blocked";
                using (FileStream fixtureStream = File.Create(Path.Combine(mapDirectory, "live.json")))
                    new System.Runtime.Serialization.Json.DataContractJsonSerializer(typeof(MapLive)).WriteObject(fixtureStream, map.Live);
                map = MapSnapshot.Load(mapDirectory, map.Mesh);
                Check(map.Live.progression.nodes[0].offers[0].conditions[0].state == "missing", "NPC offers lost during JSON round trip");
                using (NavigationMapWindow mapWindow = new NavigationMapWindow(mapDirectory)) {
                    mapWindow.StartPosition = FormStartPosition.Manual; mapWindow.Location = new Point(-32000, -32000);
                    mapWindow.ShowInTaskbar = false; mapWindow.Show(); Application.DoEvents();
                    using (Bitmap preview = new Bitmap(mapWindow.Width, mapWindow.Height)) {
                        mapWindow.DrawToBitmap(preview, new Rectangle(Point.Empty, preview.Size));
                        preview.Save(Path.Combine(repo, "build", "launcher", "map-preview.png"));
                    }
                    mapWindow.Close(); checks++;
                }
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
