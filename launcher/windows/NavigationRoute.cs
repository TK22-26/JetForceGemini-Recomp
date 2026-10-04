using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;

namespace JfgLauncher {
    // Floor connectivity with conservative model bounds and bounded terrain probes. Exact capsule motion and parkour remain unproved.
    internal sealed class NavigationRoute {
        // Reserve room for steering drift and stopping. Live checks retain the
        // smaller body envelope, allowing normal tracking error to recover.
        internal const float PlanningMargin=20;
        internal int RunningWaypoint = -1, RunningThrough = -1;
        private long runningUntil;
        internal readonly List<HeightPoint> Points = new List<HeightPoint>();
        internal uint Level;
        internal long Generation;
        internal uint ApproachGate;
        internal float[] GatePosition;
        internal bool ApproachOnly {get {return ApproachGate!=0;} }
        internal bool GateCleared(MapSnapshot map) {
            MapCollisionModel gate=NavigationCollision.Model(map.Live,ApproachGate);
            if(gate==null || !gate.enabled)return true;
            HeightPoint from=Points[Points.Count-1],to=new HeightPoint(GatePosition[0],from.Y,GatePosition[2]);
            return !NavigationCollision.Intersects(gate,from,to);
        }
        private sealed class Edge { internal int To; internal HeightPoint Portal; }
        private sealed class Owner { internal int Triangle; internal HeightPoint A, B; }
        private static string Key(HeightPoint p) {
            return p.X.ToString("R", CultureInfo.InvariantCulture) + "," + p.Y.ToString("R", CultureInfo.InvariantCulture) + "," + p.Z.ToString("R", CultureInfo.InvariantCulture);
        }
        private static float Distance(HeightPoint a, HeightPoint b) {
            float x=a.X-b.X,y=a.Y-b.Y,z=a.Z-b.Z; return (float)Math.Sqrt(x*x+y*y+z*z);
        }
        private static HeightPoint Center(HeightSurface s) {
            return new HeightPoint((s.Points[0].X+s.Points[1].X+s.Points[2].X)/3,
                (s.Points[0].Y+s.Points[1].Y+s.Points[2].Y)/3,(s.Points[0].Z+s.Points[1].Z+s.Points[2].Z)/3);
        }
        private static bool Project(HeightSurface s, HeightPoint p, out HeightPoint result) {
            HeightPoint a=s.Points[0],b=s.Points[1],c=s.Points[2];
            float den=(b.Z-c.Z)*(a.X-c.X)+(c.X-b.X)*(a.Z-c.Z);
            result=p;if(Math.Abs(den)<.001f)return false;
            float u=((b.Z-c.Z)*(p.X-c.X)+(c.X-b.X)*(p.Z-c.Z))/den;
            float v=((c.Z-a.Z)*(p.X-c.X)+(a.X-c.X)*(p.Z-c.Z))/den;
            if(u<-.001f||v<-.001f||u+v>1.001f)return false;
            result=new HeightPoint(p.X,u*a.Y+v*b.Y+(1-u-v)*c.Y,p.Z);return true;
        }
        private static int Floor(List<HeightSurface> floors,HeightPoint p,bool start,out HeightPoint projected) {
            int best=-1;float score=Single.MaxValue;projected=p;
            for(int i=0;i<floors.Count;i++) {
                HeightPoint q;if(!Project(floors[i],p,out q))continue;
                float dy=Math.Abs(q.Y-p.Y);
                if(dy<(start?60:180) && dy<score){score=dy;best=i;projected=q;}
            }
            return best;
        }
        private static List<HeightSurface> WalkingFloors(MapGeometry mesh) {
            List<HeightSurface> floors=new MapLayers(mesh).Floors;
            // The display includes steep upward surfaces; walking uses a more
            // conservative 45-degree limit until character-specific limits are known.
            floors.RemoveAll(delegate(HeightSurface floor) {
                HeightPoint a=floor.Points[0],b=floor.Points[1],c=floor.Points[2];
                HeightPoint normal=Cross(Subtract(b,a),Subtract(c,a));
                double magnitude=Math.Sqrt(Dot(normal,normal));
                return magnitude<.0001 || Math.Abs(normal.Y)/magnitude<.70710678;
            });
            return floors;
        }
        // Follow the changing floor height along a clear horizontal corridor.
        // Triangle-center graphs can miss an overlapping ramp foot or thin deck.
        private static NavigationRoute FollowSurfaceLine(MapSnapshot map,List<HeightSurface> floors,HeightPoint start,HeightPoint goal) {
            float dx=goal.X-start.X,dz=goal.Z-start.Z,length=(float)Math.Sqrt(dx*dx+dz*dz);
            if(length<1||length>5000)return null;
            int count=(int)Math.Ceiling(length/20);if(count>250)return null;
            var raw=new List<HeightPoint>();HeightPoint previous=start;
            for(int i=1;i<=count;i++) {
                var sample=HeightPoint.Lerp(start,goal,(float)i/count);bool found=false;HeightPoint next=sample;
                foreach(var floor in floors) {
                    HeightPoint p;if(!Project(floor,sample,out p)||Math.Abs(p.Y-previous.Y)>24)continue;
                    if(!found||p.Y>next.Y){found=true;next=p;}
                }
                if(!found||!ClearWalk(map,floors,previous,next,PlanningMargin))return null;
                raw.Add(next);previous=next;
            }
            if(Math.Abs(previous.Y-goal.Y)>3)return null;
            var route=new NavigationRoute{Level=map.Live.level,Generation=map.Live.generation};
            previous=start;int at=0;
            while(at<raw.Count) {
                int next=at;
                for(int i=at+1;i<raw.Count;i++) {
                    if(!Supported(floors,previous,raw[i],2)||!ClearWalk(map,floors,previous,raw[i],PlanningMargin))break;
                    next=i;
                }
                route.Points.Add(raw[next]);previous=raw[next];at=next+1;
            }
            float weighted=0,distance=0;previous=start;
            foreach(var point in route.Points){weighted+=TravelCost(map.Live,previous,point);distance+=Distance(previous,point);previous=point;}
            return weighted<=distance*1.01f?route:null;
        }
        internal static bool HasDirectSurfaceWalk(MapSnapshot map,HeightPoint destination) {
            var floors=WalkingFloors(map.Mesh);HeightPoint a,b;
            if(Floor(floors,new HeightPoint(map.Live.player.position),true,out a)<0||
               Floor(floors,destination,false,out b)<0)return false;
            return FollowSurfaceLine(map,floors,a,b)!=null;
        }
        internal static NavigationRoute Plan(MapSnapshot snapshot,float[] destination) {
            if(snapshot==null||snapshot.Live.player==null)throw new InvalidDataException("Enter a room before planning.");
            NavigationCollision.Require(snapshot.Live);
            System.Diagnostics.Stopwatch planning=System.Diagnostics.Stopwatch.StartNew();
            List<HeightSurface> floors=WalkingFloors(snapshot.Mesh);
            if(floors.Count==0||floors.Count>2000)throw new InvalidDataException("Unsupported surface count for route planning.");
            HeightPoint startPoint,endPoint;
            int start=Floor(floors,new HeightPoint(snapshot.Live.player.position),true,out startPoint);
            int goal=Floor(floors,new HeightPoint(destination),false,out endPoint);
            if(start<0||goal<0)throw new InvalidDataException("No matching floor under player or exit. Jump/dive exits need manual control.");
            var surfaceLine=FollowSurfaceLine(snapshot,floors,startPoint,endPoint);if(surfaceLine!=null)return surfaceLine;
            List<Edge>[] graph=new List<Edge>[floors.Count];HeightPoint[] centers=new HeightPoint[floors.Count];
            Dictionary<string,List<Owner>> edges=new Dictionary<string,List<Owner>>();
            for(int i=0;i<floors.Count;i++) {
                graph[i]=new List<Edge>();centers[i]=Center(floors[i]);
                for(int j=0;j<3;j++) {
                    HeightPoint a=floors[i].Points[j],b=floors[i].Points[(j+1)%3];
                    if(Distance(a,b)<40)continue; // Reject narrow portals; this is still not capsule clearance.
                    string ka=Key(a),kb=Key(b),key=String.CompareOrdinal(ka,kb)<0?ka+"|"+kb:kb+"|"+ka;
                    List<Owner> owners;if(!edges.TryGetValue(key,out owners)){owners=new List<Owner>();edges.Add(key,owners);}
                    owners.Add(new Owner {Triangle=i,A=a,B=b});
                }
            }
            foreach(List<Owner> owners in edges.Values) if(owners.Count>=2) {
                Owner a=owners[0],b=owners[1];HeightPoint portal=HeightPoint.Lerp(a.A,a.B,.5f);
                graph[a.Triangle].Add(new Edge {To=b.Triangle,Portal=portal});
                graph[b.Triangle].Add(new Edge {To=a.Triangle,Portal=portal});
            }
            // Collision blocks may split a floor edge or meet across a small step.
            // Stitch only collinear overlapping XZ edges with <=24 units of rise.
            List<Owner> boundary=new List<Owner>();
            foreach(List<Owner> owners in edges.Values)if(owners.Count==1)boundary.Add(owners[0]);
            for(int i=0;i<boundary.Count;i++)for(int j=i+1;j<boundary.Count;j++) {
                Owner a=boundary[i],b=boundary[j];if(a.Triangle==b.Triangle)continue;
                float dx=a.B.X-a.A.X,dz=a.B.Z-a.A.Z,len=(float)Math.Sqrt(dx*dx+dz*dz);if(len<40)continue;
                float ux=dx/len,uz=dz/len;
                if(Math.Abs((b.A.X-a.A.X)*uz-(b.A.Z-a.A.Z)*ux)>.5f || Math.Abs((b.B.X-a.A.X)*uz-(b.B.Z-a.A.Z)*ux)>.5f)continue;
                float ta=(b.A.X-a.A.X)*ux+(b.A.Z-a.A.Z)*uz,tb=(b.B.X-a.A.X)*ux+(b.B.Z-a.A.Z)*uz;
                float low=Math.Max(0,Math.Min(ta,tb)),high=Math.Min(len,Math.Max(ta,tb));if(high-low<40||Math.Abs(tb-ta)<.01f)continue;
                float ya0=a.A.Y+(a.B.Y-a.A.Y)*low/len,ya1=a.A.Y+(a.B.Y-a.A.Y)*high/len;
                float yb0=b.A.Y+(b.B.Y-b.A.Y)*(low-ta)/(tb-ta),yb1=b.A.Y+(b.B.Y-b.A.Y)*(high-ta)/(tb-ta);
                if(Math.Abs(ya0-yb0)>24||Math.Abs(ya1-yb1)>24)continue;
                float mid=(low+high)/2;
                HeightPoint portal=new HeightPoint(a.A.X+ux*mid,(ya0+ya1+yb0+yb1)/4,a.A.Z+uz*mid);
                graph[a.Triangle].Add(new Edge {To=b.Triangle,Portal=portal});graph[b.Triangle].Add(new Edge {To=a.Triangle,Portal=portal});
            }
            float[] cost=new float[floors.Count];int[] previous=new int[floors.Count];bool[] visited=new bool[floors.Count];HeightPoint[] portals=new HeightPoint[floors.Count];
            for(int i=0;i<cost.Length;i++){cost[i]=Single.MaxValue;previous[i]=-1;}cost[start]=0;
            for(int pass=0;pass<floors.Count;pass++) {
                int current=-1;float best=Single.MaxValue;
                for(int i=0;i<cost.Length;i++)if(!visited[i]&&cost[i]<best){best=cost[i];current=i;}
                if(current<0)break;if(current==goal)break;visited[current]=true;
                foreach(Edge edge in graph[current]) {
                    float next=best+Distance(centers[current],edge.Portal)+Distance(edge.Portal,centers[edge.To]);
                    if(next<cost[edge.To]){cost[edge.To]=next;previous[edge.To]=current;portals[edge.To]=edge.Portal;}
                }
            }
            if(start!=goal&&previous[goal]<0)return GlobalRoute(snapshot,floors,startPoint,endPoint);
            NavigationRoute route=new NavigationRoute {Level=snapshot.Live.level,Generation=snapshot.Live.generation};
            List<HeightPoint> reverse=new List<HeightPoint>();
            for(int at=goal;at!=start;at=previous[at]){reverse.Add(portals[at]);if(reverse.Count>254)throw new InvalidDataException("Route exceeds prototype limit.");}
            reverse.Reverse();route.Points.AddRange(reverse);route.Points.Add(endPoint);
            Straighten(route,snapshot.Mesh,floors,startPoint);
            try {
                CollisionRoute(route,snapshot,floors,startPoint,planning);
                float weighted=0,direct=0;HeightPoint previousPoint=startPoint;
                foreach(HeightPoint point in route.Points) {weighted+=TravelCost(snapshot.Live,previousPoint,point);direct+=Distance(previousPoint,point);previousPoint=point;}
                // Even a collision-free short candidate may hug an obstacle.
                // Compare it with the room-wide comfort search before accepting.
                if(weighted>direct*1.01f)try {
                    NavigationRoute wider=GlobalRoute(snapshot,floors,startPoint,endPoint);
                    float widerCost=0;previousPoint=startPoint;
                    foreach(HeightPoint point in wider.Points) {widerCost+=TravelCost(snapshot.Live,previousPoint,point);previousPoint=point;}
                    if(widerCost<weighted)route=wider;
                }catch(InvalidDataException) { /* Keep the already verified candidate. */ }
                return route;
            }
            catch(InvalidDataException) {return GlobalRoute(snapshot,floors,startPoint,endPoint);}
        }
        // The first path is only a candidate. A local repair cannot discover a
        // room-sized loop, so search all floor samples with clearance on every edge.
        private sealed class SearchBounds {
            internal float LX,HX,LZ,HZ;
            internal SearchBounds(HeightPoint[] p) {
                LX=HX=p[0].X;LZ=HZ=p[0].Z;
                foreach(HeightPoint v in p){LX=Math.Min(LX,v.X);HX=Math.Max(HX,v.X);LZ=Math.Min(LZ,v.Z);HZ=Math.Max(HZ,v.Z);}
            }
            internal bool Touch(float lx,float hx,float lz,float hz) {return HX>=lx && LX<=hx && HZ>=lz && LZ<=hz;}
        }
        private sealed class SearchClearance {
            private MapSnapshot map;
            private List<HeightSurface> floors;
            private SearchBounds[] floorBounds,faceBounds;
            internal SearchClearance(MapSnapshot value,List<HeightSurface> surfaces) {
                map=value;floors=surfaces;floorBounds=new SearchBounds[floors.Count];faceBounds=new SearchBounds[map.Mesh.triangles.Length];
                for(int i=0;i<floors.Count;i++)floorBounds[i]=new SearchBounds(floors[i].Points);
                for(int i=0;i<faceBounds.Length;i++) {
                    MapFace f=map.Mesh.triangles[i];faceBounds[i]=new SearchBounds(new HeightPoint[]{new HeightPoint(map.Mesh.vertices[f.v[0]]),new HeightPoint(map.Mesh.vertices[f.v[1]]),new HeightPoint(map.Mesh.vertices[f.v[2]])});
                }
            }
            internal bool Clear(HeightPoint a,HeightPoint b) {
                if(NavigationCollision.Blocking(map.Live,a,b)!=null)return false;
                float pad=NavigationCollision.Radius+PlanningMargin+1,lx=Math.Min(a.X,b.X)-pad,hx=Math.Max(a.X,b.X)+pad,lz=Math.Min(a.Z,b.Z)-pad,hz=Math.Max(a.Z,b.Z)+pad;
                List<HeightSurface> nearby=new List<HeightSurface>();List<MapFace> faces=new List<MapFace>();
                for(int i=0;i<floorBounds.Length;i++)if(floorBounds[i].Touch(lx,hx,lz,hz))nearby.Add(floors[i]);
                for(int i=0;i<faceBounds.Length;i++)if(faceBounds[i].Touch(lx,hx,lz,hz))faces.Add(map.Mesh.triangles[i]);
                return ClearWalk(new MapSnapshot {Live=map.Live,Mesh=new MapGeometry {vertices=map.Mesh.vertices,triangles=faces.ToArray()}},nearby,a,b,PlanningMargin);
            }
        }
        private static float TravelCost(MapLive live,HeightPoint a,HeightPoint b) {
            float factor=NavigationCollision.Blocking(live,a,b,80)!=null?3:
                NavigationCollision.Blocking(live,a,b,120)!=null?1.5f:1;
            return Distance(a,b)*factor;
        }
        private static long Cell(int x,int z) {return ((long)x<<32) ^ (long)(uint)z;}
        private static NavigationRoute GlobalRoute(MapSnapshot map,List<HeightSurface> floors,HeightPoint start,HeightPoint goal) {
            if(NavigationCollision.Blocking(map.Live,start,start)!=null)throw new InvalidDataException("Player is inside a conservative entity box. Move outside it before starting AI.");
            if(NavigationCollision.Blocking(map.Live,goal,goal)!=null)throw new InvalidDataException("Exit approach overlaps an enabled entity collision box.");
            System.Diagnostics.Stopwatch timer=System.Diagnostics.Stopwatch.StartNew();
            List<HeightPoint> nodes=new List<HeightPoint>{start,goal};HashSet<string> unique=new HashSet<string>{Key(start),Key(goal)};
            Action<HeightPoint> add=delegate(HeightPoint point) {
                if(NavigationCollision.Blocking(map.Live,point,point)!=null)return;
                if(unique.Add(Key(point))) {
                    if(nodes.Count>=16000)throw new InvalidDataException("Room-wide clearance graph exceeds its sample limit.");
                    nodes.Add(point);
                }
            };
            foreach(HeightSurface floor in floors) {
                add(Center(floor));
                // Large open triangles also need interior samples; edge-only
                // candidates cannot walk alongside a long obstacle inside one.
                int divisions=Math.Min(32,Math.Max(2,(int)Math.Ceiling(Math.Max(Distance(floor.Points[0],floor.Points[1]),Math.Max(Distance(floor.Points[1],floor.Points[2]),Distance(floor.Points[2],floor.Points[0])))/120)));
                for(int i=1;i<divisions;i++)for(int j=1;j<divisions-i;j++) {
                    float u=(float)i/divisions,v=(float)j/divisions;
                    add(new HeightPoint(floor.Points[0].X*(1-u-v)+floor.Points[1].X*u+floor.Points[2].X*v,
                        floor.Points[0].Y*(1-u-v)+floor.Points[1].Y*u+floor.Points[2].Y*v,
                        floor.Points[0].Z*(1-u-v)+floor.Points[1].Z*u+floor.Points[2].Z*v));
                }
                for(int edge=0;edge<3;edge++) {
                    HeightPoint a=floor.Points[edge],b=floor.Points[(edge+1)%3];
                    int pieces=Math.Max(2,(int)Math.Ceiling(Distance(a,b)/100));
                    for(int i=1;i<pieces;i++)add(HeightPoint.Lerp(a,b,(float)i/pieces));
                }
            }
            foreach(MapCollisionModel box in map.Live.collision.models) {
                if(!box.enabled || NavigationCollision.SameActor(box.address,map.Live.player.address))continue;
                float margin=NavigationCollision.Radius+PlanningMargin+12;
                foreach(float x in new float[]{box.lower[0]-margin,box.upper[0]+margin})
                    foreach(float z in new float[]{box.lower[2]-margin,box.upper[2]+margin})
                        foreach(HeightSurface floor in floors) {HeightPoint point;if(Project(floor,new HeightPoint(x,0,z),out point))add(point);}
            }
            Dictionary<long,List<int>> cells=new Dictionary<long,List<int>>();
            for(int i=0;i<nodes.Count;i++) {
                long key=Cell((int)Math.Floor(nodes[i].X/200),(int)Math.Floor(nodes[i].Z/200));List<int> cell;
                if(!cells.TryGetValue(key,out cell)){cell=new List<int>();cells.Add(key,cell);}cell.Add(i);
            }
            SearchClearance clearance=new SearchClearance(map,floors);
            float[] cost=new float[nodes.Count];int[] previous=new int[nodes.Count];bool[] closed=new bool[nodes.Count];
            for(int i=0;i<nodes.Count;i++){cost[i]=Single.MaxValue;previous[i]=-1;}cost[0]=0;
            for(int iteration=0;iteration<nodes.Count;iteration++) {
                if(timer.ElapsedMilliseconds>3000)throw new InvalidDataException("Room-wide clearance search reached its time limit; no route was verified.");
                int current=-1;float best=Single.MaxValue;
                for(int i=0;i<nodes.Count;i++)if(!closed[i] && cost[i]!=Single.MaxValue) {
                    float estimate=cost[i]+Distance(nodes[i],goal);if(estimate<best){best=estimate;current=i;}
                }
                if(current<0)break;if(current==1)break;closed[current]=true;
                HeightPoint from=nodes[current];int cx=(int)Math.Floor(from.X/200),cz=(int)Math.Floor(from.Z/200);
                for(int x=cx-2;x<=cx+2;x++)for(int z=cz-2;z<=cz+2;z++) {
                    List<int> cell;if(!cells.TryGetValue(Cell(x,z),out cell))continue;
                    foreach(int next in cell) {
                        if(closed[next] || next==current)continue;
                        float length=Distance(from,nodes[next]);if(length>350 || length<.01f)continue;
                        float travel=TravelCost(map.Live,from,nodes[next]);if(cost[current]+travel>=cost[next])continue;
                        if(!clearance.Clear(from,nodes[next]))continue;
                        cost[next]=cost[current]+travel;previous[next]=current;
                    }
                }
            }
            if(previous[1]<0)throw new InvalidDataException("No route found in the room-wide clearance graph; inspect floor, gate and collision bounds.");
            List<HeightPoint> path=new List<HeightPoint>();
            for(int at=1;at!=0;at=previous[at]){path.Add(nodes[at]);if(path.Count>256)throw new InvalidDataException("Room-wide route exceeds waypoint limit.");}
            path.Reverse();NavigationRoute result=new NavigationRoute {Level=map.Live.level,Generation=map.Live.generation};
            int index=0;HeightPoint prior=start;
            while(index<path.Count) {
                int next=index;
                float originalCost=0;HeightPoint segmentStart=prior;
                for(int i=index;i<path.Count;i++) {
                    originalCost+=TravelCost(map.Live,segmentStart,path[i]);segmentStart=path[i];
                    if(Distance(prior,path[i])<=500 && TravelCost(map.Live,prior,path[i])<=originalCost*1.001f && clearance.Clear(prior,path[i]))next=i;
                }
                result.Points.Add(path[next]);prior=path[next];index=next+1;
            }
            return result;
        }
        private sealed class Span { internal float Low,High; }
        private static bool Clip(float value,float delta,ref float low,ref float high) {
            if(Math.Abs(delta)<.000001f)return value>=-.0001f;
            float crossing=-value/delta;
            if(delta>0)low=Math.Max(low,crossing);else high=Math.Min(high,crossing);
            return low<=high+.00001f;
        }
        private static bool Supported(List<HeightSurface> floors,HeightPoint from,HeightPoint to,float tolerance=2) {
            List<Span> spans=new List<Span>();
            foreach(HeightSurface floor in floors) {
                HeightPoint a=floor.Points[0],b=floor.Points[1],c=floor.Points[2];
                float ux=b.X-a.X,uy=b.Y-a.Y,uz=b.Z-a.Z,vx=c.X-a.X,vy=c.Y-a.Y,vz=c.Z-a.Z;
                float nx=uy*vz-uz*vy,ny=uz*vx-ux*vz,nz=ux*vy-uy*vx;
                if(Math.Abs(ny)<.0001f)continue;
                float winding=(ux*vz-uz*vx)>0?1:-1,low=0,high=1;
                bool inside=true;
                for(int i=0;i<3;i++) {
                    HeightPoint p=floor.Points[i],q=floor.Points[(i+1)%3];float ex=q.X-p.X,ez=q.Z-p.Z;
                    if(!Clip(winding*(ex*(from.Z-p.Z)-ez*(from.X-p.X)),winding*(ex*(to.Z-from.Z)-ez*(to.X-from.X)),ref low,ref high)){inside=false;break;}
                }
                if(!inside)continue;
                float fromFloor=a.Y-(nx*(from.X-a.X)+nz*(from.Z-a.Z))/ny;
                float toFloor=a.Y-(nx*(to.X-a.X)+nz*(to.Z-a.Z))/ny;
                float difference=from.Y-fromFloor,delta=(to.Y-toFloor)-difference;
                if(!Clip(tolerance-difference,-delta,ref low,ref high)||!Clip(tolerance+difference,delta,ref low,ref high))continue;
                if(low<=high)spans.Add(new Span {Low=low,High=high});
            }
            spans.Sort(delegate(Span a,Span b){return a.Low.CompareTo(b.Low);});float covered=0;
            foreach(Span span in spans){if(span.Low>covered+.00001f)return false;covered=Math.Max(covered,span.High);if(covered>=.99999f)return true;}
            return false;
        }
        private static HeightPoint Subtract(HeightPoint a,HeightPoint b){return new HeightPoint(a.X-b.X,a.Y-b.Y,a.Z-b.Z);}
        private static HeightPoint Cross(HeightPoint a,HeightPoint b){return new HeightPoint(a.Y*b.Z-a.Z*b.Y,a.Z*b.X-a.X*b.Z,a.X*b.Y-a.Y*b.X);}
        private static float Dot(HeightPoint a,HeightPoint b){return a.X*b.X+a.Y*b.Y+a.Z*b.Z;}
        internal static bool Obstructed(MapGeometry mesh,HeightPoint from,HeightPoint to) {
            HeightPoint direction=Subtract(to,from);
            foreach(MapFace face in mesh.triangles) {
                HeightPoint a=new HeightPoint(mesh.vertices[face.v[0]]),edge1=Subtract(new HeightPoint(mesh.vertices[face.v[1]]),a),edge2=Subtract(new HeightPoint(mesh.vertices[face.v[2]]),a);
                HeightPoint h=Cross(direction,edge2);float determinant=Dot(edge1,h);if(Math.Abs(determinant)<.00001f)continue;
                float inverse=1/determinant;HeightPoint s=Subtract(from,a);float u=inverse*Dot(s,h);if(u<0||u>1)continue;
                HeightPoint q=Cross(s,edge1);float v=inverse*Dot(direction,q);if(v<0||u+v>1)continue;
                float t=inverse*Dot(edge2,q);if(t>.0001f && t<.9999f)return true;
            }
            return false;
        }
        internal static bool StraightWalk(MapGeometry mesh,List<HeightSurface> floors,HeightPoint from,HeightPoint to) {
            float dx=to.X-from.X,dz=to.Z-from.Z,length=(float)Math.Sqrt(dx*dx+dz*dz);
            if(length<.01f||length>600||Math.Abs(to.Y-from.Y)>80)return false;
            // Continuous surface coverage prevents shortcuts across even thin gaps
            // or another story. Three offset probes keep a 40-unit floor strip.
            foreach(float offset in new float[]{-20,0,20}) {
                float ox=-dz/length*offset,oz=dx/length*offset;
                HeightPoint a=new HeightPoint(from.X+ox,from.Y,from.Z+oz),b=new HeightPoint(to.X+ox,to.Y,to.Z+oz);
                if(!Supported(floors,a,b))return false;
                foreach(float height in new float[]{4,40,80})
                    if(Obstructed(mesh,new HeightPoint(a.X,a.Y+height,a.Z),new HeightPoint(b.X,b.Y+height,b.Z)))return false;
                for(float t=0;t<=1;t+=Math.Min(1,24/length)) {
                    HeightPoint p=HeightPoint.Lerp(a,b,t);
                    if(Obstructed(mesh,new HeightPoint(p.X,p.Y+4,p.Z),new HeightPoint(p.X,p.Y+80,p.Z)))return false;
                }
            }
            return true;
        }
        internal static void Straighten(NavigationRoute route,MapGeometry mesh,List<HeightSurface> floors,HeightPoint start) {
            List<HeightPoint> original=new List<HeightPoint>(route.Points);route.Points.Clear();int at=-1;
            while(at<original.Count-1) {
                int next=at+1;
                for(int end=original.Count-1;end>at+1;--end)
                    if(StraightWalk(mesh,floors,start,original[end])){next=end;break;}
                start=original[next];route.Points.Add(start);at=next;
            }
        }

