using System;
using System.Collections.Generic;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.Runtime.Serialization;
using System.Text;
using System.Windows.Forms;

namespace JfgLauncher {
    [DataContract] internal sealed class MapJump {
        [DataMember] public string state = "";
        [DataMember] public bool active = false, calibrated = false;
        [DataMember] public float velocity = 0, gravity = 0, apex = 0, fit_error = 0;
        [DataMember] public long nonce = 0;
        [DataMember] public int completed = 0, flight_update = 0, button = 8;
    }
    internal sealed class JumpLanding {
        internal HeightPoint Point;
        internal float Radius = 12;
        internal int Surface = -1;
        public override string ToString() {
            return "Landing X "+Point.X.ToString("0")+"  Y "+Point.Y.ToString("0")+"  Z "+Point.Z.ToString("0");
        }
    }
    internal sealed class JumpPlan {
        internal HeightPoint Start, Target;
        internal float FootOffset, Duration, Radius, Lift;
        internal uint Level;
        internal long Generation;
        internal readonly List<HeightPoint> Arc = new List<HeightPoint>();
    }

    internal sealed class JumpApproach {
        internal NavigationRoute Walk;
        internal JumpPlan Jump;
    }
    internal static class BoxJumpPlanner {
        internal static JumpApproach Approach(MapSnapshot map,JumpLanding landing) {
            NeedLive(map);
            HeightPoint origin=new HeightPoint(map.Live.player.position);float offset=Offset(map);
            try {return new JumpApproach {Jump=Plan(map,landing)};}catch(InvalidDataException){}
            List<JumpPlan> arcs=new List<JumpPlan>();
            float[] saved=map.Live.player.position;
            try {
                for(int r=56;r<=88;r+=8)for(int a=0;a<24;a++) {
                    double angle=a*Math.PI/12;float x=landing.Point.X+(float)Math.Cos(angle)*r,z=landing.Point.Z+(float)Math.Sin(angle)*r,y;
                    if(!Floor(map.Mesh,x,z,origin.Y-offset,24,out y))continue;
                    HeightPoint start=new HeightPoint(x,y+offset,z);
                    if(!Patch(map,start,24,offset))continue;
                    map.Live.player.position=new float[]{start.X,start.Y,start.Z};
                    try {JumpPlan candidate=Plan(map,landing);if(Horizontal(candidate.Start,candidate.Target)<=candidate.Duration*4.0f)arcs.Add(candidate);}catch(InvalidDataException){}
                }
            }finally {map.Live.player.position=saved;}
            arcs.Sort(delegate(JumpPlan a,JumpPlan b){return Horizontal(origin,a.Start).CompareTo(Horizontal(origin,b.Start));});
            int tried=0;
            foreach(JumpPlan arc in arcs) {
                if(++tried>12)break;
                try {
                    NavigationRoute walk=NavigationRoute.Plan(map,new float[]{arc.Start.X,arc.Start.Y,arc.Start.Z});
                    HeightPoint end=walk.Points[walk.Points.Count-1];
                    if(Math.Abs(end.Y+offset-arc.Start.Y)>4)continue;
                    return new JumpApproach {Walk=walk,Jump=arc};
                }catch(InvalidDataException){}
            }
            throw new InvalidDataException("No supported walking approach and clear jump arc to this landing.");
        }


