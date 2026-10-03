using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Runtime.Serialization;

namespace JfgLauncher {
    [DataContract] internal sealed class MapActor {
        [DataMember] public uint address = 0;
        [DataMember] public int behavior = 0;
        [DataMember] public string name = "";
        [DataMember] public float[] position = null;
        internal string Name { get {return String.IsNullOrWhiteSpace(name)?"Entity "+behavior:name;} }
    }
    [DataContract] internal sealed class MapCollisionModel {
        [DataMember] public uint address = 0;
        [DataMember] public bool enabled = false;
        [DataMember] public float[] lower = null, upper = null;
        internal bool Overlaps(float low,float high) {return upper[1]>=low && lower[1]<=high;}
    }
    [DataContract] internal sealed class MapCollision {
        [DataMember] public int schema = 0;
        [DataMember] public bool known = false;
        [DataMember] public string reason = "";
        [DataMember] public MapCollisionModel[] models = null;
        internal static MapCollision Empty() {return new MapCollision {schema=1,known=true,reason="registered model bounds",models=new MapCollisionModel[0]};}
        internal void Validate(MapActor[] actors) {
            if(schema!=1 || String.IsNullOrEmpty(reason) || reason.Length>160 || models==null || models.Length>1024 || (!known && models.Length!=0))
                throw new InvalidDataException("Invalid collision inventory.");
            HashSet<uint> available=new HashSet<uint>(),seen=new HashSet<uint>();
            foreach(MapActor a in actors)available.Add(a.address & 0x1FFFFFFF);
            foreach(MapCollisionModel m in models) {
                if(m==null || m.address==0 || !available.Contains(m.address & 0x1FFFFFFF) || !seen.Add(m.address & 0x1FFFFFFF))
                    throw new InvalidDataException("Collision model has no unique current entity.");
                MapSnapshot.Point(m.lower);MapSnapshot.Point(m.upper);
                for(int i=0;i<3;i++)if(m.lower[i]>m.upper[i] || Math.Abs(m.lower[i])>1000000 || Math.Abs(m.upper[i])>1000000)
                    throw new InvalidDataException("Invalid collision bounds.");
            }
        }
    }
    internal static class NavigationCollision {
        // Prototype clearance envelope, not a decoded character-specific capsule.
        internal const float Radius=20, BodyHeight=80, FootClearance=4;
        internal static bool SameActor(uint a,uint b) {return a!=0 && b!=0 && (a&0x1FFFFFFF)==(b&0x1FFFFFFF);}
        internal static void Require(MapLive live) {
            if(live==null || live.collision==null || !live.collision.known)
                throw new InvalidDataException("Collision bounds unavailable; use the updated native build before routing.");
            live.collision.Validate(live.actors??new MapActor[0]);
        }
        internal static MapActor Actor(MapLive live,uint address) {
            if(live.actors!=null)foreach(MapActor a in live.actors)if(SameActor(a.address,address))return a;
            return null;
        }
        internal static MapCollisionModel Model(MapLive live,uint address) {
            if(live.collision!=null && live.collision.models!=null)foreach(MapCollisionModel m in live.collision.models)if(SameActor(m.address,address))return m;
            return null;
        }
        private static bool Clip(float p,float d,float low,float high,ref float enter,ref float leave) {
            if(Math.Abs(d)<.000001f)return p>=low && p<=high;
            float a=(low-p)/d,b=(high-p)/d;
            enter=Math.Max(enter,Math.Min(a,b));leave=Math.Min(leave,Math.Max(a,b));return enter<=leave;
        }
        internal static bool Intersects(MapCollisionModel m,HeightPoint a,HeightPoint b) {
            float enter=0,leave=1;
            // Swept upright body box via Minkowski expansion. Height varies with
            // the route segment; an upper-story box does not block lower floors.
            return Clip(a.X,b.X-a.X,m.lower[0]-Radius,m.upper[0]+Radius,ref enter,ref leave) &&
                Clip(a.Y,b.Y-a.Y,m.lower[1]-BodyHeight,m.upper[1]-FootClearance,ref enter,ref leave) &&
                Clip(a.Z,b.Z-a.Z,m.lower[2]-Radius,m.upper[2]+Radius,ref enter,ref leave);
        }
        internal static MapCollisionModel Blocking(MapLive live,HeightPoint a,HeightPoint b) {
            foreach(MapCollisionModel m in live.collision.models)
                if(m.enabled && !SameActor(m.address,live.player.address) && Intersects(m,a,b))return m;
            return null;
        }
        internal static string CheckRoute(MapLive live,NavigationRoute route,int waypoint) {
            try {Require(live);}catch(InvalidDataException error){return error.Message;}
            if(route==null || waypoint<0 || waypoint>route.Points.Count)return "Invalid remaining route";
            HeightPoint prior=new HeightPoint(live.player.position);
            for(int i=waypoint;i<route.Points.Count;i++) {
                MapCollisionModel blocked=Blocking(live,prior,route.Points[i]);
                if(blocked!=null) {MapActor a=Actor(live,blocked.address);return "Route blocked by "+(a==null?"entity":a.Name)+" (Y "+blocked.lower[1].ToString("0")+" to "+blocked.upper[1].ToString("0")+")";}
                prior=route.Points[i];
            }
            return null;
        }
        internal static string Details(MapLive live,MapActor actor) {
            MapCollisionModel model=Model(live,actor.address);
            string text=actor.Name+"\r\nEntity "+actor.address.ToString("X8")+" | behavior "+actor.behavior+
                "\r\nPosition: X "+actor.position[0].ToString("0.0")+"  Y "+actor.position[1].ToString("0.0")+"  Z "+actor.position[2].ToString("0.0");
            if(model==null)return text+"\r\n\r\nCollision bounds unknown. This origin marker is not a solid footprint.";
            return text+"\r\n\r\n"+(model.enabled?"Polygon collision enabled":"Polygon collision disabled")+
                "\r\nBase Y: "+model.lower[1].ToString("0.0")+"\r\nTop Y: "+model.upper[1].ToString("0.0")+
                "\r\nHeight: "+(model.upper[1]-model.lower[1]).ToString("0.0")+
                "\r\nWidth X: "+(model.upper[0]-model.lower[0]).ToString("0.0")+" | Depth Z: "+(model.upper[2]-model.lower[2]).ToString("0.0")+
                "\r\n\r\nConservative bounding box; empty space inside irregular shapes may also be excluded from routes.";
        }
    }
    internal static class CollisionMapDrawing {
        internal static RectangleF Footprint(MapCollisionModel model,Func<HeightPoint,PointF> project) {
            PointF a=project(new HeightPoint(model.lower)),b=project(new HeightPoint(model.upper));
            return RectangleF.FromLTRB(Math.Min(a.X,b.X),Math.Min(a.Y,b.Y),Math.Max(a.X,b.X),Math.Max(a.Y,b.Y));
        }
        internal static void Paint(Graphics g,MapLive live,MapLayers layers,int mode,float low,float high,bool other,bool origins,uint selected,
                Font font,Func<HeightPoint,PointF> project) {
            HashSet<uint> registered=new HashSet<uint>();
            if(live.collision!=null && live.collision.known)foreach(MapCollisionModel m in live.collision.models) {
                registered.Add(m.address & 0x1FFFFFFF);
                if(NavigationCollision.SameActor(m.address,live.player.address))continue;
                bool overlap=mode==2 || m.Overlaps(low,high);
                if(!overlap && !other)continue;
                RectangleF box=Footprint(m,project);if(box.Width<1)box.Width=1;if(box.Height<1)box.Height=1;
                Color top=MapLayers.HeightColor((m.upper[1]-layers.Low)/(layers.High-layers.Low));
                Color bottom=MapLayers.HeightColor((m.lower[1]-layers.Low)/(layers.High-layers.Low));
                bool chosen=NavigationCollision.SameActor(m.address,selected);
                if(overlap && m.enabled) {
                    using(Brush fill=new SolidBrush(Color.FromArgb(155,top)))g.FillRectangle(fill,box);
                    using(Brush band=new SolidBrush(bottom))g.FillRectangle(band,box.X,box.Y,Math.Min(4,box.Width),box.Height);
                }
                using(Pen edge=new Pen(chosen?Color.White:overlap?Color.Orange:Color.FromArgb(100,top),chosen?3:2)) {
                    if(!m.enabled || !overlap)edge.DashStyle=DashStyle.Dash;
                    g.DrawRectangle(edge,box.X,box.Y,box.Width,box.Height);
                }
                // Label sizeable boxes; clicking any box exposes exact extents.
                if(chosen || (overlap && box.Width>=28 && box.Height>=18)) {
                    MapActor actor=NavigationCollision.Actor(live,m.address);
                    string text=(actor==null?"Entity":actor.Name)+"  Y "+m.lower[1].ToString("0")+".."+m.upper[1].ToString("0")+
                        (!m.enabled?" (disabled)":!overlap?m.lower[1]>high?" (above)":" (below)":"");
                    SizeF size=g.MeasureString(text,font);
                    using(Brush bg=new SolidBrush(Color.FromArgb(210,9,16,24)))g.FillRectangle(bg,box.X,box.Y,size.Width,size.Height);
                    g.DrawString(text,font,chosen?Brushes.White:Brushes.Wheat,box.X,box.Y);
                }
            }
            if(origins && live.actors!=null)foreach(MapActor a in live.actors) {
                if(registered.Contains(a.address&0x1FFFFFFF) || NavigationCollision.SameActor(a.address,live.player.address))continue;
                bool off=mode!=2 && (a.position[1]<low||a.position[1]>high);if(off&&!other)continue;
                PointF p=project(new HeightPoint(a.position));bool chosen=NavigationCollision.SameActor(a.address,selected);
                using(Pen pen=new Pen(off?Color.DimGray:Color.Silver,chosen?3:1)) {g.DrawLine(pen,p.X-3,p.Y-3,p.X+3,p.Y+3);g.DrawLine(pen,p.X-3,p.Y+3,p.X+3,p.Y-3);}
                if(chosen)g.DrawString(a.Name+" (bounds unknown)",font,Brushes.White,p.X+6,p.Y);
            }
        }
    }
}
