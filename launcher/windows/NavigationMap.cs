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
        [DataMember] public uint address = 0;
        [DataMember] public int destination_code = 0;
    }
    [DataContract] internal sealed class MapInventory
    {
        [DataMember] public bool known = false;
        [DataMember] public int? character = null;
        [DataMember] public bool? red_key = null;
        [DataMember] public int? weapons_mask = null;
        internal string Summary { get {
            if (!known) return "Inventory: unknown";
            return "Character " + character + " | Red key: " + (red_key == true ? "owned" : "missing")
                + "\r\nMachine gun: " + ((weapons_mask.Value & 4) != 0 ? "owned" : "missing");
        } }
    }
    [DataContract] internal sealed class MapNpcCondition
    {
        [DataMember] public string domain = "", description = "", state = "";
        [DataMember] public int id = -1;
    }
    [DataContract] internal sealed class MapNpcOffer
    {
        [DataMember] public string id = "", kind = "", reward = "", status = "", scope = "";
        [DataMember] public int action = -1, item = -1, weapon = -1, flag = -1, destination = -1, cost = 0;
        [DataMember] public int[] consumed_items = null;
        [DataMember] public MapNpcCondition[] conditions = null;
        internal void Validate()
        {
            foreach (string text in new string[] { id, kind, reward, status, scope })
                if (String.IsNullOrEmpty(text) || text.Length > 256) throw new InvalidDataException("Invalid NPC offer text.");
            if (status != "owned" && status != "available" && status != "blocked" && status != "unknown")
                throw new InvalidDataException("Invalid NPC offer status.");
            if (action < -1 || action > 18 || item < -1 || item > 26 || weapon < -1 || weapon > 14 ||
                flag < -1 || flag > 1151 || destination < -1 || destination > 4095 || cost < 0 || cost > 32767 ||
                conditions == null || conditions.Length > 40 || consumed_items == null || consumed_items.Length > 27)
                throw new InvalidDataException("Invalid NPC offer values.");
            foreach (int value in consumed_items) if (value < 0 || value > 26) throw new InvalidDataException("Invalid trade item.");
            foreach (MapNpcCondition c in conditions) {
                if (c == null || String.IsNullOrEmpty(c.description) || c.description.Length > 512 ||
                    (c.domain != "dialogue_row" && c.domain != "visibility" && c.domain != "prerequisite") ||
                    (c.state != "met" && c.state != "missing" && c.state != "unknown"))
                    throw new InvalidDataException("Invalid NPC prerequisite.");
            }
        }
        internal string Details { get {
            string result = reward + " [" + status + "] (" + kind.Replace('_', ' ') + ")";
            if (scope != "none") result += "\r\nOwnership: " + scope.Replace('_', ' ');
            foreach (MapNpcCondition c in conditions) result += "\r\n  " + c.description + ": " + c.state;
            if (cost > 0) result += "\r\nCost: " + cost + " tokens";
            if (consumed_items.Length > 0) result += "\r\nTrade items are consumed when accepted.";
            if (kind == "transition") result += "\r\nScene effects require separate verification.";
            return result;
        } }
    }
    [DataContract] internal sealed class MapNpcCatalog
    {
        [DataMember] public bool known = false;
        [DataMember] public int dialogue_groups = 0, choice_tables = 0;
    }
    [DataContract] internal sealed class MapInteraction
    {
        [DataMember] public uint address = 0, linked_actor = 0;
        [DataMember] public float[] position = null;
        [DataMember] public string kind = "", label = "", action = "", status = "";
        [DataMember] public string requirement = "", reward = "", traversal = "";
        [DataMember] public bool requirement_known = false;
        [DataMember] public bool npc_catalog_known = false;
        [DataMember] public MapNpcOffer[] offers = null;
        internal string OfferDetails { get {
            if (offers == null || offers.Length == 0) return "";
            string result = "\r\n\r\nNPC offers (alternative dialogue paths):";
            foreach (MapNpcOffer offer in offers) result += "\r\n\r\n" + offer.Details;
            return result;
        } }
        [DataMember] public int reward_item = -1, reward_weapon = -1, required_weapon = -1;
        [DataMember] public int spoken = -1, encounter = -1, dialogue = -1;
        [DataMember] public int raw_state = -1, raw_condition = -1;
        [DataMember] public int door_id = -1, required_item = -1, target_health = -1, target_max_health = -1, reset_ticks = -1;
        [OnDeserializing] private void Init(StreamingContext context) {
            reward_item = reward_weapon = required_weapon = spoken = encounter = dialogue = raw_state = raw_condition = -1;
            door_id = required_item = target_health = target_max_health = reset_ticks = -1;
        }
        internal string Caption { get { return label + " [" + status.Replace('_', ' ') + "]"; } }
        public override string ToString() { return Caption; }
        internal string Details { get {
            return Caption + "\r\n\r\nAction: " + action.Replace('_', ' ')
                + "\r\nRequires: " + requirement + (requirement_known ? "" : " (unverified)")
                + "\r\nReward: " + reward
                + (door_id < 0 ? "" : "\r\nDoor group: " + door_id)
                + (target_health < 0 ? "" : "\r\nTarget strength: " + target_health + " / " + target_max_health + " (raw)")
                + (spoken < 0 ? "" : "\r\nSpoken to: " + (spoken == 1 ? "yes" : "no"))
                + OfferDetails
                + "\r\n\r\nX " + position[0].ToString("0.##") + "  Y " + position[1].ToString("0.##") + "  Z " + position[2].ToString("0.##")
                + (linked_actor == 0 ? "" : "\r\nLinked actor: " + linked_actor.ToString("X8"))
                + "\r\n\r\nAccess / traversal: unknown. Check doors, jumps and height before routing.";
        } }
    }
    [DataContract] internal sealed class MapProgression
    {
        [DataMember] public int schema = 0;
        [DataMember] public MapInventory inventory = null;
        [DataMember] public MapNpcCatalog npc_catalog = null;
        [DataMember] public MapInteraction[] nodes = null;
        internal void Validate()
        {
            if (schema != 1 || inventory == null || nodes == null || nodes.Length > 4096)
                throw new InvalidDataException("Invalid progression data.");
            if (inventory.known && (!inventory.character.HasValue || inventory.character < 0 || inventory.character > 2 ||
                !inventory.red_key.HasValue || !inventory.weapons_mask.HasValue || inventory.weapons_mask < 0 || inventory.weapons_mask > 65535))
                throw new InvalidDataException("Invalid inventory.");
            if (!inventory.known && (inventory.character.HasValue || inventory.red_key.HasValue || inventory.weapons_mask.HasValue))
                throw new InvalidDataException("Unknown inventory contains ownership claims.");
            if (npc_catalog != null && (npc_catalog.known ? npc_catalog.dialogue_groups != 45 || npc_catalog.choice_tables < 0 || npc_catalog.choice_tables > 107
                : npc_catalog.dialogue_groups != 0 || npc_catalog.choice_tables != 0)) throw new InvalidDataException("Invalid NPC catalog coverage.");
            HashSet<uint> seen = new HashSet<uint>();
            foreach (MapInteraction node in nodes) {
                if (node == null || node.address == 0 || !seen.Add(node.address)) throw new InvalidDataException("Invalid interaction identity.");
                if (node.offers != null) {
                    if (node.offers.Length > 128 || (!node.npc_catalog_known && node.offers.Length != 0)) throw new InvalidDataException("Invalid NPC offers.");
                    HashSet<string> offerIds = new HashSet<string>();
                    foreach (MapNpcOffer offer in node.offers) {
                        if (offer == null) throw new InvalidDataException("Missing NPC offer.");
                        offer.Validate();
                        if (!offerIds.Add(offer.id)) throw new InvalidDataException("Duplicate NPC offer.");
                    }
                }
                MapSnapshot.Point(node.position);
                foreach (string text in new string[] { node.kind, node.label, node.action, node.status, node.requirement, node.reward })
                    if (String.IsNullOrEmpty(text) || text.Length > 160) throw new InvalidDataException("Invalid interaction text.");
                if (node.traversal != "unknown" || node.spoken < -1 || node.spoken > 1 ||
                    node.reward_weapon < -1 || node.reward_weapon > 14 || node.required_weapon < -1 || node.required_weapon > 14)
                    throw new InvalidDataException("Unsupported interaction state.");
            }
        }
    }

    [DataContract] internal sealed class MapAi {
        [DataMember] public string state = "off";
        [DataMember] public bool active = false;
        [DataMember] public int waypoint = 0, count = 0, jump_attempts = 0;
        [DataMember] public long nonce = 0;
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
        [DataMember] public MapProgression progression = null;
        [DataMember] public MapAi navigation_ai = null;
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
            if (live.progression != null) live.progression.Validate();
            return new MapSnapshot { Mesh = mesh, Live = live };
        }
    }

    internal sealed class MapCanvas : Control
    {
        private MapSnapshot snapshot;
        internal NavigationRoute Route;
        private MapLayers layers;
        private FloorFollower follower=new FloorFollower();
        private readonly List<HeightPoint> trail=new List<HeightPoint>();
        private float centerX,centerZ,spanX=1,spanZ=1,zoom=1;
        private PointF pan,movement;
        private Point mouse;
        private bool dragging;
        private long lastUpdate=-1;
        internal uint SelectedAddress;
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
            for(int n=0;snapshot.Live.progression == null && n<snapshot.Live.exits.Length;n++)Marker(g,snapshot.Live.exits[n].position,Color.Gold,"Exit "+(n+1),0);
            HashSet<uint> enriched = new HashSet<uint>();
            if (snapshot.Live.progression != null) foreach (MapInteraction node in snapshot.Live.progression.nodes) {
                enriched.Add(node.address);
                if (node.address == SelectedAddress && (Mode == 2 || OtherLevels || (node.position[1] >= low && node.position[1] <= high))) {
                    PointF selectedPoint = Project(new HeightPoint(node.position));
                    using (Pen selectedPen = new Pen(Color.White, 2)) g.DrawEllipse(selectedPen, selectedPoint.X - 10, selectedPoint.Y - 10, 20, 20);
                }
                Color color = node.kind == "npc" ? Color.CornflowerBlue : node.kind == "tribal" ? Color.White :
                    node.kind == "exit" ? Color.Yellow : node.kind == "gate" ? Color.Violet : node.kind == "target" ? Color.OrangeRed :
                    node.kind == "key" ? Color.Plum : node.kind == "weapon" ? Color.Orange : Color.LightGreen;
                if (node.status == "owned" || node.status == "opened" || node.status == "activated") color = Color.Gray;
                Marker(g, node.position, color, node.Caption, node.kind == "npc" || node.kind == "tribal" ? 2 : node.kind == "exit" ? 0 : 1);
            }
            if (snapshot.Live.progression == null) foreach (MapMarker marker in snapshot.Live.markers)
                if (!enriched.Contains(marker.address)) Marker(g, marker.position, marker.kind == "opened" ? Color.Gray : marker.kind == "key" ? Color.Plum : marker.kind == "weapon" ? Color.Orange : Color.LightGreen, marker.label, 1);
            if (snapshot.Live.progression == null) foreach (MapMarker npc in snapshot.Live.npcs)
                if (!enriched.Contains(npc.address)) Marker(g, npc.position, npc.kind == "tribal" ? Color.White : Color.CornflowerBlue, npc.label, 2);
            if (Route != null && Route.Level == snapshot.Live.level && Route.Generation == snapshot.Live.generation) {
                using(Pen routePen = new Pen(Color.Yellow,3)) {
                    routePen.DashStyle = DashStyle.Dash;
                    PointF previous = Project(new HeightPoint(snapshot.Live.player.position));
                    foreach(HeightPoint p in Route.Points) { PointF next=Project(p); g.DrawLine(routePen,previous,next);previous=next; }
                }
            }
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
        private readonly Label inventoryStatus = new Label { Dock = DockStyle.Top, Height = 68, Padding = new Padding(8) };
        private readonly ListBox interactionList = new ListBox { Dock = DockStyle.Top, Height = 170, HorizontalScrollbar = true };
        private readonly TextBox interactionDetails = new TextBox { Dock = DockStyle.Fill, Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Vertical, BorderStyle = BorderStyle.None, BackColor = SystemColors.Control };
        private MapSnapshot aiSnapshot;
        private NavigationRoute aiRoute;
        private bool aiRunning;
        private long aiNonce = DateTime.UtcNow.Ticks;
        private readonly CheckBox jumpAssist = new CheckBox { Text = "Experimental jump assist", AutoSize = true };
        private readonly Label aiStatus = new Label { Text = "AI off - select an exit and plan a candidate route", AutoSize = true };
        private void StopAi() {
            aiRunning=false;
            if(aiRoute!=null)try { aiRoute.Send(directory,++aiNonce,false,true); } catch(IOException) {} catch(UnauthorizedAccessException) {}
            aiStatus.Text="AI stopped";
        }
        private long interactionGeneration = -1;
        private uint interactionLevel;
        private void UpdateInteractions(MapSnapshot value)
        {
            MapProgression progress = value == null ? null : value.Live.progression;
            MapInteraction selected = interactionList.SelectedItem as MapInteraction;
            uint address = value != null && value.Live.generation == interactionGeneration && value.Live.level == interactionLevel && selected != null ? selected.address : 0;
            interactionGeneration = value == null ? -1 : value.Live.generation;
            interactionLevel = value == null ? 0 : value.Live.level;
            interactionList.BeginUpdate();
            interactionList.Items.Clear();
            if (progress != null) foreach (MapInteraction node in progress.nodes) {
                int index = interactionList.Items.Add(node);
                if (node.address == address) interactionList.SelectedIndex = index;
            }
            if (interactionList.SelectedIndex < 0 && interactionList.Items.Count > 0) interactionList.SelectedIndex = 0;
            interactionList.EndUpdate();
            inventoryStatus.Text = progress == null ? "Progression data unavailable" :
                (value.IsLive ? "LIVE  " : "SAVED SNAPSHOT  ") + progress.inventory.Summary;
            selected = interactionList.SelectedItem as MapInteraction;
            interactionDetails.Text = selected == null ? "Select a loaded interaction to inspect its reward, requirements and coordinates." : selected.Details;
        }

        private readonly MapCanvas canvas = new MapCanvas();
        private readonly Label status = new Label();
        private NumericUpDown layerHeight;
        private readonly Timer timer = new Timer();
        private MapGeometry cached;
        private string directory;
        internal NavigationMapWindow(string path)
        {
            Text = "JFG Live Map";
            ClientSize = new Size(1240, 760);
            MinimumSize = new Size(1040, 600);
            Font = new Font("Segoe UI", 9);
            Controls.Add(canvas);
            Panel progressionPanel = new Panel { Dock = DockStyle.Right, Width = 300, Padding = new Padding(8) };
            progressionPanel.Controls.Add(interactionDetails); progressionPanel.Controls.Add(interactionList); progressionPanel.Controls.Add(inventoryStatus);
            Controls.Add(progressionPanel);
            interactionList.SelectedIndexChanged += delegate {
                MapInteraction node = interactionList.SelectedItem as MapInteraction;
                interactionDetails.Text = node == null ? "" : node.Details;
                canvas.SelectedAddress = node == null ? 0 : node.address; canvas.Invalidate();
            };
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
            bar.Controls.Add(new Label { Text = "Diamonds: blue NPCs, white Tribals   Orange-red: targets   Violet: doors", AutoSize = true, Padding = new Padding(6, 0, 0, 0) });
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
            bar.Height = 172;
            Button planAi = new Button { Text = "Plan exit route", AutoSize = true };
            Button startAi = new Button { Text = "Start AI", AutoSize = true };
            Button stopAi = new Button { Text = "Stop AI", AutoSize = true };
            bar.SetFlowBreak(context, true);
            bar.Controls.Add(planAi);bar.Controls.Add(startAi);bar.Controls.Add(stopAi);bar.Controls.Add(jumpAssist);
            bar.SetFlowBreak(jumpAssist,true);bar.Controls.Add(aiStatus);
            planAi.Click += delegate {
                StopAi();
                try {
                    MapInteraction target = interactionList.SelectedItem as MapInteraction;
                    if(target==null || target.kind!="exit")throw new InvalidDataException("Select an exit in the interaction list first.");
                    aiRoute=NavigationRoute.Plan(aiSnapshot,target.position);canvas.Route=aiRoute;canvas.Invalidate();
                    aiStatus.Text="Candidate route: "+aiRoute.Points.Count+" waypoints. Doors and jumps need verification.";
                }catch(InvalidDataException error){aiRoute=null;canvas.Route=null;aiStatus.Text=error.Message;}
            };
            startAi.Click += delegate {
                if(aiRoute==null || aiSnapshot==null || !aiSnapshot.IsLive || !aiSnapshot.Live.clearing_active ||
                    aiRoute.Level!=aiSnapshot.Live.level || aiRoute.Generation!=aiSnapshot.Live.generation){aiStatus.Text="Plan a route in active gameplay first.";return;}
                try { ++aiNonce;aiRoute.Send(directory,aiNonce,jumpAssist.Checked,false);aiRunning=true;aiStatus.Text="AI starting; any controller input or Esc stops it."; }
                catch(IOException error){aiStatus.Text=error.Message;aiRunning=false;}
            };
            stopAi.Click += delegate { StopAi(); };
            FormClosing += delegate { StopAi(); };
            timer.Interval = 200; timer.Tick += delegate { RefreshMap(); };
            BindDirectory(path); timer.Start();
            FormClosed += delegate { timer.Stop(); timer.Dispose(); };
        }
        internal void BindDirectory(string path) { StopAi(); aiRoute=null;canvas.Route=null; directory = LocalSetup.FullPath(path); cached = null; canvas.UpdateMap(null); UpdateInteractions(null); RefreshMap(); }
        internal void RefreshMap()
        {
            try {
                MapSnapshot value = MapSnapshot.Load(directory, cached);
                aiSnapshot=value;
                if(aiRoute!=null && (aiRoute.Level!=value.Live.level || aiRoute.Generation!=value.Live.generation || !value.IsLive || !value.Live.clearing_active)) { StopAi();aiRoute=null;canvas.Route=null; }
                if(aiRunning && aiRoute!=null) aiRoute.Send(directory,aiNonce,jumpAssist.Checked,false);
                if(value.Live.navigation_ai!=null && aiRoute!=null) {
                    MapAi ai=value.Live.navigation_ai;
                    if(ai.nonce==aiNonce && (ai.active || (aiRunning && ai.state!="off" && ai.state!="stopped"))) {
                        aiStatus.Text="AI: "+ai.state.Replace('_',' ')+" | waypoint "+ai.waypoint+" / "+ai.count+" | jumps "+ai.jump_attempts;
                        if(!ai.active)aiRunning=false;
                    }
                }
                cached = value.Mesh; canvas.UpdateMap(value); UpdateInteractions(value);
                if (canvas.Mode != 1) layerHeight.Value = Math.Max(layerHeight.Minimum, Math.Min(layerHeight.Maximum, (decimal)canvas.CenterHeight));
                int tribalCount = 0;
                foreach (MapMarker npc in value.Live.npcs)
                    if (npc.kind == "tribal") tribalCount++;
                status.Text = (value.IsLive ? (value.Live.clearing_active ? "LIVE" : "LIVE · scripted scene / controls suspended") : "Saved map · game closed, paused, or no longer exporting")
                    + "  |  " + value.Live.exits.Length + " exits  |  " + value.Live.markers.Length + " items  |  "
                    + (value.Live.npcs.Length - tribalCount) + " NPCs  |  " + tribalCount + " Tribals";
            }
            catch (InvalidDataException error) { StopAi();aiSnapshot=null; cached = null; canvas.UpdateMap(null); UpdateInteractions(null); status.Text = error.Message; }
            catch (IOException) { StopAi();aiSnapshot=null; cached = null; canvas.UpdateMap(null); UpdateInteractions(null); status.Text = "Waiting for the game to export a room..."; }
            catch (SerializationException) { StopAi();aiSnapshot=null; cached = null; canvas.UpdateMap(null); UpdateInteractions(null); status.Text = "Waiting for a complete map update..."; }
            catch (UnauthorizedAccessException) { StopAi();aiSnapshot=null; cached = null; canvas.UpdateMap(null); UpdateInteractions(null); status.Text = "Cannot read this export folder."; }
        }
    }
}