        [ThreadStatic] private static bool searchingSnapshot;
        [ThreadStatic] private static Dictionary<int,HeightPoint[]> surfaceBounds;
        [ThreadStatic] private static MapGeometry floorMesh;
        [ThreadStatic] private static List<HeightSurface> floorCache;
        private static List<HeightSurface> Floors(MapGeometry mesh) {
            if(floorMesh!=mesh) {floorMesh=mesh;floorCache=new MapLayers(mesh).Floors;}
            return floorCache;
        }
        internal static bool Floor(MapGeometry mesh,float x,float z,float y,float tolerance,out float height) {
            height=0;float best=Single.MaxValue;
            foreach(HeightSurface s in Floors(mesh)) {
                HeightPoint a=s.Points[0],b=s.Points[1],c=s.Points[2];
                float den=(b.Z-c.Z)*(a.X-c.X)+(c.X-b.X)*(a.Z-c.Z);
                if(Math.Abs(den)<.001f)continue;
                float u=((b.Z-c.Z)*(x-c.X)+(c.X-b.X)*(z-c.Z))/den;
                float v=((c.Z-a.Z)*(x-c.X)+(a.X-c.X)*(z-c.Z))/den;
                if(u<-.001f||v<-.001f||u+v>1.001f)continue;
                float value=u*a.Y+v*b.Y+(1-u-v)*c.Y,dy=Math.Abs(value-y);
                if(dy<=tolerance && dy<best){best=dy;height=value;}
            }
            return best<Single.MaxValue;
        }
        internal static float Offset(MapSnapshot map) {
            HeightPoint p=new HeightPoint(map.Live.player.position);float y;
            if(!Floor(map.Mesh,p.X,p.Z,p.Y,60,out y))throw new InvalidDataException("No supported starting floor. Move onto open, level ground.");
            return p.Y-y;
        }
        internal static bool Patch(MapSnapshot map,HeightPoint p,float radius,float offset) {
            for(int i=0;i<9;i++) {
                float angle=(float)(i*Math.PI/4),x=p.X+(i==8?0:(float)Math.Cos(angle)*radius);
                float z=p.Z+(i==8?0:(float)Math.Sin(angle)*radius),height;
                if(!Floor(map.Mesh,x,z,p.Y-offset,3,out height))return false;
                if(NavigationRoute.Obstructed(map.Mesh,new HeightPoint(x,height+4,z),new HeightPoint(x,height+80,z)))return false;
            }
            return true;
        }
        internal static List<JumpLanding> Candidates(MapSnapshot map,bool upperPlatforms=false) {
            NeedLive(map);float offset=Offset(map);
            HeightPoint player=new HeightPoint(map.Live.player.position);
            List<JumpLanding> result=new List<JumpLanding>();

            List<HeightPoint> samples=new List<HeightPoint>();
            foreach(HeightSurface s in Floors(map.Mesh)) {
                // Use slope, not triangle height span: large or gently tilted box
                // tops are valid landing surfaces. The patch check still requires
                // continuous support and small local height variation.
                HeightPoint e0=s.Points[0],e1=s.Points[1],e2=s.Points[2];
                float ux=e1.X-e0.X,uy=e1.Y-e0.Y,uz=e1.Z-e0.Z;
                float vx=e2.X-e0.X,vy=e2.Y-e0.Y,vz=e2.Z-e0.Z;
                float nx=uy*vz-uz*vy,ny=uz*vx-ux*vz,nz=ux*vy-uy*vx;
                if(Math.Abs(ny)<.001f || Math.Sqrt(nx*nx+nz*nz)/Math.Abs(ny)>.125)continue;
                HeightPoint a=s.Points[0],b=s.Points[1],c=s.Points[2];
                samples.Add(new HeightPoint((a.X+b.X+c.X)/3,s.High+offset,(a.Z+b.Z+c.Z)/3));
                // The common diagonal midpoint is the centre of a rectangular
                // box top. Triangle centroids can miss narrow but valid tops.
                for(int edge=0;edge<3;edge++) {
                    HeightPoint u=s.Points[edge],v=s.Points[(edge+1)%3];
                    
                    HeightPoint middle=new HeightPoint((u.X+v.X)/2,s.High+offset,(u.Z+v.Z)/2);
                    samples.Add(middle);
                    float cx=(a.X+b.X+c.X)/3,cz=(a.Z+b.Z+c.Z)/3,dx=cx-middle.X,dz=cz-middle.Z,len=(float)Math.Sqrt(dx*dx+dz*dz);
                    // Sample long platform edges, not just their midpoint or
                    // centroid: a clear entry can lie between obstructions.
                    float ex=v.X-u.X,ez=v.Z-u.Z,edgeLength=(float)Math.Sqrt(ex*ex+ez*ez);
                    if(edgeLength>96 && s.High+offset>player.Y+12) {
                        float ix=-ez/edgeLength,iz=ex/edgeLength;
                        if(ix*dx+iz*dz<0){ix=-ix;iz=-iz;}
                        int sections=Math.Min(12,(int)Math.Ceiling(edgeLength/64));
                        for(int part=1;part<sections;part++)foreach(float inset in new float[]{32,48})
                            samples.Add(new HeightPoint(u.X+ex*part/sections+ix*inset,s.High+offset,u.Z+ez*part/sections+iz*inset));
                    }
                    if(len>1)foreach(float inset in new float[]{32,44,56})samples.Add(new HeightPoint(middle.X+dx/len*inset,middle.Y,middle.Z+dz/len*inset));
                }
            }
            foreach(HeightPoint sample in samples) {
                float support;
                if(!Floor(map.Mesh,sample.X,sample.Z,sample.Y-offset,8,out support))continue;
                HeightPoint p=new HeightPoint(sample.X,support+offset,sample.Z);
                if(p.Y-player.Y<12||p.Y-player.Y>(upperPlatforms?1200:180)||Horizontal(p,player)>(upperPlatforms?1600:650))continue;
                if(!Patch(map,p,28,offset))continue;
                float radius=8;
                for(float candidate=12;candidate<=32;candidate+=4) {
                    if(!Patch(map,p,20+candidate,offset))break;
                    radius=candidate;
                }
                JumpLanding duplicate=null;
                foreach(JumpLanding old in result)if(Horizontal(old.Point,p)<12&&Math.Abs(old.Point.Y-p.Y)<4){duplicate=old;break;}
                if(duplicate==null)result.Add(new JumpLanding{Point=p,Radius=radius});
                else if(radius>duplicate.Radius){duplicate.Point=p;duplicate.Radius=radius;}
            }
            AssignSurfaces(map.Mesh,result);
            result.Sort(delegate(JumpLanding a,JumpLanding b){return Horizontal(a.Point,player).CompareTo(Horizontal(b.Point,player));});
            return result;
        }

