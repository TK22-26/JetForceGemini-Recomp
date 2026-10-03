using System;
using System.IO;
using System.Drawing;
using System.Collections.Generic;
using System.Runtime.Serialization.Json;
using System.Windows.Forms;

namespace JfgLauncher {
    internal static class NavigationCollisionTests {
        private static int checks;
        private static void Check(bool condition,string message) {if(!condition)throw new Exception("Collision: "+message);++checks;}
        private static void Reject(Action action,string message) {bool failed=false;try{action();}catch(InvalidDataException){failed=true;}Check(failed,message);}
        internal static MapSnapshot Fixture() {
            return new MapSnapshot {
                Mesh=new MapGeometry {schema=1,level=27,generation=1,vertices=new float[][] {new float[]{-1000,0,-1000},new float[]{1000,0,-1000},new float[]{-1000,0,1000},new float[]{1000,0,1000}},
                    triangles=new MapFace[] {new MapFace {v=new int[]{0,2,1},normal=new float[]{0,1,0}},new MapFace {v=new int[]{1,2,3},normal=new float[]{0,1,0}}}},
                Live=new MapLive {schema=1,level=27,generation=1,mesh_ready=true,clearing_active=true,timestamp_ms=NavigationExplorer.Clock,update=1,
                    player=new MapPlayer {address=0x80100000,position=new float[]{0,0,0}},exits=new MapMarker[0],markers=new MapMarker[0],npcs=new MapMarker[0],
                    navigation_ai=new MapAi(),actors=new MapActor[0],collision=MapCollision.Empty()}
            };
        }
        private static void Put(MapSnapshot map,float bottom,float top,bool enabled) {
            map.Live.actors=new MapActor[]{new MapActor {address=0x80102000,name="Test obstacle",behavior=54,position=new float[]{230,bottom,0}}};
            map.Live.collision.models=new MapCollisionModel[]{new MapCollisionModel {address=0x80102000,enabled=enabled,lower=new float[]{200,bottom,-40},upper=new float[]{260,top,40}}};
        }
        private static void Write(string directory,MapSnapshot map) {
            Directory.CreateDirectory(directory);map.Live.timestamp_ms=NavigationExplorer.Clock;
            using(FileStream file=File.Create(Path.Combine(directory,"mesh.json")))new DataContractJsonSerializer(typeof(MapGeometry)).WriteObject(file,map.Mesh);
            using(FileStream file=File.Create(Path.Combine(directory,"live.json")))new DataContractJsonSerializer(typeof(MapLive)).WriteObject(file,map.Live);
        }
        private static Button Button(Control parent,string label) {
            foreach(Control c in parent.Controls){if(c is Button && c.Text==label)return (Button)c;Button b=Button(c,label);if(b!=null)return b;}return null;
        }
        internal static int Run(string root) {
            checks=0;
            MapSnapshot speedMap=Fixture();
            NavigationRoute speedRoute=NavigationRoute.Plan(speedMap,new float[]{500,0,0});
            Check(speedRoute.CheckRemaining(speedMap,0)==null && speedRoute.RunningWaypoint==0,"open straight segment cannot run");
            Put(speedMap,0,81,true);
            speedMap.Live.collision.models[0].lower[2]=30;speedMap.Live.collision.models[0].upper[2]=100;
            Check(speedRoute.CheckRemaining(speedMap,0)==null && speedRoute.RunningWaypoint==-1,"running allowed close to model");
            speedMap.Live.collision.models[0].lower[1]=120;speedMap.Live.collision.models[0].upper[1]=180;
            Check(speedRoute.CheckRemaining(speedMap,0)==null && speedRoute.RunningWaypoint==0,"upper story incorrectly prevents running");
            speedMap.Live.timestamp_ms=NavigationExplorer.Clock-5000;
            Check(speedRoute.CheckRemaining(speedMap,0)==null && speedRoute.RunningWaypoint==-1,"stale map enables running");
            speedMap=Fixture();speedMap.Live.scripted_camera=true;
            Check(speedRoute.CheckRemaining(speedMap,0)==null && speedRoute.RunningWaypoint==-1,"scripted camera enables running");
            speedMap=Fixture();
            foreach(float[] vertex in speedMap.Mesh.vertices)vertex[2]=vertex[2]<0?-25:25;
            Check(speedRoute.CheckRemaining(speedMap,0)==null && speedRoute.RunningWaypoint==-1,"narrow floor enables running");
            speedMap=Fixture();
            NavigationRoute dense=new NavigationRoute {Level=27,Generation=1};
            for(int x=20;x<=300;x+=20)dense.Points.Add(new HeightPoint(x,0,0));
            Check(dense.CheckRemaining(speedMap,0)==null && dense.RunningWaypoint==0 && dense.RunningThrough>=10,
                "short waypoints interrupt running clearance");
            MapSnapshot map=Fixture();Put(map,0,81,true);NavigationCollision.Require(map.Live);
            HeightPoint start=new HeightPoint(0,0,0),end=new HeightPoint(500,0,0);
            Check(NavigationCollision.Blocking(map.Live,start,end)!=null,"body moved through obstacle");
            Check(NavigationCollision.Blocking(map.Live,new HeightPoint(0,0,59),new HeightPoint(500,0,59))!=null,"player radius ignored");
            Check(NavigationCollision.Blocking(map.Live,new HeightPoint(0,0,61),new HeightPoint(500,0,61))==null,"clear lateral path blocked");
            Put(map,200,260,true);Check(NavigationCollision.Blocking(map.Live,start,end)==null,"upper story blocked lower route");
            Put(map,-100,-10,true);Check(NavigationCollision.Blocking(map.Live,start,end)==null,"lower story blocked upper route");
            Put(map,79,120,true);Check(NavigationCollision.Blocking(map.Live,start,end)!=null,"overhead body clearance ignored");
            Put(map,0,81,false);Check(NavigationCollision.Blocking(map.Live,start,end)==null,"disabled polygon model blocked route");
            Put(map,0,81,true);map.Live.player.address=map.Live.collision.models[0].address;
            Check(NavigationCollision.Blocking(map.Live,start,end)==null,"player collided with own model");map.Live.player.address=0x80100000;
            NavigationRoute route=NavigationRoute.Plan(map,new float[]{500,0,0});
            Check(route.Points.Count>1,"obstacle did not create detour");
            Check(NavigationCollision.CheckRoute(map.Live,route,0)==null,"emitted detour crosses obstacle");
            var floors=new MapLayers(map.Mesh).Floors;HeightPoint previous=start;
            foreach(HeightPoint p in route.Points){Check(NavigationRoute.ClearWalk(map,floors,previous,p),"emitted unchecked walking segment");previous=p;}
            Check(Math.Abs(previous.X-500)<.01 && Math.Abs(previous.Z)<.01,"detour missed destination");
            MapCollisionModel model=map.Live.collision.models[0];
            Check(model.Overlaps(-5,5) && model.Overlaps(60,90) && !model.Overlaps(100,150),"slice uses actor origin instead of full height");
            Check(NavigationCollision.Details(map.Live,map.Live.actors[0]).Contains("Height: 81"),"inspector lacks measured height");
            model.upper[0]=100;Reject(delegate{NavigationCollision.Require(map.Live);},"reversed bounds accepted");model.upper[0]=260;
            model.lower[1]=Single.NaN;Reject(delegate{NavigationCollision.Require(map.Live);},"nonfinite bounds accepted");model.lower[1]=0;
            map.Live.collision.models=new MapCollisionModel[]{model,model};Reject(delegate{NavigationCollision.Require(map.Live);},"duplicate entity accepted");map.Live.collision.models=new MapCollisionModel[]{model};
            map.Live.actors=new MapActor[0];Reject(delegate{NavigationCollision.Require(map.Live);},"stale entity bounds accepted");Put(map,0,81,true);
            map.Live.collision.known=false;Reject(delegate{NavigationRoute.Plan(map,new float[]{500,0,0});},"unknown collision routed");map.Live.collision.known=true;
            map.Live.player.position=new float[]{230,0,0};Reject(delegate{NavigationRoute.Plan(map,new float[]{500,0,0});},"started inside blocking box");map.Live.player.position=new float[]{0,0,0};
            Reject(delegate{NavigationRoute.Plan(map,new float[]{230,0,0});},"target inside box accepted");
            Put(map,100,160,true);Check(NavigationRoute.Plan(map,new float[]{500,0,0}).Points.Count==1,"overhead floor forced detour without body overlap");
            Put(map,0,81,false);Check(NavigationRoute.Plan(map,new float[]{500,0,0}).Points.Count==1,"disabled model forced detour");
            MapSnapshot terrain=Fixture();
            terrain.Mesh.vertices=new float[][] {new float[]{-1000,0,-1000},new float[]{1000,0,-1000},new float[]{-1000,0,1000},new float[]{1000,0,1000},new float[]{200,0,-100},new float[]{200,200,-100},new float[]{200,0,100},new float[]{200,200,100}};
            terrain.Mesh.triangles=new MapFace[]{new MapFace{v=new int[]{0,2,1},normal=new float[]{0,1,0}},new MapFace{v=new int[]{1,2,3},normal=new float[]{0,1,0}},new MapFace{v=new int[]{4,5,6}},new MapFace{v=new int[]{5,7,6}}};
            Check(!NavigationRoute.ClearWalk(terrain,new MapLayers(terrain.Mesh).Floors,start,end),"unsmoothed segment crossed static wall");
            terrain.Mesh.vertices[4]=new float[]{150,50,-100};terrain.Mesh.vertices[5]=new float[]{300,50,-100};terrain.Mesh.vertices[6]=new float[]{150,50,100};terrain.Mesh.vertices[7]=new float[]{300,50,100};
            Check(!NavigationRoute.ClearWalk(terrain,new MapLayers(terrain.Mesh).Floors,start,end),"low ceiling did not block standing body");
            terrain=Fixture();terrain.Mesh.vertices=new float[][]{new float[]{-100,0,-100},new float[]{249,0,-100},new float[]{-100,0,100},new float[]{249,0,100},new float[]{251,0,-100},new float[]{600,0,-100},new float[]{251,0,100},new float[]{600,0,100}};
            terrain.Mesh.triangles=new MapFace[]{new MapFace{v=new int[]{0,2,1},normal=new float[]{0,1,0}},new MapFace{v=new int[]{1,2,3},normal=new float[]{0,1,0}},new MapFace{v=new int[]{4,6,5},normal=new float[]{0,1,0}},new MapFace{v=new int[]{5,6,7},normal=new float[]{0,1,0}}};
            Check(!NavigationRoute.ClearWalk(terrain,new MapLayers(terrain.Mesh).Floors,start,end),"walking route crossed a thin floor gap");
            string folder=Path.Combine(root,"collision-map");Write(folder,map);map=MapSnapshot.Load(folder,null);
            Check(map.Live.collision.models.Length==1 && map.Live.actors[0].Name=="Test obstacle","collision serialization lost data");
            NavigationRoute straight=NavigationRoute.Plan(map,new float[]{500,0,0});map.Live.collision.models[0].enabled=true;
            Check(NavigationCollision.CheckRoute(map.Live,straight,0)!=null,"newly enabled blocker did not invalidate route");
            Check(NavigationCollision.CheckRoute(map.Live,straight,straight.Points.Count)==null,"completed route rechecked old segments");
            // Rendering preserves an upper-story box as context without filling
            // the player's lower floor. Disabled boxes are also unfilled.
            map.Live.collision.models[0].enabled=true;MapLayers layers=new MapLayers(map.Mesh);
            Func<HeightPoint,PointF> project=delegate(HeightPoint p){return new PointF(p.X,p.Z+100);};
            using(Bitmap filled=new Bitmap(600,220))using(Bitmap other=new Bitmap(600,220))using(Font font=new Font("Segoe UI",9)) {
                using(Graphics g=Graphics.FromImage(filled)){g.Clear(Color.Black);CollisionMapDrawing.Paint(g,map.Live,layers,0,-5,5,true,false,0,font,project);}
                using(Graphics g=Graphics.FromImage(other)){g.Clear(Color.Black);CollisionMapDrawing.Paint(g,map.Live,layers,0,150,160,true,false,0,font,project);}
                Check(filled.GetPixel(230,110).ToArgb()!=Color.Black.ToArgb(),"same-floor collision has no fill");
                Check(other.GetPixel(230,110).ToArgb()==Color.Black.ToArgb(),"other-floor collision filled current slice");
                filled.Save(Path.Combine(root,"collision-footprint-test.png"));
            }
            // Exercise actual UI dispatch and cancellation when a moving/closing
            // model makes a previously planned route unsafe.
            map=Fixture();Put(map,0,81,false);
            map.Live.exits=new MapMarker[]{new MapMarker {address=0x80103000,position=new float[]{500,0,0},destination_code=99}};
            map.Live.progression=new MapProgression {schema=1,inventory=new MapInventory(),nodes=new MapInteraction[]{new MapInteraction {
                address=0x80103000,position=new float[]{500,0,0},kind="exit",label="Exit 1",action="enter_exit",status="unknown",requirement="Unknown",reward="Unknown",traversal="unknown"}}};
            Write(folder,map);
            using(NavigationMapWindow window=new NavigationMapWindow(folder)) {
                window.ShowInTaskbar=false;window.StartPosition=FormStartPosition.Manual;window.Location=new Point(-32000,-32000);window.Show();Application.DoEvents();
                Button(window,"Plan exit route").PerformClick();Button(window,"Start AI").PerformClick();
                string command=File.ReadAllText(Path.Combine(folder,"ai-command.txt"));string[] words=command.Split(new char[]{' ','\r','\n'},StringSplitOptions.RemoveEmptyEntries);
                Check(Int32.Parse(words[6])>0,"UI did not dispatch collision-checked route");
                map.Live.navigation_ai=new MapAi {nonce=Int64.Parse(words[3]),active=true,state="following",waypoint=0};
                map.Live.collision.models[0].enabled=true;++map.Live.update;Write(folder,map);window.RefreshMap();
                words=File.ReadAllText(Path.Combine(folder,"ai-command.txt")).Split(new char[]{' ','\r','\n'},StringSplitOptions.RemoveEmptyEntries);
                Check(words[6]=="0","UI kept moving after entity blocked the route");window.Close();
            }
            using(MapCanvas canvas=new MapCanvas()) {
                map=Fixture();canvas.UpdateMap(map);
                Check(canvas.EntityLow==4 && canvas.EntityHigh==80,"player floor does not use body height");
                canvas.Mode=1;canvas.ManualHeight=200;canvas.SliceWidth=40;
                Check(canvas.EntityLow==180 && canvas.EntityHigh==220,"manual height slice ignored");
            }
            // Drift changes the segment from the actual player position. Check
            // terrain again instead of assuming the originally planned line is safe.
            map=Fixture();NavigationRoute drift=NavigationRoute.Plan(map,new float[]{500,0,0});
            Check(drift.CheckRemaining(map,0)==null,"open live segment rejected");
            MapGeometry old=map.Mesh;
            var vertices=new System.Collections.Generic.List<float[]>(old.vertices);
            int first=vertices.Count;
            vertices.Add(new float[]{250,0,-300});vertices.Add(new float[]{250,200,-300});vertices.Add(new float[]{250,0,300});vertices.Add(new float[]{250,200,300});
            var faces=new System.Collections.Generic.List<MapFace>(old.triangles);
            faces.Add(new MapFace {v=new int[]{first,first+1,first+2}});faces.Add(new MapFace {v=new int[]{first+1,first+3,first+2}});
            map.Mesh=new MapGeometry {vertices=vertices.ToArray(),triangles=faces.ToArray()};
            Check(drift.CheckRemaining(map,0)!=null,"live terrain obstruction was ignored");
            // A room-sized obstacle needs a global detour beyond the local 360-unit patch.
            map=Fixture();Put(map,0,180,true);map.Live.collision.models[0].lower[2]=-700;map.Live.collision.models[0].upper[2]=700;
            NavigationRoute around=NavigationRoute.Plan(map,new float[]{500,0,0});bool beyond=false;HeightPoint prev=new HeightPoint(map.Live.player.position);
            foreach(HeightPoint point in around.Points){if(Math.Abs(point.Z)>720)beyond=true;Check(NavigationRoute.ClearWalk(map,new MapLayers(map.Mesh).Floors,prev,point),"global detour emitted uncleared segment");prev=point;}
            Check(beyond,"room-wide search did not go around long obstacle");
            // Prefer the open side of a hut over a short body-width squeeze.
            map=Fixture();Put(map,0,180,true);
            map.Live.player.position=new float[]{0,0,70};
            var obstacle=map.Live.collision.models[0];obstacle.lower[2]=-800;obstacle.upper[2]=40;
            var comfort=NavigationRoute.Plan(map,new float[]{500,0,70});
            HeightPoint last=new HeightPoint(map.Live.player.position);bool wide=false;
            foreach(HeightPoint point in comfort.Points) {
                Check(NavigationCollision.Blocking(map.Live,last,point,NavigationCollision.Radius+NavigationRoute.PlanningMargin)==null,"planned route left no steering clearance");
                if(point.Z>100)wide=true;last=point;
            }
            Check(wide,"short narrow route was preferred over open detour");
            map.Live.player.position=new float[]{0,0,100};
            Check(NavigationRoute.ClearWalk(map,new MapLayers(map.Mesh).Floors,new HeightPoint(map.Live.player.position),new HeightPoint(500,0,100),NavigationRoute.PlanningMargin),"preference fixture must have a valid short route");
            comfort=NavigationRoute.Plan(map,new float[]{500,0,100});wide=false;
            foreach(HeightPoint point in comfort.Points)if(point.Z>150)wide=true;
            Check(wide,"valid shortest route was accepted without comparing safer clearance");
            // Increasing the margin must retain the original body probes; an
            // interior thin obstacle must not fall between new outer probes.
            map=Fixture();map.Mesh.vertices=new float[][] {
                new float[]{-1000,0,-1000},new float[]{1000,0,-1000},new float[]{-1000,0,1000},new float[]{1000,0,1000},
                new float[]{250,70,19},new float[]{250,90,19},new float[]{250,70,21},new float[]{250,90,21}};
            map.Mesh.triangles=new MapFace[] {new MapFace{v=new int[]{0,2,1},normal=new float[]{0,1,0}},new MapFace{v=new int[]{1,2,3},normal=new float[]{0,1,0}},new MapFace{v=new int[]{4,5,6}},new MapFace{v=new int[]{5,7,6}}};
            Check(!NavigationRoute.ClearWalk(map,new MapLayers(map.Mesh).Floors,start,end),"body probe missed thin interior obstacle");
            Check(!NavigationRoute.ClearWalk(map,new MapLayers(map.Mesh).Floors,start,end,NavigationRoute.PlanningMargin),"comfort probes discarded body collision checks");
            var planned=Fixture();var latest=Fixture();
            var dispatched=NavigationRoute.Plan(planned,new float[]{500,0,0});
            planned.Live.timestamp_ms=NavigationExplorer.Clock-6000;
            Check(dispatched.DispatchProblem(planned,latest)==null,"fresh verified snapshot could not replace aged planning snapshot");
            latest.Live.navigation_ai.manual_inputs++;
            Check(dispatched.DispatchProblem(planned,latest).Contains("manual"),"input during planning allowed automatic dispatch");
            latest.Live.navigation_ai.manual_inputs=0;latest.Live.clearing_active=false;
            Check(dispatched.DispatchProblem(planned,latest).Contains("suspended"),"cutscene during planning allowed dispatch");
            latest.Live.clearing_active=true;latest.Live.generation++;
            Check(dispatched.DispatchProblem(planned,latest).Contains("changed"),"changed room allowed dispatch");
            latest.Live.generation=1;latest.Live.timestamp_ms=NavigationExplorer.Clock-6000;
            Check(dispatched.DispatchProblem(planned,latest).Contains("stopped"),"stale latest snapshot allowed dispatch");
            return checks;
        }
    }
}
