using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Runtime.Serialization;
using System.Text;
using System.Threading;

namespace JfgLauncher {
    [DataContract] internal sealed class MapDialogueChoice {
        [DataMember] public int action=0,prerequisite=0;
    }
    [DataContract] internal sealed class MapDialogue {
        [DataMember] public bool known=false,active=false,ready=false,choices=false;
        [DataMember] public uint token=0;
        [DataMember] public int selected=0;
        [DataMember] public MapDialogueChoice[] rows=null;
        internal void Validate() {
            if(!known)return;
            if(selected<0||selected>31||rows==null||rows.Length>32)throw new InvalidDataException("Invalid dialogue state.");
            if(active&&choices&&(rows.Length==0||selected>=rows.Length))throw new InvalidDataException("Invalid dialogue selection.");
            foreach(var row in rows)if(row==null||row.action<0||row.action>65535||row.prerequisite< -1||row.prerequisite>32767)
                throw new InvalidDataException("Invalid dialogue choice.");
        }
    }
    internal static class DialogueFlow {
        internal static bool Active(MapSnapshot map) {return map.Live.dialogue!=null&&map.Live.dialogue.known&&map.Live.dialogue.active;}
        // Offers describe a ROM-derived path. Match actions, never translated text
        // or menu indices (the game removes invisible rows from live menus).
        internal static int Select(MapDialogue d,MapNpcOffer offer,bool owned) {
            if(!d.ready)return -1;
            if(!d.choices)return 0;
            int target=-1;
            if(offer!=null&&!owned) {
                for(int i=0;i<d.rows.Length;i++)if(d.rows[i].action==offer.action){target=i;break;}
                if(target<0) {
                    string[] path=offer.id.Split('/');
                    for(int step=1;step<path.Length;step++) {
                        int table;if(!Int32.TryParse(path[step].Split(':')[0],out table))continue;
                        for(int i=0;i<d.rows.Length;i++)if(d.rows[i].action==(0x2000|table))target=i;
                        if(target>=0)break;
                    }
                }
            }
            if(target<0&&(offer==null||owned))
                for(int i=0;i<d.rows.Length;i++)if((d.rows[i].action&0xF000)==0x5000){target=i;break;}
            if(target<0)throw new InvalidDataException("Dialogue choice needs a known reward path or manual selection.");
            return target==d.selected?0:target<d.selected?1:2;
        }
        internal static void Send(string directory,MapLive live,long nonce,int action) {
            string text=String.Format(CultureInfo.InvariantCulture,"JFGDIALOGUE1 {0} {1} {2} {3} {4} {5} {6}\n",
                live.level,live.generation,nonce,NavigationExplorer.Clock,
                live.navigation_ai==null?0:live.navigation_ai.manual_inputs,live.dialogue.token,action);
            string file=Path.Combine(directory,"ai-dialogue.txt"),temp=file+".tmp";
            File.WriteAllText(temp,text,new UTF8Encoding(false));
            if(File.Exists(file))File.Replace(temp,file,null);else File.Move(temp,file);
        }
    }
    // Coordinates the existing exit explorer and shared action runner. Only one
    // owns ai-command.txt at a time; a stopped worker must exit before restart.
    internal sealed class AutonomousExplorer {
        private NavigationExplorer exits;
        private readonly string directory;
        private readonly Action<ChestTrial,string,uint,MapNpcOffer,float[]> execute;
        private ChestTrial trial;
        private Thread worker;
        private volatile bool done;
        private volatile string message="",failure;
        private bool running,launchPending,resume;
        private string kind;
        private uint actor;
        private MapNpcOffer offer;
        private float[] goal;
        private long started,manual,lastNow;
        private readonly HashSet<string> attempted=new HashSet<string>();
        internal int JumpButton=8;
        internal AutonomousExplorer(string path,NavigationExplorer explorer) {directory=path;exits=explorer;execute=Execute;}
        internal AutonomousExplorer(string path,NavigationExplorer explorer,Action<ChestTrial,string,uint,MapNpcOffer,float[]> executor) {directory=path;exits=explorer;execute=executor;}
        private void Execute(ChestTrial runner,string action,uint address,MapNpcOffer reward,float[] destination) {
            if(action=="dialogue")runner.RunDialogue();
            else if(action=="NPC reward")runner.RunNpc(address,reward);
            else if(action=="weapon chest")runner.Run(address,JumpButton);
            else if(action=="key pickup")runner.RunPickup(address,JumpButton);
            else runner.RunTraversal(destination,JumpButton);
        }
        internal static AutonomousExplorer Load(string path){return new AutonomousExplorer(path,NavigationExplorer.Load(path));}
        internal bool Busy {get{return worker!=null&&!done;}}
        internal bool Running {get{return running;}}
        internal bool MayHeartbeat {get{return running&&!Busy&&!launchPending&&!resume&&exits.MayHeartbeat;}}
        internal string Status {get{return Busy||launchPending?message:!running&&!String.IsNullOrEmpty(failure)?failure:exits.Status;}}
        internal string TargetKey {get{return exits.TargetKey;}}
        internal string Describe(uint level,MapMarker marker){return exits.Describe(level,marker);}
        internal void Save(string path){exits.Save(path);}
        internal void ObserveIdle(MapSnapshot map,long now){if(!Busy&&!launchPending)exits.ObserveIdle(map,now);}
        internal void Dispatched(long nonce,long now){exits.Dispatched(nonce,now);}
        internal ExploreCommand RouteBlocked(string reason,long now){return exits.RouteBlocked(reason,now);}
        internal void RetryRoom(MapSnapshot map,long now){if(Busy)return;attempted.Clear();exits.RetryRoom(map,now);}
        internal void Stop(string reason){
            running=false;launchPending=false;failure=reason;exits.Stop(reason);
            if(trial!=null)trial.Cancelled=true;
        }
        internal void Start(MapSnapshot map,long now) {
            if(Busy)throw new InvalidDataException("The previous action is stopping; wait before restarting.");
            worker=null;trial=null;done=false;failure=null;attempted.Clear();
            if(map==null||map.Live.dialogue==null)throw new InvalidDataException("Update the native runtime for autonomous dialogue support.");
            started=lastNow=now;manual=map.Live.navigation_ai==null?0:map.Live.navigation_ai.manual_inputs;
            exits.Start(map,now);running=true;resume=false;
        }
        private ExploreCommand Halt(string reason){Stop(reason);return new ExploreCommand{Stop=true};}
        internal ExploreCommand MissingMap(long now) {
            if(Busy||launchPending)return Halt("Autonomous AI stopped: map unavailable during action.");
            var result=exits.MissingMap(now);running=exits.Running;return result;
        }
        internal static MapNpcOffer UsefulOffer(MapInteraction node) {
            if(node.action!="talk"||node.offers==null)return null;
            MapNpcOffer best=null;int priority=Int32.MaxValue;
            foreach(var o in node.offers)if(o.status=="available"&&
                (o.kind=="item"||o.kind=="weapon"||o.kind=="ship_part")&&o.cost==0) {
                int rank=o.kind=="item"?0:o.kind=="ship_part"?1:2;
                if(rank<priority){priority=rank;best=o;}
            }
            return best;
        }
        internal static int ObjectivePriority(MapInteraction node) {
            var reward=UsefulOffer(node);
            if(reward!=null)return reward.kind=="item"?0:reward.kind=="ship_part"?1:2;
            if(node.action=="collect"&&node.kind=="key")return 0;
            if(node.action=="open_chest")return 3;
            return 10;
        }
        private static MapInteraction[] OrderedObjectives(MapSnapshot map) {
            var nodes=(MapInteraction[])map.Live.progression.nodes.Clone();
            Array.Sort(nodes,delegate(MapInteraction a,MapInteraction b) {
                int priority=ObjectivePriority(a).CompareTo(ObjectivePriority(b));
                if(priority!=0)return priority;
                var p=new HeightPoint(map.Live.player.position);
                return BoxJumpPlanner.Horizontal(p,new HeightPoint(a.position)).CompareTo(
                    BoxJumpPlanner.Horizontal(p,new HeightPoint(b.position)));
            });
            return nodes;
        }
        private ExploreCommand Prepare(string action,uint address,MapNpcOffer reward,float[] destination) {
            kind=action;actor=address;offer=reward;goal=destination;
            launchPending=true;resume=true;message="Autonomous AI: "+action+"; releasing walking controls";
            return new ExploreCommand{Stop=true};
        }
        private void Launch() {
            launchPending=false;done=false;failure=null;
            trial=new ChestTrial(directory);
            trial.Report=delegate(string text){message="Autonomous AI: "+text;};
            worker=new Thread(delegate(){
                try {
                    execute(trial,kind,actor,offer,goal);
                }catch(Exception error){failure=error is OperationCanceledException?"Action cancelled":error.Message;}
                finally {done=true;}
            });worker.IsBackground=true;worker.Start();
        }
        internal ExploreCommand Tick(MapSnapshot map,long now) {
            if(!running)return new ExploreCommand();
            if(now<lastNow||now-started>15*60*1000)return Halt("Autonomous AI stopped: session time limit or clock change.");
            lastNow=now;
            if(!map.IsLive)return Halt("Autonomous AI stopped: stale map.");
            if(map.Live.navigation_ai!=null&&map.Live.navigation_ai.manual_inputs!=manual)
                return Halt("Autonomous AI stopped: manual input.");
            if(Busy)return new ExploreCommand();
            if(worker!=null) {
                worker.Join();worker=null;trial=null;
                if(failure!=null)return Halt("Autonomous AI stopped: "+failure);
            }
            if(launchPending){Launch();return new ExploreCommand();}
            if(DialogueFlow.Active(map))return Prepare("dialogue",0,null,null);
            if(resume) {
                if(!map.Live.clearing_active)return new ExploreCommand();
                exits.ResumeAfterAction(map,now);resume=false;
            }
            if(exits.OwnsRoom(map)&&map.Live.clearing_active&&map.Live.progression!=null) {
                foreach(var node in OrderedObjectives(map)) {
                    string key=map.Live.level+":"+map.Live.generation+":"+node.address;
                    var reward=UsefulOffer(node);
                    key+=reward==null?":chest":":offer:"+reward.action;
                    if(attempted.Contains(key))continue;
                    if(reward!=null) {
                        attempted.Add(key);return Prepare("NPC reward",node.address,reward,null);
                    }
                    if(node.action=="collect"&&node.kind=="key"&&node.status=="present") {
                        attempted.Add(key);return Prepare("key pickup",node.address,null,null);
                    }
                    var inv=map.Live.progression.inventory;
                    if(node.action=="open_chest"&&node.reward_weapon>=0&&node.reward_weapon<15&&
                       inv!=null&&inv.known&&inv.weapons_mask.HasValue&&(inv.weapons_mask.Value&(1<<node.reward_weapon))==0) {
                        attempted.Add(key);return Prepare("weapon chest",node.address,null,null);
                    }
                }
            }
            var command=exits.Tick(map,now);
            if(!exits.Running&&exits.Status.Contains("no reachable forward exits")) {
                foreach(var marker in map.Live.exits) {
                    string key="jump:"+map.Live.level+":"+map.Live.generation+":"+NavigationExplorer.ExitKey(marker);
                    if(exits.IsArrival(map.Live.level,marker)||attempted.Contains(key))continue;
                    if(!BoxJumpPlanner.NeedsPlatformTraversal(map,new HeightPoint(marker.position)))continue;
                    attempted.Add(key);return Prepare("platform route",0,null,marker.position);
                }
            }
            running=exits.Running;return command;
        }
    }
}