        private static string VertexKey(HeightPoint p) {
            return p.X.ToString("R",CultureInfo.InvariantCulture)+","+p.Y.ToString("R",CultureInfo.InvariantCulture)+","+p.Z.ToString("R",CultureInfo.InvariantCulture);
        }
        private static int Root(int[] parent,int x) {while(parent[x]!=x){parent[x]=parent[parent[x]];x=parent[x];}return x;}
        private static void AssignSurfaces(MapGeometry mesh,List<JumpLanding> points) {
            var floors=Floors(mesh);int[] parent=new int[floors.Count];
            var edges=new Dictionary<string,int>();
            for(int i=0;i<floors.Count;i++) {
                parent[i]=i;HeightPoint[] p=floors[i].Points;
                for(int e=0;e<3;e++) {
                    string a=VertexKey(p[e]),b=VertexKey(p[(e+1)%3]);
                    string key=String.CompareOrdinal(a,b)<0?a+"|"+b:b+"|"+a;int other;
                    if(edges.TryGetValue(key,out other))parent[Root(parent,i)]=Root(parent,other);else edges[key]=i;
                }
            }
            surfaceBounds=new Dictionary<int,HeightPoint[]>();
            for(int i=0;i<floors.Count;i++) {
                int root=Root(parent,i);HeightPoint[] box;
                if(!surfaceBounds.TryGetValue(root,out box)) {
                    box=new HeightPoint[]{new HeightPoint(Single.MaxValue,Single.MaxValue,Single.MaxValue),new HeightPoint(Single.MinValue,Single.MinValue,Single.MinValue)};
                    surfaceBounds[root]=box;
                }
                foreach(HeightPoint vertex in floors[i].Points) {
                    box[0]=new HeightPoint(Math.Min(box[0].X,vertex.X),Math.Min(box[0].Y,vertex.Y),Math.Min(box[0].Z,vertex.Z));
                    box[1]=new HeightPoint(Math.Max(box[1].X,vertex.X),Math.Max(box[1].Y,vertex.Y),Math.Max(box[1].Z,vertex.Z));
                }
            }
            foreach(JumpLanding point in points)for(int i=0;i<floors.Count;i++) {
                HeightPoint a=floors[i].Points[0],b=floors[i].Points[1],c=floors[i].Points[2];float x=point.Point.X,z=point.Point.Z;
                float den=(b.Z-c.Z)*(a.X-c.X)+(c.X-b.X)*(a.Z-c.Z);
                if(Math.Abs(den)<.001f)continue;
                float u=((b.Z-c.Z)*(x-c.X)+(c.X-b.X)*(z-c.Z))/den,v=((c.Z-a.Z)*(x-c.X)+(a.X-c.X)*(z-c.Z))/den;
                if(u>=-.001f&&v>=-.001f&&u+v<=1.001f&&Math.Abs(u*a.Y+v*b.Y+(1-u-v)*c.Y-point.Point.Y)<3) {point.Surface=Root(parent,i);break;}
            }
        }
        // An elevated trigger is not a platform. Classify the actual floor
        // before measuring or issuing any jump input.
        internal static bool NeedsPlatformTraversal(MapSnapshot map,HeightPoint goal) {
            if(map==null||map.Mesh==null||map.Live==null||map.Live.player==null||
               map.Live.collision==null||!map.Live.collision.known)return false;
            if(NavigationRoute.HasDirectSurfaceWalk(map,goal))return false;
            var initial=new JumpLanding{Point=new HeightPoint(map.Live.player.position)};
            float y;
            if(!Floor(map.Mesh,goal.X,goal.Z,goal.Y,180,out y))return false;
            var target=new JumpLanding{Point=new HeightPoint(goal.X,y,goal.Z)};
            var points=new List<JumpLanding>{initial,target};AssignSurfaces(map.Mesh,points);
            if(initial.Surface<0||target.Surface<0||initial.Surface==target.Surface)return false;
            // A ramp already leads to the target's elevation: investigate its
            // walking clearance or missing geometry, not a standing jump.
            return target.Point.Y>surfaceBounds[initial.Surface][1].Y+12;
        }
        private static bool PossibleSurfaceStep(int from,int to,MapJump profile) {
            HeightPoint[] a=surfaceBounds[from],b=surfaceBounds[to];
            float rise=b[0].Y-a[1].Y;
            if(rise<8||rise>profile.apex-8)return false;
            float dx=Math.Max(0,Math.Max(b[0].X-a[1].X,a[0].X-b[1].X));
            float dz=Math.Max(0,Math.Max(b[0].Z-a[1].Z,a[0].Z-b[1].Z));
            float disc=profile.velocity*profile.velocity-2*profile.gravity*rise;
            return disc>0&&Math.Sqrt(dx*dx+dz*dz)<=(profile.velocity+Math.Sqrt(disc))/profile.gravity*4.5;
        }
        internal static List<JumpLanding> Sequence(MapSnapshot map,JumpLanding goal,Action<string> trace=null) {
            NeedLive(map);
            if(map.Live.box_jump==null||!map.Live.box_jump.calibrated)throw new InvalidDataException("Calibrate a standing jump first.");
            var all=Candidates(map,true);all.Add(goal);
            var initial=new JumpLanding{Point=new HeightPoint(map.Live.player.position)};all.Add(initial);AssignSurfaces(map.Mesh,all);
            if(initial.Surface>=0&&initial.Surface==goal.Surface)return new List<JumpLanding>();
            if(goal.Surface<0)throw new InvalidDataException("Goal has no supported platform.");
            var groups=new Dictionary<int,List<JumpLanding>>();
            foreach(JumpLanding c in all) {
                if(c.Surface<0||c.Point.Y>goal.Point.Y+3)continue;
                List<JumpLanding> group;if(!groups.TryGetValue(c.Surface,out group)){group=new List<JumpLanding>();groups[c.Surface]=group;}
                group.Add(c);
            }
            // Keep alternative safe entry points on the goal platform; walking to
            // an item is a separate action after the platform landing is confirmed.
            // Bounds only reject impossible branches. They never authorize a
            // jump; every retained link still needs its complete clearance check.
            var useful=new HashSet<int>{goal.Surface};bool added=true;
            while(added) {
                added=false;
                foreach(int from in groups.Keys)if(!useful.Contains(from))
                    foreach(int to in new List<int>(useful))if(PossibleSurfaceStep(from,to,map.Live.box_jump)){useful.Add(from);added=true;break;}
            }
            var hops=new Dictionary<int,int>{{goal.Surface,0}};
            bool changed=true;
            while(changed) {
                changed=false;
                foreach(int from in useful)foreach(int to in new List<int>(hops.Keys))
                    if(PossibleSurfaceStep(from,to,map.Live.box_jump)&&(!hops.ContainsKey(from)||hops[from]>hops[to]+1)) {hops[from]=hops[to]+1;changed=true;}
            }
            float[] saved=map.Live.player.position;bool previousSearch=searchingSnapshot;
            var watch=System.Diagnostics.Stopwatch.StartNew();int expansions=0;searchingSnapshot=true;
            try {
                var route=SearchPlatforms(map,-2,new HeightPoint(saved),goal,groups,hops,watch,0,ref expansions,trace);
                if(route!=null)return route;
            }finally {map.Live.player.position=saved;searchingSnapshot=previousSearch;}
            throw new InvalidDataException("No verified ascending platform sequence found within the search limit. Try a nearer platform.");
        }
        private static List<JumpLanding> SearchPlatforms(MapSnapshot map,int surface,HeightPoint position,JumpLanding goal,
            Dictionary<int,List<JumpLanding>> groups,Dictionary<int,int> hops,System.Diagnostics.Stopwatch watch,int depth,ref int expansions,Action<string> trace) {
            if(surface==goal.Surface)return new List<JumpLanding>();
            if(depth>=8||++expansions>32||watch.ElapsedMilliseconds>=12000)return null;
            var ordered=new List<int>(hops.Keys);ordered.Sort(delegate(int a,int b){return hops[a].CompareTo(hops[b]);});
            foreach(int next in ordered) {
                if(next==surface||(surface>=0&&!PossibleSurfaceStep(surface,next,map.Live.box_jump)))continue;
                var candidates=new List<JumpLanding>(groups[next]);
                candidates.Sort(delegate(JumpLanding a,JumpLanding b){return Horizontal(position,a.Point).CompareTo(Horizontal(position,b.Point));});
                int tried=0;var deferred=new List<JumpLanding>();
                foreach(JumpLanding candidate in candidates) {
                    float rise=candidate.Point.Y-position.Y;
                    if(rise<12||rise>map.Live.box_jump.apex-8||Horizontal(position,candidate.Point)>800)continue;
                    if(watch.ElapsedMilliseconds>=12000)return null;
                    if(++tried>8)break;
                    map.Live.player.position=new float[]{position.X,position.Y,position.Z};
                    try {
                        var edge=Approach(map,candidate);
                        float length=Math.Max(1,Horizontal(edge.Jump.Start,edge.Jump.Target));
                        HeightPoint forward=new HeightPoint(candidate.Point.X+(candidate.Point.X-edge.Jump.Start.X)/length*16,
                            candidate.Point.Y,candidate.Point.Z+(candidate.Point.Z-edge.Jump.Start.Z)/length*16);
                        if(!Patch(map,forward,20,edge.Jump.FootOffset)){deferred.Add(candidate);continue;}
                        if(trace!=null)trace("EDGE "+surface+" -> "+next+" at "+candidate.Point.X+","+candidate.Point.Y+","+candidate.Point.Z);
                        var rest=SearchPlatforms(map,next,candidate.Point,goal,groups,hops,watch,depth+1,ref expansions,trace);
                        if(rest!=null){rest.Insert(0,candidate);return rest;}
                    }catch(InvalidDataException error){if(trace!=null)trace("REJECT "+next+": "+error.Message);}
                }
                // Keep small, necessary steps available, but prefer landings
                // with room for residual forward momentum whenever one exists.
                foreach(JumpLanding candidate in deferred) {
                    if(watch.ElapsedMilliseconds>=12000)return null;
                    var rest=SearchPlatforms(map,next,candidate.Point,goal,groups,hops,watch,depth+1,ref expansions,trace);
                    if(rest!=null){rest.Insert(0,candidate);return rest;}
                }
            }
            return null;
        }
        internal static float Horizontal(HeightPoint a,HeightPoint b) {float x=a.X-b.X,z=a.Z-b.Z;return (float)Math.Sqrt(x*x+z*z);}
        internal static void NeedLive(MapSnapshot map) {
            if(map==null||(!searchingSnapshot&&!map.IsLive)||!map.Live.clearing_active||map.Live.scripted_camera||map.Live.player==null)
                throw new InvalidDataException("Enter active gameplay before a jump trial.");
            NavigationCollision.Require(map.Live);
        }
        internal static JumpPlan Plan(MapSnapshot map,JumpLanding landing) {
            NeedLive(map);MapJump profile=map.Live.box_jump;
            if(profile==null||!profile.calibrated||profile.gravity<=0||profile.velocity<=0||
                Single.IsNaN(profile.gravity)||Single.IsNaN(profile.velocity)||Single.IsInfinity(profile.gravity)||Single.IsInfinity(profile.velocity)||profile.gravity>20||profile.velocity>200||Single.IsNaN(profile.apex)||Single.IsInfinity(profile.apex)||Single.IsNaN(profile.fit_error)||profile.fit_error>8)
                throw new InvalidDataException("Calibrate a standing jump in open space first.");
            JumpPlan plan=new JumpPlan {Start=new HeightPoint(map.Live.player.position),Target=landing.Point,Radius=landing.Radius,
                Level=map.Live.level,Generation=map.Live.generation,FootOffset=Offset(map)};
            if(!Patch(map,plan.Target,20+plan.Radius,plan.FootOffset))
                throw new InvalidDataException("Landing patch lacks body clearance or continuous support.");
            float rise=plan.Target.Y-plan.Start.Y,disc=profile.velocity*profile.velocity-2*profile.gravity*rise;
            
            if(rise>profile.apex-8)
                throw new InvalidDataException("Landing is above the measured jump height. Use an intermediate platform.");
            if(rise < -160||disc<=0)throw new InvalidDataException("Landing is outside the measured jump height.");
            plan.Duration=(profile.velocity+(float)Math.Sqrt(disc))/profile.gravity;
            
            if(plan.Duration<4||plan.Duration>160)
                throw new InvalidDataException("Landing is outside the measured flight duration.");
            // Close boxes need a vertical takeoff before forward motion; a
            // straight interpolation would sweep the body through their side.
            InvalidDataException last=null;
            for(int delay=0;delay<=Math.Floor(profile.velocity/profile.gravity);delay++) {
                float travel=plan.Duration-delay;
                if(travel<4||Horizontal(plan.Start,plan.Target)>travel*4.5f)continue;
                plan.Lift=profile.velocity*delay-.5f*profile.gravity*delay*delay;
                if(plan.Lift>profile.apex-4)continue;
                plan.Arc.Clear();int count=(int)Math.Ceiling(plan.Duration*2);
                for(int i=0;i<=count;i++) {
                    float t=plan.Duration*i/count,u=Math.Max(0,(t-delay)/travel);
                    plan.Arc.Add(new HeightPoint(plan.Start.X+(plan.Target.X-plan.Start.X)*u,
                        plan.Start.Y+profile.velocity*t-.5f*profile.gravity*t*t,
                        plan.Start.Z+(plan.Target.Z-plan.Start.Z)*u));
                }
                try {ValidateArc(map,plan);return plan;}catch(InvalidDataException error){last=error;}
            }
            throw last??new InvalidDataException("Landing is outside the conservative jump range. Walk closer first.");
        }
        internal static void ValidateArc(MapSnapshot map,JumpPlan plan) {
            NavigationCollision.Require(map.Live);
            if(map.Live.level!=plan.Level||map.Live.generation!=plan.Generation)throw new InvalidDataException("Room changed; plan again.");
            for(int i=1;i<plan.Arc.Count;i++) {
                HeightPoint a=plan.Arc[i-1],b=plan.Arc[i];
                HeightPoint fa=new HeightPoint(a.X,a.Y-plan.FootOffset,a.Z),fb=new HeightPoint(b.X,b.Y-plan.FootOffset,b.Z);
                if(NavigationCollision.Blocking(map.Live,fa,fb)!=null)throw new InvalidDataException("Jump arc meets an entity collision box.");
                
                float bodyRadius=20;
                foreach(float y in new float[]{4,40,80})foreach(HeightPoint shift in new HeightPoint[]{new HeightPoint(0,y,0),new HeightPoint(bodyRadius,y,0),new HeightPoint(-bodyRadius,y,0),new HeightPoint(0,y,bodyRadius),new HeightPoint(0,y,-bodyRadius)})
                    if(NavigationRoute.Obstructed(map.Mesh,new HeightPoint(fa.X+shift.X,fa.Y+shift.Y,fa.Z+shift.Z),new HeightPoint(fb.X+shift.X,fb.Y+shift.Y,fb.Z+shift.Z)))
                        throw new InvalidDataException("Jump arc meets terrain, box side or ceiling.");
                if(NavigationRoute.Obstructed(map.Mesh,new HeightPoint(fb.X,fb.Y+4,fb.Z),new HeightPoint(fb.X,fb.Y+80,fb.Z)))
                    throw new InvalidDataException("Jump body does not fit under overhead geometry.");
            }
        }

