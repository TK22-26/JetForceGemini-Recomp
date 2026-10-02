using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Runtime.Serialization;
using System.Runtime.Serialization.Json;
using System.Windows.Forms;

namespace JfgLauncher
{
    [DataContract] internal sealed class MapFace
    {
        [DataMember] public int[] v = null;
    }
    [DataContract] internal sealed class MapGeometry
    {
        [DataMember] public int schema = 0;
        [DataMember] public uint level = 0;
        [DataMember] public long generation = 0;
        [DataMember] public float[][] vertices = null;
        [DataMember] public MapFace[] triangles = null;
    }
    [DataContract] internal sealed class MapPlayer
    {
        [DataMember] public float[] position = null;
    }
    [DataContract] internal sealed class MapMarker
    {
        [DataMember] public float[] position = null;
        [DataMember] public string kind = "";
        [DataMember] public string label = "";
        [DataMember] public int destination_code = 0;
    }
    [DataContract] internal sealed class MapLive
    {
        [DataMember] public int schema = 0;
        [DataMember] public uint level = 0;
        [DataMember] public long generation = 0;
        [DataMember] public long timestamp_ms = 0;
        [DataMember] public long update = 0;
        [DataMember] public bool mesh_ready = false;
        [DataMember] public bool clearing_active = false;
        [DataMember] public MapPlayer player = null;
        [DataMember] public MapMarker[] exits = null;
        [DataMember] public MapMarker[] markers = null;
    }
    internal sealed class MapSnapshot
    {
        internal MapGeometry Mesh;
        internal MapLive Live;
        internal bool IsLive {
            get {
                double age = (DateTime.UtcNow - new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalMilliseconds - Live.timestamp_ms;
                return age >= 0 && age <= 5000;
            }
        }
        internal static void Point(float[] value)
        {
            if (value == null || value.Length != 3) throw new InvalidDataException("Invalid map position.");
            foreach (float v in value)
                if (Single.IsNaN(v) || Single.IsInfinity(v)) throw new InvalidDataException("Invalid map coordinate.");
        }
        private static T Read<T>(string path)
        {
            using (FileStream file = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
            {
                if (file.Length > 128 * 1024 * 1024) throw new InvalidDataException("Map export is too large.");
                return (T)new DataContractJsonSerializer(typeof(T)).ReadObject(file);
            }
        }
        internal static MapSnapshot Load(string directory, MapGeometry cached)
        {
            MapLive live = Read<MapLive>(Path.Combine(directory, "live.json"));
            if (live == null || live.schema != 1 || live.generation < 1)
                throw new InvalidDataException("Unsupported map export.");
            if (!live.mesh_ready || live.player == null)
                throw new InvalidDataException("Waiting for gameplay and room geometry...");
            MapGeometry mesh = cached;
            if (mesh == null || mesh.generation != live.generation || mesh.level != live.level)
            {
                mesh = Read<MapGeometry>(Path.Combine(directory, "mesh.json"));
                if (mesh == null || mesh.schema != 1 || mesh.generation != live.generation || mesh.level != live.level)
                    throw new InvalidDataException("Room is changing...");
                if (mesh.vertices == null || mesh.vertices.Length == 0 || mesh.vertices.Length > 131072 ||
                    mesh.triangles == null || mesh.triangles.Length == 0 || mesh.triangles.Length > 262144)
                    throw new InvalidDataException("Invalid room geometry.");
                foreach (float[] point in mesh.vertices) Point(point);
                foreach (MapFace face in mesh.triangles) {
                    if (face == null || face.v == null || face.v.Length != 3)
                        throw new InvalidDataException("Invalid room face.");
                    foreach (int index in face.v)
                        if (index < 0 || index >= mesh.vertices.Length) throw new InvalidDataException("Invalid room vertex.");
                }
                live = Read<MapLive>(Path.Combine(directory, "live.json"));
            }
            if (live == null || live.schema != 1 || !live.mesh_ready || live.player == null ||
                live.generation != mesh.generation || live.level != mesh.level)
                throw new InvalidDataException("Room is changing...");
            Point(live.player.position);
            if (live.exits == null) live.exits = new MapMarker[0];
            if (live.markers == null) live.markers = new MapMarker[0];
            if (live.exits.Length > 1024 || live.markers.Length > 1024)
                throw new InvalidDataException("Too many map markers.");
            foreach (MapMarker marker in live.exits) { if (marker == null) throw new InvalidDataException(); Point(marker.position); }
            foreach (MapMarker marker in live.markers) {
                if (marker == null) throw new InvalidDataException();
                Point(marker.position);
                if ((marker.label ?? "").Length > 80 || (marker.kind ?? "").Length > 32) throw new InvalidDataException();
            }
            return new MapSnapshot { Mesh = mesh, Live = live };
        }
    }

    internal sealed class MapCanvas : Control
    {
        private MapSnapshot snapshot;
        private readonly List<PointF> trail = new List<PointF>();
        private float centerX, centerZ, spanX = 1, spanZ = 1, zoom = 1;
        private PointF pan, movement;
        private Point mouse;
        private bool dragging;
        private long lastUpdate = -1;
        internal MapCanvas()
        {
            DoubleBuffered = true;
            ResizeRedraw = true;
            BackColor = Color.FromArgb(16, 24, 34);
            Dock = DockStyle.Fill;
        }
        internal void Fit() { zoom = 1; pan = new PointF(); Invalidate(); }
        internal void UpdateMap(MapSnapshot value)
        {
            if (value != null && (snapshot == null || !Object.ReferenceEquals(snapshot.Mesh, value.Mesh))) {
                float lowX = Single.MaxValue, lowZ = Single.MaxValue, highX = Single.MinValue, highZ = Single.MinValue;
                foreach (float[] p in value.Mesh.vertices) {
                    lowX = Math.Min(lowX, p[0]); highX = Math.Max(highX, p[0]);
                    lowZ = Math.Min(lowZ, p[2]); highZ = Math.Max(highZ, p[2]);
                }
                centerX = (lowX + highX) / 2; centerZ = (lowZ + highZ) / 2;
                spanX = Math.Max(1, highX - lowX); spanZ = Math.Max(1, highZ - lowZ);
                trail.Clear(); lastUpdate = -1; movement = new PointF(); Fit();
            }
            snapshot = value;
            if (value != null && value.Live.update != lastUpdate) {
                PointF p = new PointF(value.Live.player.position[0], value.Live.player.position[2]);
                if (trail.Count > 0) {
                    PointF before = trail[trail.Count - 1];
                    float dx = p.X - before.X, dz = p.Y - before.Y;
                    float length = (float)Math.Sqrt(dx * dx + dz * dz);
                    if (length > .2f) movement = new PointF(dx / length, dz / length);
                }
                trail.Add(p);
                if (trail.Count > 256) trail.RemoveAt(0);
                lastUpdate = value.Live.update;
            }
            Invalidate();
        }
        private PointF Project(float x, float z)
        {
            float scale = Math.Min(Math.Max(1, Width - 50) / spanX, Math.Max(1, Height - 50) / spanZ) * zoom;
            return new PointF(Width / 2f + (x - centerX) * scale + pan.X,
                              Height / 2f + (z - centerZ) * scale + pan.Y);
        }
        private PointF Project(float[] p) { return Project(p[0], p[2]); }
        private void Marker(Graphics g, float[] p, Color color, string text, bool square)
        {
            PointF at = Project(p);
            using (Brush brush = new SolidBrush(color)) {
                if (square) g.FillRectangle(brush, at.X - 4, at.Y - 4, 8, 8);
                else g.FillEllipse(brush, at.X - 4, at.Y - 4, 8, 8);
                g.DrawString(text, Font, brush, at.X + 7, at.Y - 7);
            }
        }
        protected override void OnPaint(PaintEventArgs e)
        {
            base.OnPaint(e);
            Graphics g = e.Graphics;
            if (snapshot == null) {
                g.DrawString("Waiting for a loaded room...", Font, Brushes.LightGray, 20, 20);
                return;
            }
            g.SmoothingMode = SmoothingMode.AntiAlias;
            using (Pen lines = new Pen(Color.FromArgb(85, 99, 126, 148), .7f)) {
                PointF[] triangle = new PointF[3];
                foreach (MapFace face in snapshot.Mesh.triangles) {
                    for (int n = 0; n < 3; n++) triangle[n] = Project(snapshot.Mesh.vertices[face.v[n]]);
                    g.DrawPolygon(lines, triangle);
                }
            }
            if (trail.Count > 1) {
                PointF[] points = new PointF[trail.Count];
                for (int n = 0; n < trail.Count; n++) points[n] = Project(trail[n].X, trail[n].Y);
                using (Pen pen = new Pen(Color.FromArgb(110, 80, 230, 250), 2)) g.DrawLines(pen, points);
            }
            for (int n = 0; n < snapshot.Live.exits.Length; n++)
                Marker(g, snapshot.Live.exits[n].position, Color.Gold, "Exit " + (n + 1), false);
            foreach (MapMarker marker in snapshot.Live.markers) {
                Color color = marker.kind == "opened" ? Color.Gray : marker.kind == "key" ? Color.Plum : marker.kind == "weapon" ? Color.Orange : Color.LightGreen;
                Marker(g, marker.position, color, marker.label ?? "Item", true);
            }
            PointF player = Project(snapshot.Live.player.position);
            using (Brush brush = new SolidBrush(snapshot.IsLive ? Color.Cyan : Color.Gray)) {
                g.FillEllipse(brush, player.X - 6, player.Y - 6, 12, 12);
                if (movement.X != 0 || movement.Y != 0)
                    g.FillPolygon(brush, new PointF[] {
                        new PointF(player.X + movement.X * 17, player.Y + movement.Y * 17),
                        new PointF(player.X - movement.Y * 7, player.Y + movement.X * 7),
                        new PointF(player.X + movement.Y * 7, player.Y - movement.X * 7) });
            }
        }
        protected override void OnMouseWheel(MouseEventArgs e) { base.OnMouseWheel(e); zoom = Math.Max(.25f, Math.Min(16, zoom * (e.Delta > 0 ? 1.2f : 1 / 1.2f))); Invalidate(); }
        protected override void OnMouseDown(MouseEventArgs e) { base.OnMouseDown(e); Focus(); dragging = e.Button == MouseButtons.Left; mouse = e.Location; Capture = dragging; }
        protected override void OnMouseMove(MouseEventArgs e) { base.OnMouseMove(e); if (dragging) { pan.X += e.X - mouse.X; pan.Y += e.Y - mouse.Y; mouse = e.Location; Invalidate(); } }
        protected override void OnMouseUp(MouseEventArgs e) { base.OnMouseUp(e); dragging = false; Capture = false; }
    }

    internal sealed class NavigationMapWindow : Form
    {
        private readonly MapCanvas canvas = new MapCanvas();
        private readonly Label status = new Label();
        private readonly Timer timer = new Timer();
        private MapGeometry cached;
        private string directory;
        internal NavigationMapWindow(string path)
        {
            Text = "JFG Live Map";
            ClientSize = new Size(840, 700);
            MinimumSize = new Size(420, 360);
            Font = new Font("Segoe UI", 9);
            Controls.Add(canvas);
            FlowLayoutPanel bar = new FlowLayoutPanel { Dock = DockStyle.Top, Height = 38 };
            Button fit = new Button { Text = "Fit room", AutoSize = true };
            fit.Click += delegate { canvas.Fit(); };
            Button files = new Button { Text = "Open exports", AutoSize = true };
            files.Click += delegate {
                if (Directory.Exists(directory))
                    System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo("explorer.exe", LocalSetup.Quote(directory)) { UseShellExecute = false });
            };
            bar.Controls.Add(fit); bar.Controls.Add(files);
            bar.Controls.Add(new Label { Text = "Wheel: zoom   Drag: pan   Cyan: player   Yellow: exits   Squares: items", AutoSize = true, Padding = new Padding(6, 8, 0, 0) });
            Controls.Add(bar);
            status.Dock = DockStyle.Bottom; status.Height = 38; status.Padding = new Padding(8);
            Controls.Add(status);
            timer.Interval = 200; timer.Tick += delegate { RefreshMap(); };
            BindDirectory(path); timer.Start();
            FormClosed += delegate { timer.Stop(); timer.Dispose(); };
        }
        internal void BindDirectory(string path) { directory = LocalSetup.FullPath(path); cached = null; canvas.UpdateMap(null); RefreshMap(); }
        internal void RefreshMap()
        {
            try {
                MapSnapshot value = MapSnapshot.Load(directory, cached);
                cached = value.Mesh; canvas.UpdateMap(value);
                status.Text = (value.IsLive ? (value.Live.clearing_active ? "LIVE" : "LIVE · scripted scene / controls suspended") : "Saved map · game closed, paused, or no longer exporting")
                    + "  |  " + value.Live.exits.Length + " exits  |  " + value.Live.markers.Length + " items  |  arrow shows movement";
            }
            catch (InvalidDataException error) { cached = null; canvas.UpdateMap(null); status.Text = error.Message; }
            catch (IOException) { cached = null; canvas.UpdateMap(null); status.Text = "Waiting for the game to export a room..."; }
            catch (SerializationException) { cached = null; canvas.UpdateMap(null); status.Text = "Waiting for a complete map update..."; }
            catch (UnauthorizedAccessException) { status.Text = "Cannot read this export folder."; }
        }
    }
}
