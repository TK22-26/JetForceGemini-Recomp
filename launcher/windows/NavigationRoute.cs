using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;

namespace JfgLauncher {
    // Surface connectivity only: dynamic doors, clearance and gap jumps remain unproved.
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
            List<HeightSurface> floors=new MapLayers(snapshot.Mesh).Floors;
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
            reverse.Reverse();route.Points.AddRange(reverse);route.Points.Add(endPoint);return route;
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
