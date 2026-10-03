using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;

namespace JfgLauncher {
    // Floor connectivity with conservative model bounds and bounded terrain probes. Exact capsule motion and parkour remain unproved.
    internal sealed class NavigationRoute {
        internal readonly List<HeightPoint> Points = new List<HeightPoint>();
        internal uint Level;
        internal long Generation;
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
        internal static NavigationRoute Plan(MapSnapshot snapshot,float[] destination) {
            if(snapshot==null||snapshot.Live.player==null)throw new InvalidDataException("Enter a room before planning.");
            NavigationCollision.Require(snapshot.Live);
            System.Diagnostics.Stopwatch planning=System.Diagnostics.Stopwatch.StartNew();
            List<HeightSurface> floors=new MapLayers(snapshot.Mesh).Floors;
            // The display includes steep upward surfaces; walking uses a more
            // conservative 45-degree limit until character-specific limits are known.
            floors.RemoveAll(delegate(HeightSurface floor) {
                HeightPoint a=floor.Points[0],b=floor.Points[1],c=floor.Points[2];
                HeightPoint normal=Cross(Subtract(b,a),Subtract(c,a));
                double magnitude=Math.Sqrt(Dot(normal,normal));
                return magnitude<.0001 || Math.Abs(normal.Y)/magnitude<.70710678;
            });
            if(floors.Count==0||floors.Count>2000)throw new InvalidDataException("Unsupported surface count for route planning.");
            HeightPoint startPoint,endPoint;
            int start=Floor(floors,new HeightPoint(snapshot.Live.player.position),true,out startPoint);
            int goal=Floor(floors,new HeightPoint(destination),false,out endPoint);
            if(start<0||goal<0)throw new InvalidDataException("No matching floor under player or exit. Jump/dive exits need manual control.");
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
            if(start!=goal&&previous[goal]<0)throw new InvalidDataException("No connected surface route. Gaps, stacked floors and parkour are not bridged automatically.");
            NavigationRoute route=new NavigationRoute {Level=snapshot.Live.level,Generation=snapshot.Live.generation};
            List<HeightPoint> reverse=new List<HeightPoint>();
            for(int at=goal;at!=start;at=previous[at]){reverse.Add(portals[at]);if(reverse.Count>254)throw new InvalidDataException("Route exceeds prototype limit.");}
            reverse.Reverse();route.Points.AddRange(reverse);route.Points.Add(endPoint);
            Straighten(route,snapshot.Mesh,floors,startPoint);
            CollisionRoute(route,snapshot,floors,startPoint,planning);return route;
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
        private static bool Obstructed(MapGeometry mesh,HeightPoint from,HeightPoint to) {
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
        internal static bool ClearWalk(MapSnapshot map,List<HeightSurface> floors,HeightPoint a,HeightPoint b) {
            if(NavigationCollision.Blocking(map.Live,a,b)!=null)return false;
            float dx=b.X-a.X,dz=b.Z-a.Z,length=(float)Math.Sqrt(dx*dx+dz*dz);
            if(length<.001f)return Math.Abs(a.Y-b.Y)<=24;
            if(length>600 || Math.Abs(a.Y-b.Y)>80 || Math.Abs(a.Y-b.Y)>length+24)return false;
            foreach(float offset in new float[]{-20,0,20}) {
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
                float margin=NavigationCollision.Radius+8;
                foreach(float x in new float[]{box.lower[0]-margin,box.upper[0]+margin})
                    foreach(float z in new float[]{box.lower[2]-margin,box.upper[2]+margin})
                        foreach(HeightSurface floor in floors) {HeightPoint p;if(Project(floor,new HeightPoint(x,from.Y,z),out p))add(p);}
            }
            foreach(HeightSurface floor in floors) {
                add(Center(floor));
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
                    float d=Distance(points[at],points[next]);if(d>600 || cost[at]+d>=cost[next])continue;
                    if(!ClearWalk(map,floors,points[at],points[next]))continue;
                    cost[next]=cost[at]+d;previous[next]=at;
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
                    if(ClearWalk(map,floors,previous,next))route.Points.Add(next);
                    else route.Points.AddRange(Detour(map,floors,previous,next,planning));
                    previous=next;
                    if(route.Points.Count>256)throw new InvalidDataException("Clearance route exceeds prototype waypoint limit.");
                }
            }
            // Only remove corners when both surface and entity tests succeed.
            List<HeightPoint> original=new List<HeightPoint>(route.Points);route.Points.Clear();int at=-1;previous=start;
            while(at<original.Count-1) {
                int next=at+1;
                for(int i=original.Count-1;i>next;i--)if(ClearWalk(map,floors,previous,original[i])){next=i;break;}
                route.Points.Add(original[next]);previous=original[next];at=next;
            }
        }

        internal static NavigationRoute PlanExit(MapSnapshot snapshot,MapMarker exit) {
            NavigationRoute route=Plan(snapshot,exit.position);
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
        internal static void ConfirmTransition(string directory,MapLive live,long nonce) {
            string path=Path.Combine(directory,"ai-confirm.txt"),temp=path+".tmp";
            string command="JFGCONFIRM1 "+live.level+" "+live.generation+" "+nonce+" "+NavigationExplorer.Clock+" "+
                (live.navigation_ai==null?0:live.navigation_ai.manual_inputs)+"\n";
            File.WriteAllText(temp,command,new UTF8Encoding(false));
            if(File.Exists(path))File.Replace(temp,path,null);else File.Move(temp,path);
        }
        internal void Send(string directory,long nonce,bool jumps,bool stop) {
            long now=(long)(DateTime.UtcNow-new DateTime(1970,1,1,0,0,0,DateTimeKind.Utc)).TotalMilliseconds;
            StringBuilder text=new StringBuilder("JFGNAV1 "+Level+" "+Generation+" "+nonce+" "+now+" "+(jumps?1:0)+" "+(stop?0:Points.Count)+"\n");
            if(!stop)foreach(HeightPoint p in Points)text.Append(p.X.ToString("R",CultureInfo.InvariantCulture)+" "+p.Y.ToString("R",CultureInfo.InvariantCulture)+" "+p.Z.ToString("R",CultureInfo.InvariantCulture)+"\n");
            string path=Path.Combine(directory,"ai-command.txt"),temporary=path+".tmp";
            File.WriteAllText(temporary,text.ToString(),new UTF8Encoding(false));
            if(File.Exists(path))File.Replace(temporary,path,null);else File.Move(temporary,path);
        }
    }
}
