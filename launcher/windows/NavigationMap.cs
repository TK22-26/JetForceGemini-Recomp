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
        [DataMember] public float[] normal = null;
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
        [DataMember] public MapMarker[] npcs = null;
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
                    if (face.normal != null) Point(face.normal);
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
            if (live.npcs == null) live.npcs = new MapMarker[0];
            if (live.exits.Length > 1024 || live.markers.Length > 1024 || live.npcs.Length > 1024)
                throw new InvalidDataException("Too many map markers.");
            foreach (MapMarker marker in live.exits) { if (marker == null) throw new InvalidDataException(); Point(marker.position); }
            foreach (MapMarker marker in live.markers) {
                if (marker == null) throw new InvalidDataException();
                Point(marker.position);
                if ((marker.label ?? "").Length > 80 || (marker.kind ?? "").Length > 32) throw new InvalidDataException();
            }
            foreach (MapMarker npc in live.npcs) {
                if (npc == null || (npc.kind != "npc" && npc.kind != "tribal"))
                    throw new InvalidDataException("Invalid NPC marker.");
                Point(npc.position);
                if (String.IsNullOrEmpty(npc.label) || npc.label.Length > 80)
                    throw new InvalidDataException("Invalid NPC label.");
            }
            return new MapSnapshot { Mesh = mesh, Live = live };
        }
    }

    internal sealed class MapCanvas : Control
    {
        private MapSnapshot snapshot;
        private MapLayers layers;
        private FloorFollower follower=new FloorFollower();
        private readonly List<HeightPoint> trail=new List<HeightPoint>();
        private float centerX,centerZ,spanX=1,spanZ=1,zoom=1;
        private PointF pan,movement;
        private Point mouse;
        private bool dragging;
        private long lastUpdate=-1;
        internal int Mode; // 0 player floor, 1 manual slice, 2 all heights.
        internal float ManualHeight, SliceWidth=64;
        internal bool OtherLevels=true;
        internal float CenterHeight {get {return Mode==1?ManualHeight:follower.Height;}}
        internal string LayerStatus {
            get {
                if(layers==null) return "";
                if(layers.Floors.Count==0) return "No upward surfaces found.";
                if(Mode==2) return "All heights: upper surfaces may cover lower floors.";
                return "Y " + (CenterHeight-SliceWidth/2).ToString("0") + " to " + (CenterHeight+SliceWidth/2).ToString("0") +
                    (Mode==0&&!follower.Grounded?" | ground unconfirmed; holding height":"") +
                    " | surface view, not a verified route";
            }
        }
        internal MapCanvas() {DoubleBuffered=true;ResizeRedraw=true;BackColor=Color.FromArgb(16,24,34);Dock=DockStyle.Fill;}
        internal void Fit() {zoom=1;pan=new PointF();Invalidate();}
        internal void UpdateMap(MapSnapshot value) {
            if(value!=null&&(snapshot==null||!Object.ReferenceEquals(snapshot.Mesh,value.Mesh))) {
                float lx=Single.MaxValue,lz=Single.MaxValue,hx=Single.MinValue,hz=Single.MinValue;
                foreach(float[] p in value.Mesh.vertices) {lx=Math.Min(lx,p[0]);hx=Math.Max(hx,p[0]);lz=Math.Min(lz,p[2]);hz=Math.Max(hz,p[2]);}
                centerX=(lx+hx)/2;centerZ=(lz+hz)/2;spanX=Math.Max(1,hx-lx);spanZ=Math.Max(1,hz-lz);
                layers=new MapLayers(value.Mesh);follower=new FloorFollower();
                trail.Clear();lastUpdate=-1;movement=new PointF();Fit();
            }
            snapshot=value;
            if(value==null) {layers=null;trail.Clear();Invalidate();return;}
            HeightPoint player=new HeightPoint(value.Live.player.position);
            follower.Update(layers,player);
            if(value.Live.update!=lastUpdate) {
                if(trail.Count>0) {
                    HeightPoint before=trail[trail.Count-1];float dx=player.X-before.X,dz=player.Z-before.Z;
                    float length=(float)Math.Sqrt(dx*dx+dz*dz);
                    if(length>1000) trail.Clear();
                    else if(length>.2f) movement=new PointF(dx/length,dz/length);
                }
                trail.Add(player);if(trail.Count>256) trail.RemoveAt(0);lastUpdate=value.Live.update;
            }
            Invalidate();
        }
        private PointF Project(HeightPoint p) {
            float scale=Math.Min(Math.Max(1,Width-80)/spanX,Math.Max(1,Height-75)/spanZ)*zoom;
            return new PointF((Width-30)/2f+(p.X-centerX)*scale+pan.X,(Height-25)/2f+(p.Z-centerZ)*scale+pan.Y);
        }
        private PointF[] Project(HeightPoint[] vertices) {
            PointF[] result=new PointF[vertices.Length];
            for(int i=0;i<result.Length;i++) result[i]=Project(vertices[i]);
            return result;
        }
        private void Label(Graphics g,string text,PointF p,Color color) {
            using(Brush back=new SolidBrush(Color.FromArgb(220,9,16,24))) {
                SizeF size=g.MeasureString(text,Font);g.FillRectangle(back,p.X,p.Y,size.Width,size.Height);
            }
            using(Brush brush=new SolidBrush(color)) g.DrawString(text,Font,brush,p);
        }
        private void Marker(Graphics g,float[] position,Color color,string text,int shape) {
            HeightPoint p=new HeightPoint(position);
            float low=CenterHeight-SliceWidth/2,high=CenterHeight+SliceWidth/2;
            bool off=Mode!=2&&(p.Y<low||p.Y>high);
            if(off&&!OtherLevels) return;
            if(off) {color=Color.FromArgb(130,color);text+=(p.Y>high?" \u2191":" \u2193")+Math.Abs(p.Y-CenterHeight).ToString("0");}
            PointF at=Project(p);
            using(Brush brush=new SolidBrush(color))
            using(Pen pen=new Pen(off?color:Color.Black,2)) {
                if(shape==2) {
                    PointF[] diamond={new PointF(at.X,at.Y-6),new PointF(at.X+6,at.Y),new PointF(at.X,at.Y+6),new PointF(at.X-6,at.Y)};
                    if(!off)g.FillPolygon(brush,diamond);g.DrawPolygon(pen,diamond);
                } else if(shape==1) {
                    if(!off)g.FillRectangle(brush,at.X-4,at.Y-4,8,8);g.DrawRectangle(pen,at.X-4,at.Y-4,8,8);
                } else {
                    if(!off)g.FillEllipse(brush,at.X-5,at.Y-5,10,10);g.DrawEllipse(pen,at.X-5,at.Y-5,10,10);
                }
            }
            Label(g,text,new PointF(at.X+8,at.Y-8),color);
        }
        protected override void OnPaint(PaintEventArgs e) {
            base.OnPaint(e);Graphics g=e.Graphics;
            if(snapshot==null||layers==null) {g.DrawString("Waiting for a loaded room...",Font,Brushes.LightGray,20,20);return;}
            g.SmoothingMode=SmoothingMode.AntiAlias;
            float low=CenterHeight-SliceWidth/2,high=CenterHeight+SliceWidth/2;
            g.SmoothingMode=SmoothingMode.None;
            if(Mode!=2&&OtherLevels) {
                using(Brush context=new SolidBrush(Color.FromArgb(13,145,163,176)))
                    foreach(HeightSurface floor in layers.Floors)
                        if(floor.Low<low||floor.High>high) g.FillPolygon(context,Project(floor.Points));
            }
            foreach(HeightPatch patch in layers.Patches) {
                HeightSurface floor=patch.Surface;
                if(Mode!=2&&(floor.High<low||floor.Low>high)) continue;
                HeightPoint[] poly=Mode==2?floor.Points:MapLayers.Clip(floor.Points,low,high);
                if(poly.Length<3) continue;
                using(Brush brush=new SolidBrush(patch.Color)) g.FillPolygon(brush,Project(poly));
            }
            g.SmoothingMode=SmoothingMode.AntiAlias;
            // Each trail segment retains height; never connect across a hidden floor.
            using(Pen pen=new Pen(Color.FromArgb(170,80,230,250),2)) {
                for(int i=1;i<trail.Count;i++) {
                    HeightPoint a=trail[i-1],b=trail[i];
                    if(Mode!=2) {
                        if((a.Y<low&&b.Y<low)||(a.Y>high&&b.Y>high))continue;
                        if(Math.Abs(b.Y-a.Y)>.0001f) {
                            float ta=(low-a.Y)/(b.Y-a.Y),tb=(high-a.Y)/(b.Y-a.Y);
                            float start=Math.Max(0,Math.Min(ta,tb)),end=Math.Min(1,Math.Max(ta,tb));
                            HeightPoint original=a;a=HeightPoint.Lerp(original,b,start);b=HeightPoint.Lerp(original,b,end);
                        }
                    }
                    g.DrawLine(pen,Project(a),Project(b));
                }
            }
            for(int n=0;n<snapshot.Live.exits.Length;n++)Marker(g,snapshot.Live.exits[n].position,Color.Gold,"Exit "+(n+1),0);
            foreach(MapMarker item in snapshot.Live.markers) {
                Color color=item.kind=="opened"?Color.Gray:item.kind=="key"?Color.Plum:item.kind=="weapon"?Color.Orange:Color.LightGreen;
                Marker(g,item.position,color,item.label??"Item",1);
            }
            foreach(MapMarker npc in snapshot.Live.npcs)Marker(g,npc.position,npc.kind=="tribal"?Color.White:Color.CornflowerBlue,npc.label,2);
            HeightPoint player=new HeightPoint(snapshot.Live.player.position);PointF atPlayer=Project(player);
            using(Brush brush=new SolidBrush(snapshot.IsLive?Color.Cyan:Color.Gray)) {
                g.FillEllipse(Brushes.Black,atPlayer.X-8,atPlayer.Y-8,16,16);g.FillEllipse(brush,atPlayer.X-6,atPlayer.Y-6,12,12);
                if(movement.X!=0||movement.Y!=0)g.FillPolygon(brush,new PointF[]{
                    new PointF(atPlayer.X+movement.X*17,atPlayer.Y+movement.Y*17),
                    new PointF(atPlayer.X-movement.Y*7,atPlayer.Y+movement.X*7),
                    new PointF(atPlayer.X+movement.Y*7,atPlayer.Y-movement.X*7)});
            }
            if(Mode!=2&&(player.Y<low||player.Y>high))Label(g,player.Y>high?"Player above slice":"Player below slice",new PointF(atPlayer.X+10,atPlayer.Y+10),Color.Cyan);
            // Fixed room-wide scale; moving the slice never changes color meanings.
            int x=Width-66,y=42;
            for(int i=0;i<MapLayers.Bands;i++)
                using(Brush brush=new SolidBrush(MapLayers.HeightColor((i+.5f)/MapLayers.Bands)))g.FillRectangle(brush,x,y+(MapLayers.Bands-1-i)*7,16,7);
            Label(g,layers.High.ToString("0"),new PointF(x-12,y-20),Color.White);
            Label(g,layers.Low.ToString("0"),new PointF(x-12,y+114),Color.White);
            Label(g,"Height Y",new PointF(x-14,y+134),Color.White);
            Label(g,LayerStatus,new PointF(8,Height-24),Color.LightGray);
        }
        protected override void OnMouseWheel(MouseEventArgs e){base.OnMouseWheel(e);zoom=Math.Max(.25f,Math.Min(16,zoom*(e.Delta>0?1.2f:1/1.2f)));Invalidate();}
        protected override void OnMouseDown(MouseEventArgs e){base.OnMouseDown(e);Focus();dragging=e.Button==MouseButtons.Left;mouse=e.Location;Capture=dragging;}
        protected override void OnMouseMove(MouseEventArgs e){base.OnMouseMove(e);if(dragging){pan.X+=e.X-mouse.X;pan.Y+=e.Y-mouse.Y;mouse=e.Location;Invalidate();}}
        protected override void OnMouseUp(MouseEventArgs e){base.OnMouseUp(e);dragging=false;Capture=false;}
    }


    internal sealed class NavigationMapWindow : Form
    {
        private readonly MapCanvas canvas = new MapCanvas();
        private readonly Label status = new Label();
        private NumericUpDown layerHeight;
        private readonly Timer timer = new Timer();
        private MapGeometry cached;
        private string directory;
        internal NavigationMapWindow(string path)
        {
            Text = "JFG Live Map";
            ClientSize = new Size(940, 760);
            MinimumSize = new Size(820, 480);
            Font = new Font("Segoe UI", 9);
            Controls.Add(canvas);
            FlowLayoutPanel bar = new FlowLayoutPanel { Dock = DockStyle.Top, Height = 116 };
            Button fit = new Button { Text = "Fit room", AutoSize = true };
            fit.Click += delegate { canvas.Fit(); };
            Button files = new Button { Text = "Open exports", AutoSize = true };
            files.Click += delegate {
                if (Directory.Exists(directory))
                    System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo("explorer.exe", LocalSetup.Quote(directory)) { UseShellExecute = false });
            };
            bar.Controls.Add(fit); bar.Controls.Add(files);
            bar.Controls.Add(new Label { Text = "Wheel: zoom   Drag: pan   Cyan: player   Yellow: exits   Squares: items", AutoSize = true, Padding = new Padding(6, 8, 0, 0) });
            bar.SetFlowBreak(bar.Controls[bar.Controls.Count - 1], true);
            bar.Controls.Add(new Label { Text = "Diamonds: blue NPCs, white Tribals", AutoSize = true, Padding = new Padding(6, 0, 0, 0) });
            ComboBox mode = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 130 };
            mode.Items.AddRange(new object[] { "Player floor", "Height slice", "All heights" });
            mode.SelectedIndex = 0;
            NumericUpDown height = new NumericUpDown { Minimum = -1000000, Maximum = 1000000, Increment = 16, Width = 90, Enabled = false };
            layerHeight = height;
            NumericUpDown thickness = new NumericUpDown { Minimum = 4, Maximum = 4096, Value = 64, Increment = 16, Width = 70 };
            CheckBox context = new CheckBox { Text = "Other levels", Checked = true, AutoSize = true, Padding = new Padding(4, 3, 0, 0) };
            mode.SelectedIndexChanged += delegate {
                if (mode.SelectedIndex == 1) height.Value = Math.Max(height.Minimum, Math.Min(height.Maximum, (decimal)canvas.CenterHeight));
                canvas.Mode = mode.SelectedIndex; canvas.ManualHeight = (float)height.Value;
                height.Enabled = canvas.Mode == 1; thickness.Enabled = canvas.Mode != 2; context.Enabled = canvas.Mode != 2;
                canvas.Invalidate();
            };
            height.ValueChanged += delegate { canvas.ManualHeight = (float)height.Value; canvas.Invalidate(); };
            thickness.ValueChanged += delegate { canvas.SliceWidth = (float)thickness.Value; canvas.Invalidate(); };
            context.CheckedChanged += delegate { canvas.OtherLevels = context.Checked; canvas.Invalidate(); };
            bar.SetFlowBreak(bar.Controls[bar.Controls.Count - 1], true);
            bar.Controls.Add(mode);
            bar.Controls.Add(new Label { Text = "Height Y", AutoSize = true, Padding = new Padding(0, 5, 0, 0) });
            bar.Controls.Add(height);
            bar.Controls.Add(new Label { Text = "Slice width", AutoSize = true, Padding = new Padding(0, 5, 0, 0) });
            bar.Controls.Add(thickness); bar.Controls.Add(context);
            bar.SetFlowBreak(context, true);
            bar.Controls.Add(new Label { Text = "Filled surfaces: height colors   Hollow markers: above/below slice   Stacked floors remain separate", AutoSize = true, Padding = new Padding(6, 0, 0, 0) });

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
                if (canvas.Mode != 1) layerHeight.Value = Math.Max(layerHeight.Minimum, Math.Min(layerHeight.Maximum, (decimal)canvas.CenterHeight));
                int tribalCount = 0;
                foreach (MapMarker npc in value.Live.npcs)
                    if (npc.kind == "tribal") tribalCount++;
                status.Text = (value.IsLive ? (value.Live.clearing_active ? "LIVE" : "LIVE · scripted scene / controls suspended") : "Saved map · game closed, paused, or no longer exporting")
                    + "  |  " + value.Live.exits.Length + " exits  |  " + value.Live.markers.Length + " items  |  "
                    + (value.Live.npcs.Length - tribalCount) + " NPCs  |  " + tribalCount + " Tribals";
            }
            catch (InvalidDataException error) { cached = null; canvas.UpdateMap(null); status.Text = error.Message; }
            catch (IOException) { cached = null; canvas.UpdateMap(null); status.Text = "Waiting for the game to export a room..."; }
            catch (SerializationException) { cached = null; canvas.UpdateMap(null); status.Text = "Waiting for a complete map update..."; }
            catch (UnauthorizedAccessException) { status.Text = "Cannot read this export folder."; }
        }
    }
}