        // Every emitted walking segment needs continuous supporting floor,
        // vertical/static probes, and a swept entity-body clearance check.
        internal static bool ClearWalk(MapSnapshot map,List<HeightSurface> floors,HeightPoint a,HeightPoint b,float margin=0) {
            if(NavigationCollision.Blocking(map.Live,a,b,NavigationCollision.Radius+margin)!=null)return false;
            float dx=b.X-a.X,dz=b.Z-a.Z,length=(float)Math.Sqrt(dx*dx+dz*dz);
            if(length<.001f)return Math.Abs(a.Y-b.Y)<=24;
            if(length>600 || Math.Abs(a.Y-b.Y)>80 || Math.Abs(a.Y-b.Y)>length+24)return false;
            foreach(float offset in margin>0?new float[]{-NavigationCollision.Radius-margin*.4f,-NavigationCollision.Radius,0,NavigationCollision.Radius,NavigationCollision.Radius+margin*.4f}:new float[]{-NavigationCollision.Radius,0,NavigationCollision.Radius}) {
                float ox=-dz/length*offset,oz=dx/length*offset;
                HeightPoint from=new HeightPoint(a.X+ox,a.Y,a.Z+oz),to=new HeightPoint(b.X+ox,b.Y,b.Z+oz);
                if(!Supported(floors,from,to,24))return false;
                // Small steps up to 24 are permitted by floor connectivity.
                // These terrain probes are conservative, not an exact capsule.
                foreach(float y in new float[]{28,54,80})
                    if(Obstructed(map.Mesh,new HeightPoint(from.X,from.Y+y,from.Z),new HeightPoint(to.X,to.Y+y,to.Z)))return false;
                int steps=Math.Max(1,(int)Math.Ceiling(length/24));
                for(int i=0;i<=steps;i++) {
                    HeightPoint p=HeightPoint.Lerp(from,to,(float)i/steps);
                    if(Obstructed(map.Mesh,new HeightPoint(p.X,p.Y+28,p.Z),new HeightPoint(p.X,p.Y+80,p.Z)))return false;
                }
            }
            return true;
        }
        private static List<HeightPoint> Detour(MapSnapshot map,List<HeightSurface> floors,HeightPoint from,HeightPoint to,System.Diagnostics.Stopwatch planning) {
            List<HeightPoint> points=new List<HeightPoint> {from,to};
            float lx=Math.Min(from.X,to.X)-360,hx=Math.Max(from.X,to.X)+360;
            float lz=Math.Min(from.Z,to.Z)-360,hz=Math.Max(from.Z,to.Z)+360;
            float ly=Math.Min(from.Y,to.Y)-80,hy=Math.Max(from.Y,to.Y)+80;
            Action<HeightPoint> add=delegate(HeightPoint p) {
                if(p.X<lx || p.X>hx || p.Z<lz || p.Z>hz || p.Y<ly || p.Y>hy || NavigationCollision.Blocking(map.Live,p,p)!=null)return;
                foreach(HeightPoint prior in points)if(Distance(prior,p)<2)return;
                if(points.Count<256)points.Add(p);
            };
            // Expanded-box corners create possible routes around an object even
            // when its bounds occupy the center of a large floor triangle.
            foreach(MapCollisionModel box in map.Live.collision.models) {
                if(!box.enabled || NavigationCollision.SameActor(box.address,map.Live.player.address) || !box.Overlaps(ly,hy+80))continue;
                float margin=NavigationCollision.Radius+PlanningMargin+12;
                foreach(float x in new float[]{box.lower[0]-margin,box.upper[0]+margin})
                    foreach(float z in new float[]{box.lower[2]-margin,box.upper[2]+margin})
                        foreach(HeightSurface floor in floors) {HeightPoint p;if(Project(floor,new HeightPoint(x,from.Y,z),out p))add(p);}
            }
            foreach(HeightSurface floor in floors) {
                add(Center(floor));
                // Large open triangles also need interior samples; edge-only
                // candidates cannot walk alongside a long obstacle inside one.
                int divisions=Math.Min(32,Math.Max(2,(int)Math.Ceiling(Math.Max(Distance(floor.Points[0],floor.Points[1]),Math.Max(Distance(floor.Points[1],floor.Points[2]),Distance(floor.Points[2],floor.Points[0])))/120)));
                for(int i=1;i<divisions;i++)for(int j=1;j<divisions-i;j++) {
                    float u=(float)i/divisions,v=(float)j/divisions;
                    add(new HeightPoint(floor.Points[0].X*(1-u-v)+floor.Points[1].X*u+floor.Points[2].X*v,
                        floor.Points[0].Y*(1-u-v)+floor.Points[1].Y*u+floor.Points[2].Y*v,
                        floor.Points[0].Z*(1-u-v)+floor.Points[1].Z*u+floor.Points[2].Z*v));
                }
                for(int i=0;i<3;i++)add(HeightPoint.Lerp(floor.Points[i],floor.Points[(i+1)%3],.5f));
            }
            int count=points.Count;float[] cost=new float[count];int[] previous=new int[count];bool[] closed=new bool[count];
            for(int i=0;i<count;i++){cost[i]=Single.MaxValue;previous[i]=-1;}cost[0]=0;
            // Bounded visibility search. An unverified edge is never emitted.
            for(int pass=0;pass<count;pass++) {
                int at=-1;float best=Single.MaxValue;
                for(int i=0;i<count;i++)if(!closed[i] && cost[i]!=Single.MaxValue) {float estimate=cost[i]+Distance(points[i],to);if(estimate<best){best=estimate;at=i;}}
                if(at<0)break;if(at==1)break;closed[at]=true;
                if(planning.ElapsedMilliseconds>2000)throw new InvalidDataException("Clearance search reached its time limit; move closer or choose another exit.");
                for(int next=0;next<count;next++) {
                    if(closed[next] || next==at)continue;
                    float d=Distance(points[at],points[next]);if(d>600)continue;
                    float travel=TravelCost(map.Live,points[at],points[next]);if(cost[at]+travel>=cost[next])continue;
                    if(!ClearWalk(map,floors,points[at],points[next],PlanningMargin))continue;
                    cost[next]=cost[at]+travel;previous[next]=at;
                }
            }
            if(previous[1]<0)throw new InvalidDataException("No verified clearance around entity or terrain obstruction. Move manually or choose another exit.");
            List<HeightPoint> path=new List<HeightPoint>();for(int at=1;at!=0;at=previous[at])path.Add(points[at]);path.Reverse();return path;
        }
        private static void CollisionRoute(NavigationRoute route,MapSnapshot map,List<HeightSurface> floors,HeightPoint start,System.Diagnostics.Stopwatch planning) {
            if(NavigationCollision.Blocking(map.Live,start,start)!=null)
                throw new InvalidDataException("Player is inside a conservative entity box. Move outside it before starting AI.");
            HeightPoint goal=route.Points[route.Points.Count-1];
            if(NavigationCollision.Blocking(map.Live,goal,goal)!=null)
                throw new InvalidDataException("Exit approach overlaps an enabled entity collision box.");
            List<HeightPoint> candidate=new List<HeightPoint>();
            foreach(HeightPoint p in route.Points)if(NavigationCollision.Blocking(map.Live,p,p)==null)candidate.Add(p);
            route.Points.Clear();HeightPoint previous=start;
            foreach(HeightPoint target in candidate) {
                if(planning.ElapsedMilliseconds>2000)throw new InvalidDataException("Clearance search reached its time limit; move closer or choose another exit.");
                // Subdivision preserves long unobstructed segments without
                // bypassing the bounded per-segment collision checks.
                int pieces=Math.Max(1,(int)Math.Ceiling(Distance(previous,target)/500));
                HeightPoint begin=previous;
                for(int i=1;i<=pieces;i++) {
                    HeightPoint next=HeightPoint.Lerp(begin,target,(float)i/pieces);
                    if(ClearWalk(map,floors,previous,next,PlanningMargin))route.Points.Add(next);
                    else route.Points.AddRange(Detour(map,floors,previous,next,planning));
                    previous=next;
                    if(route.Points.Count>256)throw new InvalidDataException("Clearance route exceeds prototype waypoint limit.");
                }
            }
            // Only remove corners when both surface and entity tests succeed.
            List<HeightPoint> original=new List<HeightPoint>(route.Points);route.Points.Clear();int at=-1;previous=start;
            while(at<original.Count-1) {
                int next=at+1;
                float originalCost=0;HeightPoint segmentStart=previous;
                for(int i=next;i<original.Count;i++) {
                    originalCost+=TravelCost(map.Live,segmentStart,original[i]);segmentStart=original[i];
                    if(TravelCost(map.Live,previous,original[i])<=originalCost*1.001f && ClearWalk(map,floors,previous,original[i],PlanningMargin))next=i;
                }
                route.Points.Add(original[next]);previous=original[next];at=next;
            }
        }