        internal static bool SupportedLanding(MapSnapshot map,JumpPlan plan) {
            if(map==null||plan==null||!map.IsLive||map.Live.level!=plan.Level||map.Live.generation!=plan.Generation||
                !map.Live.clearing_active||map.Live.player==null||map.Live.box_jump==null||map.Live.box_jump.active)return false;
            string state=map.Live.box_jump.state;
            if(state!="jump_landed"&&state!="jump_missed_landing")return false;
            HeightPoint actual=new HeightPoint(map.Live.player.position);
            float distance=Horizontal(actual,plan.Target);
            if(distance>64||Math.Abs(actual.Y-plan.Target.Y)>3)return false;
            // Verify a connected area of support at the requested elevation.
            // An overshoot onto another storey or across a gap never counts.
            for(int i=0;i<=16;i++) {
                HeightPoint point=HeightPoint.Lerp(plan.Target,actual,i/16.0f);
                if(!Patch(map,point,20,plan.FootOffset))return false;
                HeightPoint feet=new HeightPoint(point.X,point.Y-plan.FootOffset,point.Z);
                if(NavigationCollision.Blocking(map.Live,feet,feet)!=null)return false;
            }
            return true;
        }
        internal static void Send(string directory,MapLive live,long nonce,int mode,HeightPoint target,float radius,int button=8,float lift=0) {
            long now=NavigationExplorer.Clock;
            string text=String.Format(CultureInfo.InvariantCulture,"JFGJUMP2 {0} {1} {2} {3} {4} {5:R} {6:R} {7:R} {8:R} {9} {10:R}\n",
                live.level,live.generation,nonce,now,mode,target.X,target.Y,target.Z,radius,button,lift);
            string path=Path.Combine(directory,"ai-command.txt"),temp=path+".tmp";
            File.WriteAllText(temp,text,new UTF8Encoding(false));
            
            for(int retry=0;;retry++) {
                try {if(File.Exists(path))File.Replace(temp,path,null);else File.Move(temp,path);break;}
                catch(IOException) {if(retry>=5)throw;System.Threading.Thread.Sleep(10);}
                catch(UnauthorizedAccessException) {if(retry>=5)throw;System.Threading.Thread.Sleep(10);}
            }
        }
    }
    internal sealed class JumpArcPanel : Panel {
        internal JumpPlan Plan;
        internal readonly List<HeightPoint> Observed=new List<HeightPoint>();
        internal JumpArcPanel(){DoubleBuffered=true;BackColor=Color.FromArgb(16,24,34);Dock=DockStyle.Fill;}
        protected override void OnPaint(PaintEventArgs e) {
            base.OnPaint(e);Graphics g=e.Graphics;
            g.DrawString("Side view: yellow predicted arc; cyan observed motion",Font,Brushes.White,12,10);
            if(Plan==null)return;
            float distance=Math.Max(80,BoxJumpPlanner.Horizontal(Plan.Start,Plan.Target)),high=Plan.Start.Y+40,low=Math.Min(Plan.Start.Y,Plan.Target.Y)-20;
            foreach(HeightPoint p in Plan.Arc)high=Math.Max(high,p.Y+30);
            foreach(HeightPoint p in Observed){high=Math.Max(high,p.Y+30);low=Math.Min(low,p.Y-20);}
            high=Math.Max(high,Plan.Target.Y+30);
            Func<HeightPoint,PointF> point=delegate(HeightPoint p) {
                float dx=Plan.Target.X-Plan.Start.X,dz=Plan.Target.Z-Plan.Start.Z,len=Math.Max(1,(float)Math.Sqrt(dx*dx+dz*dz));
                float x=((p.X-Plan.Start.X)*dx+(p.Z-Plan.Start.Z)*dz)/len;
                return new PointF(30+x/distance*(Width-60),Height-35-(p.Y-low)/(high-low)*(Height-80));
            };
            using(Pen line=new Pen(Color.Gold,2))for(int i=1;i<Plan.Arc.Count;i++)g.DrawLine(line,point(Plan.Arc[i-1]),point(Plan.Arc[i]));
            using(Pen line=new Pen(Color.Cyan,2))for(int i=1;i<Observed.Count;i++)g.DrawLine(line,point(Observed[i-1]),point(Observed[i]));
            
            PointF end=point(Plan.Target);g.FillEllipse(Brushes.Lime,end.X-5,end.Y-5,10,10);
            g.DrawString("Landing Y "+Plan.Target.Y.ToString("0.0"),Font,Brushes.Lime,end.X-90,end.Y+8);
        }
    }
    internal sealed class BoxJumpWindow : Form {
        private readonly string directory;
        private readonly Timer timer=new Timer();
        private readonly ListBox targets=new ListBox {Dock=DockStyle.Left,Width=290};
        private readonly Label status=new Label {Dock=DockStyle.Bottom,Height=76,Padding=new Padding(8)};
        private readonly JumpArcPanel arc=new JumpArcPanel();
        private readonly ComboBox controls=new ComboBox {DropDownStyle=ComboBoxStyle.DropDownList,Width=145};
        private int jumpButton=8;
        private List<JumpLanding> sequence;private int sequenceIndex;
        private MapSnapshot snapshot;private MapGeometry cached;private JumpPlan plan;
        private JumpApproach approach;private HeightPoint previewOrigin;private long settleUntil;private int approachRetries;
        private long nonce=NavigationExplorer.Clock,lastUpdate=-1,started;
        private int planningVersion;
        private bool running;private int mode;private HeightPoint commandTarget;private uint room;private long generation;
        internal BoxJumpWindow(string path) {
            directory=path;Text="Box jumping prototype";ClientSize=new Size(980,600);
            Controls.Add(arc);Controls.Add(targets);Controls.Add(status);
            FlowLayoutPanel bar=new FlowLayoutPanel {Dock=DockStyle.Top,Height=78};
            Button calibrate=new Button {Text="1. Calibrate jump",AutoSize=true},scan=new Button {Text="2. Find landings",AutoSize=true},
                preview=new Button {Text="3. Plan platform route",AutoSize=true},run=new Button {Text="4. Run route",AutoSize=true},stop=new Button {Text="Stop",AutoSize=true};
            controls.Items.AddRange(new object[]{"Normal: C-Up","Expert: A"});controls.SelectedIndex=0;
            controls.SelectedIndexChanged+=delegate {Stop();sequence=null;plan=null;status.Text="Calibrate again after changing controls.";};
            bar.Controls.AddRange(new Control[]{controls,calibrate,scan,preview,run,stop});
            bar.SetFlowBreak(stop,true);bar.Controls.Add(new Label {Text="Prototype: checked approaches and ascending box jumps. Movement input or Esc cancels. Use copied saves.",AutoSize=true});
            Controls.Add(bar);
            calibrate.Click+=delegate {Action(delegate {
                BoxJumpPlanner.NeedLive(snapshot);
                Stop();sequence=null;plan=null;arc.Plan=null;Start(0,new HeightPoint(snapshot.Live.player.position));
            });};
            scan.Click+=delegate {Action(delegate {
                Stop();targets.Items.Clear();foreach(JumpLanding p in BoxJumpPlanner.Candidates(snapshot,true))targets.Items.Add(p);
                if(targets.Items.Count>0)targets.SelectedIndex=0;
                status.Text=targets.Items.Count+" supported landing candidates. Select one and preview.";
            });};
            preview.Click+=delegate {Action(delegate {
                Stop();JumpLanding selected=targets.SelectedItem as JumpLanding;
                if(selected==null)throw new InvalidDataException("Find and select a landing first.");
                BoxJumpPlanner.NeedLive(snapshot);
                MapSnapshot planningMap=snapshot;
                HeightPoint origin=new HeightPoint(planningMap.Live.player.position);
                int version=++planningVersion;plan=null;sequence=null;arc.Plan=null;arc.Invalidate();
                status.Text="Searching supported platform links...";preview.Enabled=false;
                var worker=new System.ComponentModel.BackgroundWorker();
                worker.DoWork+=delegate(object sender,System.ComponentModel.DoWorkEventArgs e) {e.Result=BoxJumpPlanner.Sequence(planningMap,selected);};
                worker.RunWorkerCompleted+=delegate(object sender,System.ComponentModel.RunWorkerCompletedEventArgs e) {
                    worker.Dispose();if(IsDisposed||Disposing)return;preview.Enabled=true;
                    if(version!=planningVersion)return;
                    if(e.Error!=null){status.Text=e.Error.Message;return;}
                    Action(delegate {
                        BoxJumpPlanner.NeedLive(snapshot);
                        HeightPoint current=new HeightPoint(snapshot.Live.player.position);
                        if(snapshot.Live.level!=planningMap.Live.level||snapshot.Live.generation!=planningMap.Live.generation||
                            BoxJumpPlanner.Horizontal(current,origin)>4||Math.Abs(current.Y-origin.Y)>3)
                            throw new InvalidDataException("Player or room changed; preview again.");
                        sequence=(List<JumpLanding>)e.Result;
                        if(sequence.Count==0)throw new InvalidDataException("Already on the selected platform.");
                        previewOrigin=current;sequenceIndex=0;approach=BoxJumpPlanner.Approach(snapshot,sequence[0]);
                        plan=approach.Jump;arc.Plan=plan;arc.Observed.Clear();arc.Invalidate();
                        status.Text=sequence.Count+" jumps planned. "+(approach.Walk==null?"Jump from here. ":"Walk to takeoff, then jump. ")+"The route ends on the selected platform; item interaction is separate.";
                    });
                };
                worker.RunWorkerAsync();
            });};
            run.Click+=delegate {Action(delegate {
                if(plan==null)throw new InvalidDataException("Preview a jump first.");
                BoxJumpPlanner.NeedLive(snapshot);
                if(BoxJumpPlanner.Horizontal(new HeightPoint(snapshot.Live.player.position),previewOrigin)>4 ||
                    Math.Abs(snapshot.Live.player.position[1]-previewOrigin.Y)>3)throw new InvalidDataException("Player moved; preview again.");
                BoxJumpPlanner.ValidateArc(snapshot,plan);
                approachRetries=0;if(approach.Walk==null)Start(1,plan.Target);else StartWalk();
            });};
            stop.Click+=delegate {Stop();status.Text="Jump stopped.";};
            KeyPreview=true;KeyDown+=delegate(object sender,KeyEventArgs e){if(e.KeyCode==Keys.Escape)Stop();};
            FormClosing+=delegate {Stop();};FormClosed+=delegate {timer.Stop();timer.Dispose();};
            timer.Interval=100;timer.Tick+=delegate {RefreshLive();};RefreshLive();timer.Start();
        }
        private void Action(System.Action action) {
            try {RefreshLive();action();}
            catch(Exception error) {
                if(!(error is IOException)&&!(error is InvalidDataException)&&!(error is UnauthorizedAccessException)&&!(error is SerializationException))throw;
                Stop();status.Text=error.Message;
            }
        }

