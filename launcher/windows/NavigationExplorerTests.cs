using System;
using System.Collections.Generic;
using System.IO;
using System.Drawing;
using System.Windows.Forms;
using System.Runtime.Serialization.Json;

namespace JfgLauncher {
    internal static class NavigationExplorerTests {
        private static int checks;
        private static void Check(bool value,string reason){if(!value)throw new Exception("Explorer: "+reason);++checks;}
        private static MapMarker Exit(int id,float x,float z) {
            return new MapMarker {address=(uint)id,destination_code=65000+id,position=new float[]{x,0,z},normal=new float[]{1,0,0}};
        }
        private static MapSnapshot Room(uint level,long generation,params MapMarker[] exits) {
            return new MapSnapshot {
                Mesh=new MapGeometry {schema=1,level=level,generation=generation,vertices=new float[][] {new float[]{-1000,0,-1000},new float[]{1000,0,-1000},new float[]{-1000,0,1000},new float[]{1000,0,1000}},
                    triangles=new MapFace[] {new MapFace {v=new int[]{0,2,1},normal=new float[]{0,1,0}},new MapFace {v=new int[]{1,2,3},normal=new float[]{0,1,0}}}},
                Live=new MapLive {schema=1,level=level,generation=generation,mesh_ready=true,clearing_active=true,timestamp_ms=100000,update=1,
                    player=new MapPlayer {position=new float[]{0,0,0}},exits=exits,markers=new MapMarker[0],npcs=new MapMarker[0],navigation_ai=new MapAi(),
                    progression=new MapProgression {schema=1,inventory=new MapInventory {known=true,character=0,red_key=false,weapons_mask=1},nodes=new MapInteraction[0]}}
            };
        }
        private static NavigationRoute SimplePlan(MapSnapshot map,MapMarker target) {
            NavigationRoute route=new NavigationRoute {Level=map.Live.level,Generation=map.Live.generation};
            route.Points.Add(new HeightPoint(target.position));return route;
        }
        private sealed class Simulation {
            internal NavigationExplorer Explorer;
            internal MapSnapshot Map;
            internal long Now=100000,Nonce=1000;
            internal Simulation(MapSnapshot map) : this(map,SimplePlan) { }
            internal Simulation(MapSnapshot map,Func<MapSnapshot,MapMarker,NavigationRoute> planner) {
                Map=map;Explorer=new NavigationExplorer(planner);Explorer.Start(Map,Now);
            }
            internal ExploreCommand Tick(long advance) {
                Now+=advance;Map.Live.timestamp_ms=Now;++Map.Live.update;
                ExploreCommand result=Explorer.Tick(Map,Now);
                if(result.Route!=null){Explorer.Dispatched(++Nonce,Now);Map.Live.navigation_ai=new MapAi {nonce=Nonce,active=true,state="following"};}
                return result;
            }
            internal void Reach(MapMarker exit) { Map.Live.player.position=(float[])exit.position.Clone();Tick(200); }
            internal void Arrive(MapSnapshot next) { Map=next;Tick(200);Tick(700); }
        }
        private static ExploreExit Remember(MapMarker marker,uint? destination) {
            return new ExploreExit {key=NavigationExplorer.ExitKey(marker),position=marker.position,rawDestination=marker.destination_code,destination=destination};
        }
        private static Button FindButton(Control parent,string label) {
            foreach(Control child in parent.Controls) {
                if(child is Button && child.Text==label)return (Button)child;
                Button found=FindButton(child,label);if(found!=null)return found;
            }
            return null;
        }
        private static void WriteSnapshot(string directory,MapSnapshot map) {
            map.Live.timestamp_ms=NavigationExplorer.Clock;++map.Live.update;
            using(FileStream file=File.Create(Path.Combine(directory,"mesh.json")))new DataContractJsonSerializer(typeof(MapGeometry)).WriteObject(file,map.Mesh);
            using(FileStream file=File.Create(Path.Combine(directory,"live.json")))new DataContractJsonSerializer(typeof(MapLive)).WriteObject(file,map.Live);
        }
        private static string[] Command(string directory) { return File.ReadAllText(Path.Combine(directory,"ai-command.txt")).Split(new char[]{' ','\n','\r'},StringSplitOptions.RemoveEmptyEntries); }
        internal static int Run(string directory) {
            checks=0;
            MapMarker entrance=Exit(1,0,0),forward=Exit(2,500,0);
            Simulation s=new Simulation(Room(1,1,entrance,forward));
            Check(s.Tick(0).Route!=null && s.Explorer.TargetKey==NavigationExplorer.ExitKey(forward),"picked arrival doorway before new exit");
            string stable=NavigationExplorer.ExitKey(forward);forward.address=900;
            Check(NavigationExplorer.ExitKey(forward)==stable,"actor reallocation changed exit identity");
            MapMarker sameCode=Exit(3,600,0);sameCode.destination_code=forward.destination_code;
            Check(NavigationExplorer.ExitKey(sameCode)!=stable,"two exits sharing a destination collapsed");
            s.Reach(forward);s.Arrive(Room(2,2,Exit(20,0,0)));
            Check(s.Explorer.History.rooms[0].exits[1].destination==2,"did not learn observed destination");
            Check(!s.Explorer.History.rooms[1].exits[0].destination.HasValue,"invented reverse connection");
            Check(s.Explorer.History.rooms[0].exits[1].destination!=forward.destination_code,"treated raw destination as room ID");

            // A -> B -> C -> A has no unexplored exits left. It must not start again.
            MapMarker ab=Exit(10,500,0),bc=Exit(11,500,0),ca=Exit(12,500,0);
            s=new Simulation(Room(10,1,ab));s.Tick(0);s.Reach(ab);s.Arrive(Room(11,2,bc));
            Check(s.Tick(700).Route!=null,"did not continue in new room");s.Reach(bc);s.Arrive(Room(12,3,ca));
            s.Tick(700);s.Reach(ca);s.Arrive(Room(10,4,ab));
            Check(s.Tick(700).Stop && !s.Explorer.Running,"circular route did not terminate");
            Check(s.Tick(700).Route==null,"stopped loop restarted itself");
            Check(s.Explorer.History.rooms.Count==3,"room generations counted as new rooms");

            // Directed known backtracking: B -> A -> C, where C still has an unknown exit.
            MapMarker ba=Exit(21,500,0),ac=Exit(22,700,0),ab2=Exit(23,500,0),unknown=Exit(24,800,0);
            s=new Simulation(Room(21,1,ba));
            s.Explorer.History.rooms[0].exits[0].destination=20;
            s.Explorer.History.rooms.Add(new ExploreRoom {level=20,exits=new List<ExploreExit>{Remember(ab2,21),Remember(ac,22)}});
            s.Explorer.History.rooms.Add(new ExploreRoom {level=22,exits=new List<ExploreExit>{Remember(unknown,null)}});
            Check(s.Tick(0).Route!=null && s.Explorer.TargetKey==NavigationExplorer.ExitKey(ba),"failed deliberate backtracking to frontier");
            s.Reach(ba);s.Arrive(Room(20,2,ab2,ac));s.Tick(700);
            Check(s.Explorer.TargetKey==NavigationExplorer.ExitKey(ac),"backtracking bounced back into exhausted room");

            // Geometric failures are remembered, not retried every update.
            int plans=0;MapMarker bad=Exit(30,450,0),good=Exit(31,700,0);
            s=new Simulation(Room(30,1,bad,good),delegate(MapSnapshot map,MapMarker exit){++plans;if(exit==bad)throw new InvalidDataException("Disconnected floor");return SimplePlan(map,exit);});
            Check(s.Tick(0).Route==null && plans==1,"did not record disconnected route");
            Check(s.Tick(400).Route!=null && plans==2 && s.Explorer.TargetKey==NavigationExplorer.ExitKey(good),"did not choose alternative exit");
            Check(s.Explorer.Describe(30,bad).StartsWith("Blocked:"),"blocked reason not exposed");

            // Arrival at the marker is not transition success.
            s=new Simulation(Room(31,1,good));s.Tick(0);s.Reach(good);
            s.Map.Live.navigation_ai.active=false;s.Map.Live.navigation_ai.state="approach_complete";
            s.Tick(200);Check(!s.Explorer.MayHeartbeat,"kept moving after approach completion");
            Check(s.Tick(2600).Stop && !s.Explorer.History.rooms[0].exits[0].destination.HasValue,"approach falsely confirmed a destination");
            Check(s.Tick(600).Stop && !s.Explorer.Running,"blocked doorway retried indefinitely");

            // Progress permits a retry, but repeated toggles and reloading do not.
            s=new Simulation(Room(32,1,bad),delegate(MapSnapshot map,MapMarker exit){throw new InvalidDataException("Locked route");});
            s.Tick(0);s.Tick(400);Check(!s.Explorer.Running,"failed single route did not stop");
            int revision=s.Explorer.History.unlockRevision;
            s.Map.Live.progression.inventory.red_key=true;s.Explorer.Start(s.Map,s.Now);s.Tick(0);
            Check(s.Explorer.History.unlockRevision==revision+1 && s.Explorer.History.rooms[0].exits[0].attempts==2,"new key did not reconsider blocked exit");
            s.Explorer.Stop("test");s.Map.Live.progression.inventory.red_key=false;s.Explorer.Start(s.Map,s.Now);s.Tick(0);
            s.Explorer.Stop("test");s.Map.Live.progression.inventory.red_key=true;s.Explorer.Start(s.Map,s.Now);s.Tick(0);
            Check(s.Explorer.History.unlockRevision==revision+1 && s.Explorer.History.rooms[0].exits[0].attempts==2,"repeated inventory toggle created endless retries");

            s=new Simulation(Room(40,1,good));s.Tick(0);s.Map.Live.navigation_ai.active=false;s.Map.Live.navigation_ai.state="manual_takeover";
            Check(s.Tick(200).Stop && !s.Explorer.Running,"manual input did not stop explorer");
            Check(s.Tick(200).Route==null,"manual cancellation rearmed controller");
            s=new Simulation(Room(40,1,good));s.Tick(0);s.Now+=6000;
            Check(s.Explorer.Tick(s.Map,s.Now).Stop && !s.Explorer.Running,"stale map did not stop");
            s=new Simulation(Room(40,1,good));s.Tick(0);s.Map.Live.update=-5;
            Check(s.Tick(200).Stop && !s.Explorer.Running,"rewound game state accepted");
            s=new Simulation(Room(40,1,good));s.Tick(0);s.Map.Live.navigation_ai=new MapAi();
            Check(s.Tick(3200).Stop && !s.Explorer.Running,"missing native acknowledgement did not stop");
            s=new Simulation(Room(40,1,good));s.Tick(0);s.Map.Live.navigation_ai.active=false;s.Map.Live.navigation_ai.state="calibration_blocked";
            Check(s.Tick(200).Stop && s.Explorer.Describe(40,good).StartsWith("Blocked:"),"movement failure not recorded");
            s=new Simulation(Room(40,1,good));s.Tick(0);s.Reach(good);
            s.Map.Live.clearing_active=false;s.Tick(200);s.Map.Live.clearing_active=true;
            Check(s.Tick(200).Stop && !s.Explorer.Running,"pause/resume restarted autonomous movement");

            // Brief load gaps near a confirmed approach can be followed across rooms.
            s=new Simulation(Room(50,1,good));s.Tick(0);s.Reach(good);
            Check(s.Explorer.MissingMap(s.Now+100).Stop && s.Explorer.Running && !s.Explorer.MayHeartbeat,"load gap did not release movement");
            s.Arrive(Room(51,2,Exit(50,500,0)));
            Check(s.Explorer.Running && s.Explorer.History.rooms[0].exits[0].destination==51,"valid transition lost across load gap");
            s=new Simulation(Room(50,1,good));s.Tick(0);s.Reach(good);s.Explorer.MissingMap(s.Now+100);
            Check(s.Explorer.MissingMap(s.Now+20200).Stop && !s.Explorer.Running,"load gap waited indefinitely");
            s=new Simulation(Room(50,1,good));s.Tick(0);s.Tick(200);s.Arrive(Room(51,2,Exit(50,500,0)));
            Check(!s.Explorer.Running && !s.Explorer.History.rooms[0].exits[0].destination.HasValue,"unrelated load invented exit connection");
            s=new Simulation(Room(50,1,good));s.Tick(0);s.Reach(good);s.Arrive(Room(50,2,good));s.Tick(11000);s.Tick(700);
            Check(!s.Explorer.Running && s.Explorer.History.rooms.Count==1,"same-room exit loop continued");
            s=new Simulation(Room(50,1,good));Check(s.Tick(15*60*1000+1).Stop && !s.Explorer.Running,"exploration run limit missing");

            s=new Simulation(Room(55,1,good));s.Tick(0);s.Reach(good);
            s.Map.Live.generation=2;s.Map.Mesh.generation=2;s.Tick(200);
            Check(!s.Explorer.History.rooms[0].exits[0].destination.HasValue && !s.Explorer.MayHeartbeat,"source generation refresh falsely confirmed a room");
            s.Arrive(Room(56,2,bad));
            Check(s.Explorer.History.rooms[0].exits[0].destination==56,"lost destination after transient source snapshot");
            s=new Simulation(Room(57,1,good));s.Tick(0);s.Reach(good);
            s.Map.Live.generation=2;s.Map.Mesh.generation=2;s.Map.Live.transition_confirm=true;
            Check(s.Tick(200).Confirm,"area-clear confirmation not requested");
            Check(!s.Tick(200).Confirm,"area-clear confirmation repeated");
            s.Map.Live.transition_confirm=false;s.Arrive(Room(58,2,bad));
            Check(s.Explorer.History.rooms[0].exits[0].destination==58,"acknowledged area-clear transition not learned");
            s=new Simulation(Room(59,1,bad),delegate(MapSnapshot map,MapMarker exit){throw new InvalidDataException("Blocked");});
            s.Tick(0);s.Explorer.RetryRoom(s.Map,s.Now);s.Explorer.Start(s.Map,s.Now);s.Tick(0);
            Check(s.Explorer.History.rooms[0].exits[0].attempts==2,"explicit room retry erased attempts or did not permit another try");
            s.Explorer.Stop("test");s.Map.Live.transition_confirm=true;bool promptRejected=false;
            try{s.Explorer.Start(s.Map,s.Now);}catch(InvalidDataException){promptRejected=true;}
            Check(promptRejected,"exploration began inside an unrelated transition prompt");
            // Real surface planner extends through a doorway only over known floor.
            MapSnapshot floor=Room(60,1,good);NavigationRoute approach=NavigationRoute.Plan(floor,good.position);
            NavigationRoute crossing=NavigationRoute.PlanExit(floor,good);
            Check(crossing.Points.Count>approach.Points.Count && crossing.Points[crossing.Points.Count-1].X>good.position[0],"did not plan through mapped doorway");
            MapMarker boundary=Exit(60,990,0);crossing=NavigationRoute.PlanExit(floor,boundary);
            Check(crossing.Points[crossing.Points.Count-1].X==990,"crossing left known floor");

            s=new Simulation(Room(61,1,good));s.Tick(0);s.Reach(good);
            MapSnapshot interrupted=Room(62,2,bad);interrupted.Live.navigation_ai.manual_inputs=1;s.Arrive(interrupted);
            Check(!s.Explorer.Running && !s.Explorer.History.rooms[0].exits[0].destination.HasValue,"manual input during room load was lost");
            s=new Simulation(Room(61,1,good));s.Map.Live.navigation_ai.manual_inputs=1;
            Check(s.Tick(0).Stop && !s.Explorer.Running,"manual input before dispatch was lost");
            MapSnapshot smooth=Room(63,1,good);
            System.Collections.Generic.List<HeightSurface> surfaces=new MapLayers(smooth.Mesh).Floors;
            Check(NavigationRoute.StraightWalk(smooth.Mesh,surfaces,new HeightPoint(0,0,0),new HeightPoint(400,0,0)),"open straight segment refused");
            Check(!NavigationRoute.StraightWalk(smooth.Mesh,surfaces,new HeightPoint(0,0,0),new HeightPoint(400,100,0)),"shortcut crossed floor heights");
            smooth.Mesh.vertices=new float[][] {new float[]{-1000,0,-1000},new float[]{1000,0,-1000},new float[]{-1000,0,1000},new float[]{1000,0,1000},new float[]{200,0,-200},new float[]{200,200,-200},new float[]{200,0,200},new float[]{200,200,200}};
            smooth.Mesh.triangles=new MapFace[]{smooth.Mesh.triangles[0],smooth.Mesh.triangles[1],new MapFace {v=new int[]{4,5,6}},new MapFace {v=new int[]{5,7,6}}};
            Check(!NavigationRoute.StraightWalk(smooth.Mesh,surfaces,new HeightPoint(0,0,0),new HeightPoint(400,0,0)),"shortcut crossed a wall");
            MapGeometry gap=new MapGeometry {vertices=new float[][]{new float[]{-100,0,-100},new float[]{199,0,-100},new float[]{-100,0,100},new float[]{199,0,100},new float[]{201,0,-100},new float[]{500,0,-100},new float[]{201,0,100},new float[]{500,0,100}},triangles=new MapFace[]{new MapFace {v=new int[]{0,2,1},normal=new float[]{0,1,0}},new MapFace {v=new int[]{1,2,3},normal=new float[]{0,1,0}},new MapFace {v=new int[]{4,6,5},normal=new float[]{0,1,0}},new MapFace {v=new int[]{5,6,7},normal=new float[]{0,1,0}}}};
            Check(!NavigationRoute.StraightWalk(gap,new MapLayers(gap).Floors,new HeightPoint(0,0,0),new HeightPoint(400,0,0)),"shortcut bridged a thin gap");
            MapSnapshot steep=Room(64,1,good);
            steep.Mesh.vertices=new float[][] {new float[]{0,0,0},new float[]{200,400,0},new float[]{0,0,200},new float[]{200,400,200}};
            steep.Live.player.position=new float[]{20,40,20};bool slopeRejected=false;
            try {NavigationRoute.Plan(steep,new float[]{180,360,180});}catch(InvalidDataException){slopeRejected=true;}
            Check(slopeRejected,"steep rock face treated as ordinary walking floor");
            // History survives closing the map, without remembering an armed command.
            s=new Simulation(Room(70,1,good));s.Tick(0);s.Reach(good);s.Arrive(Room(71,2,Exit(70,500,0)));
            string path=Path.Combine(directory,"explorer-history-test");Directory.CreateDirectory(path);s.Explorer.Save(path);
            NavigationExplorer loaded=NavigationExplorer.Load(path);
            Check(!loaded.Running && loaded.History.rooms.Count==2 && loaded.History.rooms[0].exits[0].destination==71,"history persistence lost connection or armed movement");
            File.WriteAllText(Path.Combine(path,"exploration-history.json"),"{broken");
            bool rejected=false;try{NavigationExplorer.Load(path);}catch(InvalidDataException){rejected=true;}
            Check(rejected,"corrupt history accepted");
            // A disappearing exit cannot keep a phantom frontier alive.
            s=new Simulation(Room(80,1,bad,good));s.Map.Live.exits=new MapMarker[]{good};s.Tick(0);
            Check(s.Explorer.History.rooms[0].exits[0].absent,"absent exit remained a frontier");
            s.Explorer.Stop("test");s.Map.Live.exits=new MapMarker[]{bad,good};s.Explorer.Start(s.Map,s.Now);
            Check(!s.Explorer.History.rooms[0].exits[0].absent,"reappearing exit stayed unavailable");
            s=new Simulation(Room(80,1,good));s.Tick(0);s.Reach(good);
            MapSnapshot arriving=Room(81,2,bad);arriving.Live.clearing_active=false;s.Arrive(arriving);
            Check(s.Explorer.Running && !s.Explorer.MayHeartbeat,"did not suspend during destination load");
            s.Tick(700);s.Map.Live.clearing_active=true;s.Tick(700);
            Check(s.Tick(700).Route!=null,"did not continue after confirmed destination finished loading");

            // Exercise actual buttons, command files, and serialized native acknowledgements.
            string ui=Path.Combine(directory,"explorer-ui-test");Directory.CreateDirectory(ui);
            MapSnapshot uiMap=Room(90,1,good);WriteSnapshot(ui,uiMap);
            using(NavigationMapWindow window=new NavigationMapWindow(ui)) {
                window.StartPosition=FormStartPosition.Manual;window.Location=new Point(-32000,-32000);window.ShowInTaskbar=false;window.Show();Application.DoEvents();
                Button explore=FindButton(window,"Explore automatically"),stop=FindButton(window,"Stop AI");
                Check(explore!=null && stop!=null,"explorer controls missing");
                Check(FindButton(window,"Retry room exits")!=null,"explicit room retry control missing");
                explore.PerformClick();string[] command=Command(ui);
                Check(command[0]=="JFGNAV1" && command[1]=="90" && Int32.Parse(command[6])>0,"Explore button did not dispatch route");
                uiMap.Live.navigation_ai=new MapAi {nonce=Int64.Parse(command[3]),active=false,state="manual_takeover"};WriteSnapshot(ui,uiMap);window.RefreshMap();
                command=Command(ui);Check(command[6]=="0","native manual takeover did not send stop");
                string stopped=File.ReadAllText(Path.Combine(ui,"ai-command.txt"));window.RefreshMap();
                Check(File.ReadAllText(Path.Combine(ui,"ai-command.txt"))==stopped,"UI rearmed after manual takeover");
                explore.PerformClick();Check(Command(ui)[6]!="0","explicit restart failed");
                stop.PerformClick();Check(Command(ui)[6]=="0","Stop AI did not cancel exploration");
                explore.PerformClick();window.Close();Check(Command(ui)[6]=="0","closing map did not release controls");
            }
            return checks;
        }
    }
}