        internal static string ExitRequirement(MapSnapshot snapshot,MapMarker exit) {
            if(snapshot.Live.progression!=null)foreach(var node in snapshot.Live.progression.nodes)
                if(node.address==exit.address) {
                    if(node.condition_known&&!node.condition_met)return "Exit is an inactive progression alternative.";
                    if(node.access_known&&!node.access_allowed&&node.status!="enemies_remaining")
                        return "Door requirement: "+node.requirement+".";
                }
            return null;
        }
        internal static NavigationRoute PlanExit(MapSnapshot snapshot,MapMarker exit) {
            string requirement=ExitRequirement(snapshot,exit);
            if(requirement!=null)throw new InvalidDataException(requirement);
            // Old captures without a measured trigger retain the compatibility
            // path. Real exports include the sphere and plane used by exitControl.
            if(exit.radius<24||exit.radius>4096||exit.normal==null)return PlanExitLegacy(snapshot,exit);
            var floors=WalkingFloors(snapshot.Mesh);
            float nx=exit.normal[0],nz=exit.normal[2],len=(float)Math.Sqrt(nx*nx+nz*nz);
            if(len<.1f)throw new InvalidDataException("Exit needs vertical traversal; no horizontal crossing direction.");
            nx/=len;nz/=len;
            if(exit.directional==0) {
                var p=snapshot.Live.player.position;
                if((p[0]-exit.position[0])*nx+(p[2]-exit.position[2])*nz<0){nx=-nx;nz=-nz;}
            }
            // Search across the opening, rather than treating the actor origin
            // as its centre. Verify both floor support and body clearance.
            var candidates=new List<HeightPoint[]>();
            foreach(float offset in new float[]{0,4,-4,8,-8,12,-12,16,-16,24,-24,32,-32,48,-48,64,-64,80,-80,96,-96}) {
                if(Math.Abs(offset)>exit.radius*.7f)continue;
                float x=exit.position[0]-nz*offset,z=exit.position[2]+nx*offset;
                foreach(float depth in new float[]{32,16}) {
                    HeightPoint near,through;
                    if(Floor(floors,new HeightPoint(x+nx*64,exit.position[1],z+nz*64),false,out near)<0||
                       Floor(floors,new HeightPoint(x-nx*depth,exit.position[1],z-nz*depth),false,out through)<0)continue;
                    if(Distance(through,new HeightPoint(exit.position))>exit.radius-4)continue;
                    if(exit.directional!=0 && exit.normal[0]*through.X+exit.normal[1]*through.Y+exit.normal[2]*through.Z+exit.plane_d>=-8)continue;
                    if(!ClearWalk(snapshot,floors,near,through))continue;
                    candidates.Add(new HeightPoint[]{near,through});
                }
            }
            // Prefer lanes with steering room, then the smallest lateral shift.
            candidates.Sort(delegate(HeightPoint[] a,HeightPoint[] b) {
                bool ac=ClearWalk(snapshot,floors,a[0],a[1],PlanningMargin),bc=ClearWalk(snapshot,floors,b[0],b[1],PlanningMargin);
                if(ac!=bc)return ac?-1:1;
                return Distance(a[1],new HeightPoint(exit.position)).CompareTo(Distance(b[1],new HeightPoint(exit.position)));
            });
            int attempts=0;
            foreach(var lane in candidates) {
                if(++attempts>6)break;
                try {
                    var route=Plan(snapshot,new[]{lane[0].X,lane[0].Y,lane[0].Z});
                    route.Points.Add(lane[1]);return route;
                }catch(InvalidDataException){}
                // A short doorway throat may begin before the default approach,
                // for example beside a low object just outside a lifting door.
                // Extend only this verified body-clear final leg; keep normal
                // comfort clearance for the route leading to it.
                HeightPoint farther;
                if(Floor(floors,new HeightPoint(lane[0].X+nx*128,lane[0].Y,lane[0].Z+nz*128),false,out farther)>=0&&
                   ClearWalk(snapshot,floors,farther,lane[1])) {
                    try {
                        var route=Plan(snapshot,new[]{farther.X,farther.Y,farther.Z});
                        route.Points.Add(lane[1]);return route;
                    }catch(InvalidDataException){}
                }
            }
            // A closed proximity gate still needs a safe approach so the game
            // can open it. The explorer waits for observed collision clearance.
            MapInteraction gateNode=null;float best=240;
            if(snapshot.Live.progression!=null)foreach(var node in snapshot.Live.progression.nodes) {
                if(node.action!="pass_door")continue;
                var box=NavigationCollision.Model(snapshot.Live,node.address);
                if(box==null||!box.enabled)continue;
                float d=Distance(new HeightPoint(node.position),new HeightPoint(exit.position));
                if(d<best){best=d;gateNode=node;}
            }
            if(gateNode!=null)return PlanDoorApproach(snapshot,exit,gateNode);
            throw new InvalidDataException("No clear walking lane crosses this exit trigger; inspect floor, height and door requirements.");
        }
        // The exit sphere can lie in front of, inside, or behind a door.
        // Approach from the player's side of the door plane, independently of
        // the trigger's location. Never plan to the far side of closed collision.
        private static NavigationRoute PlanDoorApproach(MapSnapshot snapshot,MapMarker exit,MapInteraction node) {
            if(node.access_known&&!node.access_allowed&&node.status!="enemies_remaining")
                throw new InvalidDataException("Door requirement: "+node.requirement+".");
            var gate=NavigationCollision.Model(snapshot.Live,node.address);
            float x=(gate.lower[0]+gate.upper[0])/2,z=(gate.lower[2]+gate.upper[2])/2;
            bool alongX=exit.normal!=null&&(Math.Abs(exit.normal[0])+Math.Abs(exit.normal[2])>.1f)
                ? Math.Abs(exit.normal[0])>Math.Abs(exit.normal[2])
                : gate.upper[0]-gate.lower[0]<gate.upper[2]-gate.lower[2];
            var player=snapshot.Live.player.position;
            var margins=new List<float>{36,20,8};
            if(node.approach_radius>=64&&node.approach_radius<=4096)
                margins.Insert(0,node.approach_radius*.72f-NavigationCollision.Radius);
            foreach(float margin in margins) {
                float px=x,pz=z,pad=NavigationCollision.Radius+margin;
                if(alongX)px=player[0]<x?gate.lower[0]-pad:gate.upper[0]+pad;
                else pz=player[2]<z?gate.lower[2]-pad:gate.upper[2]+pad;
                try {
                    var route=Plan(snapshot,new[]{px,node.position[1],pz});
                    if(node.approach_radius!=0&&
                       Distance(route.Points[route.Points.Count-1],new HeightPoint(node.position))>=node.approach_radius-12)continue;
                    route.ApproachGate=gate.address;
                    // Keep the original doorway location while its model moves.
                    // A trigger before the door cannot prove the door has lifted.
                    route.GatePosition=new[]{x,node.position[1],z};
                    return route;
                }catch(InvalidDataException){}
            }
            throw new InvalidDataException("No clear approach reaches the door's opening radius.");
        }
        private static NavigationRoute PlanExitLegacy(MapSnapshot snapshot,MapMarker exit) {
            NavigationRoute route;
            try {route=Plan(snapshot,exit.position);}
            catch(InvalidDataException) {
                // A trigger behind a closed door is not the same as an unreachable
                // room. Offer a verified route up to its near side, without crossing.
                MapInteraction nearest=null;float best=240;
                if(snapshot.Live.progression!=null)foreach(MapInteraction node in snapshot.Live.progression.nodes) {
                    if(node.action!="pass_door")continue;
                    MapCollisionModel box=NavigationCollision.Model(snapshot.Live,node.address);
                    if(box==null || !box.enabled)continue;
                    float distance=Distance(new HeightPoint(node.position),new HeightPoint(exit.position));
                    if(distance<best){best=distance;nearest=node;}
                }
                if(nearest==null) {
                    if(exit.radius>=24&&exit.radius<=256&&exit.normal!=null) {
                        float approachX=exit.normal[0],approachZ=exit.normal[2],len=(float)Math.Sqrt(approachX*approachX+approachZ*approachZ);
                        if(len>.1f) {
                            approachX/=len;approachZ/=len;
                            var p=snapshot.Live.player.position;
                            if((p[0]-exit.position[0])*approachX+(p[2]-exit.position[2])*approachZ<0){approachX=-approachX;approachZ=-approachZ;}
                            foreach(float offset in new float[]{24,40,56})if(offset<exit.radius)
                                try {
                                    var near=Plan(snapshot,new[]{exit.position[0]+approachX*offset,exit.position[1],exit.position[2]+approachZ*offset});
                                    var nearEnd=near.Points[near.Points.Count-1];
                                    var through=new HeightPoint(exit.position[0]-approachX*48,nearEnd.Y,exit.position[2]-approachZ*48);
                                    // Only the final doorway leg may shed the extra steering
                                    // margin. Retain full body, floor and headroom clearance.
                                    if(ClearWalk(snapshot,WalkingFloors(snapshot.Mesh),nearEnd,through))
                                        near.Points.Add(through);
                                    return near;
                                }catch(InvalidDataException){}
                        }
                    }
                    throw;
                }
                return PlanDoorApproach(snapshot,exit,nearest);
            }
            HeightPoint end=route.Points[route.Points.Count-1];
            HeightPoint from=route.Points.Count>1?route.Points[route.Points.Count-2]:new HeightPoint(snapshot.Live.player.position);
            float dx=end.X-from.X,dz=end.Z-from.Z,length=(float)Math.Sqrt(dx*dx+dz*dz);
            if(length<1)return route;
            // Continue a short distance through the doorway only on connected floor.
            // No radius/condition field is interpreted as proof that the gate is open.
            float nx=dx/length,nz=dz/length;
            if(exit.normal!=null) {
                float horizontal=(float)Math.Sqrt(exit.normal[0]*exit.normal[0]+exit.normal[2]*exit.normal[2]);
                if(horizontal>.2f) {
                    nx=exit.normal[0]/horizontal;nz=exit.normal[2]/horizontal;
                    if(nx*dx+nz*dz<0){nx=-nx;nz=-nz;}
                }
            }
            MapSnapshot approach=new MapSnapshot {Mesh=snapshot.Mesh,Live=new MapLive {
                level=snapshot.Live.level,generation=snapshot.Live.generation,actors=snapshot.Live.actors,collision=snapshot.Live.collision,player=new MapPlayer {address=snapshot.Live.player.address,position=new float[]{end.X,end.Y,end.Z}}}};
            try {
                NavigationRoute crossing=Plan(approach,new float[]{end.X+nx*48,end.Y,end.Z+nz*48});
                float travel=0;HeightPoint previous=end;
                foreach(HeightPoint point in crossing.Points){travel+=Distance(previous,point);previous=point;}
                if(travel<=96 && crossing.Points.Count<=3 && route.Points.Count+crossing.Points.Count<=256)route.Points.AddRange(crossing.Points);
            }catch(InvalidDataException) { /* Approach only; the explorer verifies the actual transition. */ }
            return route;
        }
        private MapGeometry clearanceMesh;
        private List<HeightSurface> clearanceFloors;
        internal string CheckRemaining(MapSnapshot map,int waypoint) {
            RunningWaypoint=RunningThrough=-1;runningUntil=0;
            string blocked=NavigationCollision.CheckRoute(map.Live,this,waypoint);
            if(blocked!=null)return blocked;
            if(waypoint>=Points.Count)return null;
            if(clearanceMesh!=map.Mesh) {clearanceMesh=map.Mesh;clearanceFloors=WalkingFloors(map.Mesh);}
            HeightPoint start;
            if(Floor(clearanceFloors,new HeightPoint(map.Live.player.position),true,out start)<0)
                return "Player has left the mapped walking floor";
            if(!ClearWalk(map,clearanceFloors,start,Points[waypoint]))
                return "Route blocked by terrain or floor clearance from current position";
            // Certify a rolling portion of the route, not one isolated point.
            // Reuse the route's steering margin rather than requiring 80-unit
            // model clearance along the entire remaining segment.
            if(map.IsLive && map.Live.clearing_active && !map.Live.scripted_camera) {
                HeightPoint prior=start;float ahead=0;
                for(int i=waypoint;i<Points.Count && ahead<240;i++) {
                    if(!ClearWalk(map,clearanceFloors,prior,Points[i],PlanningMargin))break;
                    ahead+=Distance(prior,Points[i]);prior=Points[i];RunningThrough=i;
                }
                if(RunningThrough>=waypoint) {RunningWaypoint=waypoint;runningUntil=map.Live.timestamp_ms+500;}
            }
            return null;
        }
        internal string DispatchProblem(MapSnapshot planned,MapSnapshot current) {
            if(!current.IsLive)return "map updates stopped while planning";
            if(Level!=current.Live.level || Generation!=current.Live.generation || current.Live.update<planned.Live.update)
                return "room or game state changed while planning";
            if(!current.Live.clearing_active)return "gameplay controls suspended while planning";
            long before=planned.Live.navigation_ai==null?0:planned.Live.navigation_ai.manual_inputs;
            long after=current.Live.navigation_ai==null?0:current.Live.navigation_ai.manual_inputs;
            if(before!=after)return "manual input detected while planning";
            return CheckRemaining(current,0);
        }
        internal static void ConfirmTransition(string directory,MapLive live,long nonce) {
            string path=Path.Combine(directory,"ai-confirm.txt"),temp=path+".tmp";
            string command="JFGCONFIRM1 "+live.level+" "+live.generation+" "+nonce+" "+NavigationExplorer.Clock+" "+
                (live.navigation_ai==null?0:live.navigation_ai.manual_inputs)+"\n";
            File.WriteAllText(temp,command,new UTF8Encoding(false));
            if(File.Exists(path))File.Replace(temp,path,null);else File.Move(temp,path);
        }
        internal void Send(string directory,long nonce,bool jumps,bool stop) {
            long now=(long)(DateTime.UtcNow-new DateTime(1970,1,1,0,0,0,DateTimeKind.Utc)).TotalMilliseconds;
            int running=!stop && now<=runningUntil?RunningWaypoint:-1;
            StringBuilder text=new StringBuilder("JFGNAV3 "+Level+" "+Generation+" "+nonce+" "+now+" "+(jumps?1:0)+" "+(stop?0:Points.Count)+" "+running+" "+(running<0?-1:RunningThrough)+"\n");
            if(!stop)foreach(HeightPoint p in Points)text.Append(p.X.ToString("R",CultureInfo.InvariantCulture)+" "+p.Y.ToString("R",CultureInfo.InvariantCulture)+" "+p.Z.ToString("R",CultureInfo.InvariantCulture)+"\n");
            string path=Path.Combine(directory,"ai-command.txt"),temporary=path+".tmp";
            File.WriteAllText(temporary,text.ToString(),new UTF8Encoding(false));
            if(File.Exists(path))File.Replace(temporary,path,null);else File.Move(temporary,path);
        }
    }
}