        private void StartWalk() {
            BoxJumpPlanner.NeedLive(snapshot);
            string problem=approach.Walk.CheckRemaining(snapshot,0);
            if(problem!=null)throw new InvalidDataException(problem);
            jumpButton=controls.SelectedIndex==0?8:32768;
            if(snapshot.Live.box_jump==null||snapshot.Live.box_jump.button!=jumpButton||!snapshot.Live.box_jump.calibrated)
                throw new InvalidDataException("Calibrate with the selected controls first.");
            room=snapshot.Live.level;generation=snapshot.Live.generation;mode=2;settleUntil=0;
            nonce=Math.Max(nonce+1,NavigationExplorer.Clock);started=NavigationExplorer.Clock;running=true;
            approach.Walk.Send(directory,nonce,false,false);status.Text="Walking to takeoff...";
        }
        private void Start(int value,HeightPoint target) {
            BoxJumpPlanner.NeedLive(snapshot);jumpButton=controls.SelectedIndex==0?8:32768;
            if(value==1 && (snapshot.Live.box_jump==null || snapshot.Live.box_jump.button!=jumpButton))throw new InvalidDataException("Calibrate with the selected controls first.");
            mode=value;commandTarget=target;room=snapshot.Live.level;generation=snapshot.Live.generation;
            nonce=Math.Max(nonce+1,NavigationExplorer.Clock);started=NavigationExplorer.Clock;running=true;arc.Observed.Clear();
            BoxJumpPlanner.Send(directory,snapshot.Live,nonce,mode,target,mode==1?plan.Radius:12,jumpButton,mode==1?plan.Lift:0);status.Text="Starting jump trial...";
        }
        private void Stop() {
            ++planningVersion;
            if(!running)return;running=false;
            try {new NavigationRoute {Level=room,Generation=generation}.Send(directory,++nonce,false,true);}catch(IOException){}catch(UnauthorizedAccessException){}
        }
        private void RefreshLive() {
            try {
                snapshot=MapSnapshot.Load(directory,cached);cached=snapshot.Mesh;
                MapJump jump=snapshot.Live.box_jump;
                if(!running)return;
                if(!snapshot.IsLive||!snapshot.Live.clearing_active||snapshot.Live.level!=room||snapshot.Live.generation!=generation) {
                    Stop();status.Text="Jump stopped: gameplay or room changed.";return;
                }

                if(mode==2) {
                    if(NavigationExplorer.Clock-started>45000){Stop();status.Text="Walking approach timed out.";return;}
                    if(settleUntil!=0) {
                        if(NavigationExplorer.Clock<settleUntil)return;
                        
                        JumpLanding landing=new JumpLanding{Point=plan.Target,Radius=plan.Radius};
                        try {plan=BoxJumpPlanner.Plan(snapshot,landing);}
                        catch(InvalidDataException) {
                            if(++approachRetries>2)throw;
                            approach=BoxJumpPlanner.Approach(snapshot,landing);plan=approach.Jump;
                            if(approach.Walk!=null){StartWalk();status.Text="Correcting settled takeoff position ("+approachRetries+"/2)...";return;}
                        }
                        arc.Plan=plan;Start(1,plan.Target);return;
                    }
                    MapAi walking=snapshot.Live.navigation_ai;
                    if(walking!=null&&walking.nonce==nonce&&!walking.active) {
                        if(walking.state!="approach_complete"){Stop();status.Text="Approach stopped: "+walking.state;return;}
                        settleUntil=NavigationExplorer.Clock+800;status.Text="Waiting for takeoff motion to settle...";return;
                    }
                    string blocked=approach.Walk.CheckRemaining(snapshot,walking!=null&&walking.nonce==nonce?walking.waypoint:0);
                    if(blocked!=null){Stop();status.Text=blocked;return;}
                    approach.Walk.Send(directory,nonce,false,false);status.Text="Walking to takeoff...";return;
                }
                if(jump!=null&&jump.nonce==nonce&&!jump.active) {
                    running=false;
                    if(mode==1 && BoxJumpPlanner.SupportedLanding(snapshot,plan)){
                        if(sequence!=null && ++sequenceIndex<sequence.Count) {
                            approach=BoxJumpPlanner.Approach(snapshot,sequence[sequenceIndex]);plan=approach.Jump;arc.Plan=plan;approachRetries=0;
                            if(approach.Walk==null)Start(1,plan.Target);else StartWalk();
                            status.Text="Platform "+sequenceIndex+" confirmed; continuing to "+(sequenceIndex+1)+"/"+sequence.Count+".";return;
                        }
                        status.Text="Route complete; supported landing confirmed.";return;
                    }status.Text=jump.state.Replace('_',' ')+" | apex "+jump.apex.ToString("0.0")+" | fit error "+jump.fit_error.ToString("0.00");
                    return;
                }
                if(NavigationExplorer.Clock-started>12000){Stop();status.Text="Jump timed out.";return;}
                if(mode==1 && plan!=null)BoxJumpPlanner.ValidateArc(snapshot,plan);
                BoxJumpPlanner.Send(directory,snapshot.Live,nonce,mode,commandTarget,mode==1?plan.Radius:12,jumpButton,mode==1?plan.Lift:0);
                if(snapshot.Live.update!=lastUpdate) {
                    lastUpdate=snapshot.Live.update;if(arc.Observed.Count<300)arc.Observed.Add(new HeightPoint(snapshot.Live.player.position));arc.Invalidate();
                }
                status.Text=jump==null?"Waiting for native jump support":jump.state.Replace('_',' ')+" | apex "+jump.apex.ToString("0.0")+" | gravity/update² "+jump.gravity.ToString("0.00");
                if(snapshot.Live.player.motion!=null&&snapshot.Live.player.motion.known)
                    status.Text+=" | movement "+snapshot.Live.player.motion.state_id+" | animation "+snapshot.Live.player.motion.animation_id;
            } catch(Exception error) {
                if(!(error is IOException)&&!(error is InvalidDataException)&&!(error is UnauthorizedAccessException)&&!(error is SerializationException))throw;
                Stop();status.Text=error.Message;
            }
        }
    }
}
