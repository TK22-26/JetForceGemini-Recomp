using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Runtime.Serialization;
using System.Runtime.Serialization.Json;

namespace JfgLauncher {
    [DataContract] internal sealed class ExploreExit {
        [DataMember] internal string key = "", blocked = "", blockedContext = "";
        [DataMember] internal uint? destination = null;
        [DataMember] internal int attempts = 0, traversals = 0;
        [DataMember] internal float[] position = null;
        [DataMember] internal int rawDestination = 0;
        [DataMember] internal bool absent = false;
    }
    [DataContract] internal sealed class ExploreRoom {
        [DataMember] internal uint level = 0;
        [DataMember] internal List<ExploreExit> exits = new List<ExploreExit>();
    }
    [DataContract] internal sealed class ExploreHistory {
        [DataMember] internal int schema = 1, unlockRevision = 0;
        [DataMember] internal List<ExploreRoom> rooms = new List<ExploreRoom>();
        [DataMember] internal List<string> facts = new List<string>();
        [DataMember] internal uint arrivalLevel = 0;
        [DataMember] internal long arrivalGeneration = -1;
        [DataMember] internal List<string> arrivalKeys = new List<string>();
    }
    internal sealed class ExploreCommand {
        internal NavigationRoute Route;
        internal bool Stop, Confirm;
    }

    // Decisions use observed directed transitions, never an assumed reverse edge
    // or raw destination code. History belongs to one game run/export directory.
    internal sealed class NavigationExplorer {
        internal ExploreHistory History = new ExploreHistory();
        internal bool Running { get; private set; }
        internal string Status { get; private set; }
        internal bool Dirty { get; private set; }
        internal bool MayHeartbeat { get { return Running && pending != null && pending.Nonce != 0 && pending.RetryAt==0 && !suspended && completedAt == 0; } }
        internal string TargetKey { get { return pending == null ? null : pending.Exit.key; } }
        private readonly Func<MapSnapshot, MapMarker, NavigationRoute> planner;
        private sealed class Pending {
            internal ExploreExit Exit;
            internal long Nonce, Started;
            internal bool Acknowledged, ConfirmationSent;
            internal int Waypoint = -1;
            internal long ProgressAt, RetryAt, FirstStarted;
            internal int Recoveries;
            internal float[] RecoveryPosition;
            internal long RecoveryStableSince, RecoveryUpdate=-1, RecoveryStarted;
            internal float BestDistance = Single.MaxValue;
            internal NavigationRoute Route;
        }
        private Pending pending;
        private ExploreRoom room;
        private long generation, lastUpdate, lastStamp, started, lastNow, completedAt, waitAt, nextPlan, manualInputs;
        private long candidateGeneration=-1,candidateSince;
        private uint candidateLevel;
        private int transitions, revisits;
        private bool suspended, settling, scriptedWaiting;
        private float[] lastPosition;
        private string context = "";
        private readonly HashSet<string> arrivals = new HashSet<string>();
        private readonly Dictionary<string,int> segmentVisits = new Dictionary<string,int>();
        internal NavigationExplorer() : this(NavigationRoute.PlanExit) { }
        internal NavigationExplorer(Func<MapSnapshot, MapMarker, NavigationRoute> plan) { planner=plan;Status="Explorer off"; }
        internal static long Clock { get { return (long)(DateTime.UtcNow-new DateTime(1970,1,1,0,0,0,DateTimeKind.Utc)).TotalMilliseconds; } }
        private static float Distance(float[] a,float[] b) {
            float dx=a[0]-b[0],dy=a[1]-b[1],dz=a[2]-b[2];return (float)Math.Sqrt(dx*dx+dy*dy+dz*dz);
        }
        private static string PositionKey(float[] p) {
            MapSnapshot.Point(p);string result="";
            foreach(float v in p) {
                if(Math.Abs(v)>1000000)throw new InvalidDataException("Exit coordinate outside supported range.");
                result+=(result.Length==0?"":",")+Math.Round(v*2,MidpointRounding.AwayFromZero).ToString(CultureInfo.InvariantCulture);
            }
            return result;
        }
        internal static string ExitKey(MapMarker exit) {
            // Actor addresses and array indices are not stable across room loads.
            return exit.destination_code.ToString(CultureInfo.InvariantCulture)+":"+PositionKey(exit.position)+":"+
                (exit.normal==null?"?":PositionKey(exit.normal));
        }
        private ExploreRoom FindRoom(uint level) { return History.rooms.Find(delegate(ExploreRoom r){return r.level==level;}); }
        private bool IsBlocked(ExploreExit exit) { return exit.absent || (exit.blocked.Length!=0 && exit.blockedContext==context); }
        private void Progress() { revisits=0;segmentVisits.Clear(); }
        private void ObserveProgress(MapSnapshot snapshot) {
            MapProgression progress=snapshot.Live.progression;
            string character="unknown";
            HashSet<string> facts=new HashSet<string>(History.facts);
            if(progress!=null && progress.inventory!=null && progress.inventory.known) {
                MapInventory inventory=progress.inventory;character=inventory.character.ToString();
                if(inventory.red_key==true)facts.Add("key:red:"+character);
                int weapons=inventory.weapons_mask.GetValueOrDefault();
                for(int i=0;i<16;i++)if((weapons&(1<<i))!=0)facts.Add("weapon:"+character+":"+i);
                foreach(MapInteraction node in progress.nodes) {
                    if(node.status=="activated" || node.status=="key_lock_cleared")
                        facts.Add("gate:"+snapshot.Live.level+":"+PositionKey(node.position)+":"+node.status);
                    if(node.offers==null)continue;
                    foreach(MapNpcOffer offer in node.offers) {
                        if(offer.status=="owned")facts.Add("owned:"+character+":"+offer.id);
                        if(offer.conditions!=null)foreach(MapNpcCondition condition in offer.conditions)
                            if(condition.domain=="prerequisite" && condition.state=="met")
                                facts.Add("prerequisite:"+character+":"+offer.id+":"+condition.id);
                    }
                }
            }
            var tracker=snapshot.Live.inventory_tracker;
            if(tracker!=null&&tracker.known) {
                tracker.Validate();
                foreach(var c in tracker.characters)
                    for(int i=0;i<c.items.Length;i++)if(c.items[i])facts.Add("item:"+c.id+":"+i);
                for(int i=0;i<tracker.shared.Length;i++)if(tracker.shared[i])facts.Add("shared:"+i);
            }
            if(facts.Count>8192)throw new InvalidDataException("Exploration progress history is full.");
            if(facts.Count!=History.facts.Count) {
                History.facts=new List<string>(facts);History.facts.Sort(StringComparer.Ordinal);
                ++History.unlockRevision;Dirty=true;Progress();
            }
            context=character+":"+History.unlockRevision;
        }
        private void ObserveRoom(MapSnapshot snapshot,bool arrived) {
            ExploreRoom found=FindRoom(snapshot.Live.level);
            if(found==null) {
                if(History.rooms.Count>=512)throw new InvalidDataException("Exploration room history is full.");
                found=new ExploreRoom {level=snapshot.Live.level};History.rooms.Add(found);Dirty=true;Progress();
            }
            room=found;ObserveProgress(snapshot);
            if(snapshot.Live.exits.Length>64)throw new InvalidDataException("Too many exits for automatic exploration.");
            HashSet<string> keys=new HashSet<string>();
            MapMarker nearestArrival=null;float arrivalDistance=400;
            if(arrived) {
                arrivals.Clear();
                if(History.arrivalLevel==snapshot.Live.level && History.arrivalGeneration==snapshot.Live.generation)
                    foreach(string key in History.arrivalKeys)arrivals.Add(key);
                foreach(MapMarker marker in snapshot.Live.exits) {
                    float distance=Distance(marker.position,snapshot.Live.player.position);
                    if(distance<arrivalDistance){arrivalDistance=distance;nearestArrival=marker;}
                }
            }
            foreach(MapMarker marker in snapshot.Live.exits) {
                string key=ExitKey(marker);
                if(!keys.Add(key))throw new InvalidDataException("Ambiguous duplicate exits; choose manually.");
                ExploreExit exit=room.exits.Find(delegate(ExploreExit e){return e.key==key;});
                if(exit==null) {
                    int total=0;foreach(ExploreRoom remembered in History.rooms)total+=remembered.exits.Count;
                    if(total>=8192)throw new InvalidDataException("Exploration exit history is full.");
                    if(room.exits.Count>=64)throw new InvalidDataException("Room exit history is full.");
                    exit=new ExploreExit {key=key,position=(float[])marker.position.Clone(),rawDestination=marker.destination_code};
                    room.exits.Add(exit);Dirty=true;
                }
                // A nearby arrival doorway is only a candidate return route.
                if(arrived && marker==nearestArrival && (History.arrivalLevel!=snapshot.Live.level || History.arrivalGeneration!=snapshot.Live.generation))arrivals.Add(key);
            }
            if(arrived) {
                History.arrivalLevel=snapshot.Live.level;History.arrivalGeneration=snapshot.Live.generation;
                History.arrivalKeys=new List<string>(arrivals);Dirty=true;
            }
            foreach(ExploreExit exit in room.exits) {
                bool absent=!keys.Contains(exit.key);
                if(absent!=exit.absent){exit.absent=absent;Dirty=true;}
            }
            generation=snapshot.Live.generation;lastUpdate=snapshot.Live.update;lastStamp=snapshot.Live.timestamp_ms;
            lastPosition=(float[])snapshot.Live.player.position.Clone();
        }
        private static bool Fresh(MapSnapshot snapshot,long now) {
            return snapshot!=null && snapshot.Live!=null && snapshot.Live.player!=null && snapshot.Live.mesh_ready &&
                snapshot.Live.timestamp_ms<=now && now-snapshot.Live.timestamp_ms<=5000;
        }
        internal void ObserveIdle(MapSnapshot snapshot,long now) {
            if(!Running && Fresh(snapshot,now) && snapshot.Live.clearing_active)
                ObserveRoom(snapshot,room==null || room.level!=snapshot.Live.level || generation!=snapshot.Live.generation);
        }
        internal void RetryRoom(MapSnapshot snapshot,long now) {
            Stop("Explorer stopped");
            if(!Fresh(snapshot,now) || !snapshot.Live.clearing_active || snapshot.Live.transition_confirm)
                throw new InvalidDataException("Return to active gameplay before retrying exits.");
            ObserveRoom(snapshot,true);
            foreach(ExploreExit exit in room.exits){exit.blocked="";exit.blockedContext="";}
            Dirty=true;Status="Room failures cleared; select Explore automatically to retry";
        }
        internal void Start(MapSnapshot snapshot,long now) {
            Stop("Explorer off");
            if(!Fresh(snapshot,now) || (!snapshot.Live.clearing_active&&!DialogueFlow.Active(snapshot)) || snapshot.Live.transition_confirm)throw new InvalidDataException("Enter active gameplay and finish any transition prompt before exploring.");
            if(snapshot.Live.exits==null)throw new InvalidDataException("Exit data unavailable.");
            ObserveRoom(snapshot,room==null || room.level!=snapshot.Live.level || generation!=snapshot.Live.generation);manualInputs=snapshot.Live.navigation_ai==null?0:snapshot.Live.navigation_ai.manual_inputs;started=lastNow=now;transitions=revisits=0;segmentVisits.Clear();
            nextPlan=now;suspended=scriptedWaiting=false;waitAt=completedAt=0;Running=true;Status="Explorer: choosing an untried exit";
        }
        internal void Stop(string reason) { Running=false;pending=null;suspended=settling=scriptedWaiting=false;candidateGeneration=-1;completedAt=waitAt=0;Status=reason; }
        private ExploreCommand Halt(string reason) { Stop(reason);return new ExploreCommand {Stop=true}; }
        internal bool OwnsRoom(MapSnapshot snapshot) {return room!=null&&room.level==snapshot.Live.level&&generation==snapshot.Live.generation;}
        internal bool IsArrival(uint level,MapMarker marker) {
            return History.arrivalLevel==level&&History.arrivalKeys.Contains(ExitKey(marker));
        }
        internal void ResumeAfterAction(MapSnapshot snapshot,long now) {
            if(!OwnsRoom(snapshot)) {lastStamp=now;return;}
            ObserveRoom(snapshot,false);pending=null;completedAt=waitAt=0;
            suspended=settling=scriptedWaiting=false;candidateGeneration=-1;
            nextPlan=now;lastNow=now;Running=true;Status="Explorer: action confirmed; replanning";
        }
        internal void Dispatched(long nonce,long now) {
            if(!Running || pending==null || nonce<=0)throw new InvalidOperationException("No exploration route awaiting dispatch.");
            pending.Nonce=nonce;pending.Started=now;
        }
        private bool NearPending() { return pending!=null && lastPosition!=null && Distance(lastPosition,pending.Exit.position)<=200; }
        internal ExploreCommand MissingMap(long now) {
            if(!Running)return new ExploreCommand();
            if(!NearPending())return Halt("Explorer stopped: map updates unavailable");
            if(waitAt==0)waitAt=now;
            suspended=true;Status="Explorer: waiting for the destination room";
            if(now<lastNow || now-waitAt>20000)return Halt("Explorer stopped: room transition not confirmed");
            lastNow=now;return new ExploreCommand {Stop=true};
        }
        private void Block(ExploreExit exit,string reason) {
            exit.blocked=reason.Length>240?reason.Substring(0,240):reason;exit.blockedContext=context;Dirty=true;
        }
        private ExploreCommand Failed(string reason,long now) {
            Block(pending.Exit,reason);pending=null;completedAt=waitAt=0;suspended=false;candidateGeneration=-1;nextPlan=now+500;
            Status="Explorer: blocked - "+reason+"; checking another exit";
            return new ExploreCommand {Stop=true};
        }
        private ExploreCommand Recover(string reason,long now) {
            if(pending==null)return Halt("Explorer stopped: "+reason);
            if(pending.RetryAt!=0)return new ExploreCommand {Stop=true};
            if(pending.Recoveries>=4 || now-pending.FirstStarted>120000)
                return Failed("Local recovery limit: "+reason,now);
            ++pending.Recoveries;pending.RetryAt=now+650;pending.Nonce=0;
            pending.RecoveryPosition=null;pending.RecoveryStableSince=0;pending.RecoveryUpdate=-1;pending.RecoveryStarted=now;
            completedAt=waitAt=0;suspended=false;
            Status="Explorer: stopped movement; replanning "+ExitLabel(pending.Exit)+" (recovery "+pending.Recoveries+"/4): "+reason;
            return new ExploreCommand {Stop=true};
        }
        internal ExploreCommand RouteBlocked(string reason,long now) {
            if(!Running || pending==null)return Halt("Explorer stopped: "+reason);
            return Recover(reason,now);
        }
        private bool HasFrontier(ExploreRoom target) {
            foreach(ExploreExit exit in target.exits)if(!exit.destination.HasValue && !IsBlocked(exit))return true;
            return false;
        }
        private int FrontierDistance(uint destination) {
            Queue<uint> queue=new Queue<uint>();Queue<int> distances=new Queue<int>();HashSet<uint> seen=new HashSet<uint>();
            queue.Enqueue(destination);distances.Enqueue(0);seen.Add(room.level);seen.Add(destination);
            while(queue.Count!=0) {
                uint level=queue.Dequeue();int distance=distances.Dequeue();ExploreRoom target=FindRoom(level);
                if(target==null)continue;if(target!=room && HasFrontier(target))return distance;
                foreach(ExploreExit exit in target.exits)if(exit.destination.HasValue && !IsBlocked(exit) && seen.Add(exit.destination.Value)) {
                    queue.Enqueue(exit.destination.Value);distances.Enqueue(distance+1);
                }
            }
            return -1;
        }
        private MapMarker Choose(MapSnapshot snapshot) {
            MapMarker best=null;double bestScore=Double.MaxValue;
            foreach(MapMarker marker in snapshot.Live.exits) {
                string key=ExitKey(marker);ExploreExit exit=room.exits.Find(delegate(ExploreExit e){return e.key==key;});
                if(exit==null || IsBlocked(exit))continue;
                double score;
                if(!exit.destination.HasValue) {
                    // Probe an arrival door only after forward exploration. Its
                    // reverse destination is unknown until an actual transition.
                    if(arrivals.Contains(key)) {
                        score=200000000;
                    } else score=0;
                }
                else {
                    if(exit.destination.Value==room.level)continue;
                    int distance=FrontierDistance(exit.destination.Value);if(distance<0)continue;
                    // Confirmed backtracking beats probing a suspected entrance.
                    score=100000000+distance*1000000;
                }
                score+=Math.Min(999999,Distance(marker.position,snapshot.Live.player.position));
                if(score<bestScore || (score==bestScore && String.CompareOrdinal(key,ExitKey(best))<0)){best=marker;bestScore=score;}
            }
            return best;
        }
        internal ExploreCommand Tick(MapSnapshot snapshot,long now) {
            if(!Running)return new ExploreCommand();
            if(now<lastNow || now-started>15*60*1000)return Halt("Explorer stopped: run time limit or clock change");
            lastNow=now;
            if(!Fresh(snapshot,now))return Halt("Explorer stopped: stale map updates");
            if(snapshot.Live.navigation_ai!=null && snapshot.Live.navigation_ai.manual_inputs!=manualInputs)
                return Halt("Explorer stopped: manual input detected");
            bool changed=snapshot.Live.level!=room.level || snapshot.Live.generation!=generation;
            if(snapshot.Live.generation<generation || (!changed && snapshot.Live.update<lastUpdate))return Halt("Explorer stopped: game state rewound");
            if(changed) {
                // A load/menu/teleport away from the target must not invent a connection.
                if(pending==null || !pending.Acknowledged || !NearPending() || now-lastStamp>20000)
                    return Halt("Explorer stopped: unexpected room change; connection not recorded");
                // Generation invalidation happens at mainChangeLevel entry, before
                // a different room is loaded. It is not transition success by itself.
                if(waitAt==0)waitAt=now;
                suspended=true;
                if(snapshot.Live.transition_confirm && !pending.ConfirmationSent) {
                    pending.ConfirmationSent=true;Status="Explorer: confirming the Area Cleared screen";
                    return new ExploreCommand {Stop=true,Confirm=true};
                }
                if(snapshot.Live.level==room.level) {
                    Status="Explorer: waiting for a different room to load";
                    if(now-waitAt>=10000) {
                        ObserveRoom(snapshot,true);
                        return Failed("Room reload did not confirm a different destination",now);
                    }
                    return new ExploreCommand {Stop=true};
                }
                if(candidateGeneration!=snapshot.Live.generation || candidateLevel!=snapshot.Live.level) {
                    candidateGeneration=snapshot.Live.generation;candidateLevel=snapshot.Live.level;candidateSince=now;
                }
                if(!snapshot.Live.clearing_active || now-candidateSince<600) {
                    Status="Explorer: waiting for stable destination gameplay";return new ExploreCommand {Stop=true};
                }
                ExploreExit edge=pending.Exit;uint destination=snapshot.Live.level;
                if(edge.destination.HasValue && edge.destination.Value!=destination)
                    return Halt("Explorer stopped: exit destination changed; inspect manually");
                if(FindRoom(destination)==null && History.rooms.Count>=512)return Halt("Explorer stopped: room history is full");
                bool newEdge=!edge.destination.HasValue;edge.destination=destination;++edge.traversals;Dirty=true;
                if(newEdge)Progress();else ++revisits;
                string segment=room.level+":"+edge.key;int visits;segmentVisits.TryGetValue(segment,out visits);segmentVisits[segment]=++visits;
                if(destination==room.level)Block(edge,"Returned to the same room");
                pending=null;completedAt=waitAt=0;suspended=scriptedWaiting=false;++transitions;
                ObserveRoom(snapshot,true);nextPlan=now+600;settling=!snapshot.Live.clearing_active;if(settling)waitAt=now;
                if(transitions>=128 || revisits>=Math.Min(64,Math.Max(8,History.rooms.Count*2)) || (segmentVisits.TryGetValue(segment,out visits) && visits>3))
                    return Halt("Explorer stopped: repeated transitions without new progress");
                Status="Explorer: confirmed arrival in room "+destination+"; choosing the next route";
                return new ExploreCommand {Stop=true};
            }
            ObserveRoom(snapshot,false);
            if(settling) {
                if(!snapshot.Live.clearing_active) {
                    if(now-waitAt>20000)return Halt("Explorer stopped: destination controls remained suspended");
                    Status="Explorer: waiting for destination gameplay";return new ExploreCommand();
                }
                settling=false;waitAt=0;
            }
            if(!snapshot.Live.clearing_active && pending!=null && (snapshot.Live.scripted_camera || scriptedWaiting)) {
                if(!scriptedWaiting)waitAt=now;
                scriptedWaiting=suspended=true;
                if(now-waitAt>15000)return Halt("Explorer stopped: scripted camera did not return control");
                Status="Explorer: waiting for the scripted camera; movement released";
                return new ExploreCommand {Stop=true};
            }
            if(scriptedWaiting && snapshot.Live.clearing_active) {
                scriptedWaiting=suspended=false;
                return Recover("Scripted camera finished; checking the route again",now);
            }
            if(!snapshot.Live.clearing_active) {
                if(!NearPending())return Halt("Explorer stopped: gameplay controls suspended");
                if(waitAt==0)waitAt=now;suspended=true;Status="Explorer: waiting for a room transition";
                if(now-waitAt>20000)return Halt("Explorer stopped: controls remained suspended");
                return new ExploreCommand {Stop=true};
            }
            if(suspended)return Halt("Explorer stopped: controls resumed in the same room; restart explicitly");
            if(pending!=null) {
                if(pending.RetryAt!=0) {
                    if(now-pending.RecoveryStarted>7000)return Failed("Player did not settle before replanning",now);
                    if(snapshot.Live.navigation_ai!=null && snapshot.Live.navigation_ai.active)return new ExploreCommand();
                    if(pending.RecoveryUpdate==snapshot.Live.update)return new ExploreCommand();
                    pending.RecoveryUpdate=snapshot.Live.update;
                    float[] position=snapshot.Live.player.position;
                    if(pending.RecoveryPosition==null || Distance(position,pending.RecoveryPosition)>2)pending.RecoveryStableSince=now;
                    pending.RecoveryPosition=(float[])position.Clone();
                    if(now<pending.RetryAt || now-pending.RecoveryStableSince<400)return new ExploreCommand();
                    MapMarker target=Array.Find(snapshot.Live.exits,delegate(MapMarker e){return ExitKey(e)==pending.Exit.key;});
                    if(target==null)return Failed("Exit disappeared during local recovery",now);
                    try {
                        NavigationRoute replacement=planner(snapshot,target);
                        if(replacement==null || replacement.Points.Count==0)throw new InvalidDataException("Empty recovery route");
                        pending.Route=replacement;pending.RetryAt=0;pending.Acknowledged=false;pending.Waypoint=-1;
                        pending.BestDistance=Single.MaxValue;pending.ProgressAt=now;
                        Status="Explorer: resuming "+ExitLabel(pending.Exit)+" after local recovery "+pending.Recoveries+"/4";
                        return new ExploreCommand {Route=replacement};
                    }catch(InvalidDataException error){return Failed("Replan from current position failed: "+error.Message,now);}
                }
                MapAi ai=snapshot.Live.navigation_ai;
                if(pending.Nonce==0)return Halt("Explorer stopped: movement command was not dispatched");
                if(now-pending.FirstStarted>120000)return Failed("Movement time limit",now);
                if(ai!=null && ai.nonce==pending.Nonce) {
                    pending.Acknowledged=true;
                    if(ai.active){
                        if(ai.waypoint>=0 && ai.waypoint<pending.Route.Points.Count) {
                            HeightPoint goal=pending.Route.Points[ai.waypoint];
                            float[] pos=snapshot.Live.player.position;
                            float distance=(float)Math.Sqrt((pos[0]-goal.X)*(pos[0]-goal.X)+(pos[2]-goal.Z)*(pos[2]-goal.Z));
                            if(pending.Waypoint!=ai.waypoint || distance<pending.BestDistance-3) {
                                pending.Waypoint=ai.waypoint;pending.BestDistance=distance;pending.ProgressAt=now;
                            }
                            long allowance=ai.state=="jump_assist"?3500:1800;
                            if(pending.ProgressAt!=0 && now-pending.ProgressAt>allowance)
                                return Recover("No progress toward waypoint; possible wall or gate",now);
                        }
                        Status="Explorer: "+ai.state.Replace('_',' ')+" toward "+ExitLabel(pending.Exit);return new ExploreCommand();
                    }
                    if(ai.state=="approach_complete") {
                        if(completedAt==0)completedAt=now;
                        if(pending.Route.ApproachOnly) {
                            if(pending.Route.GateCleared(snapshot)) {
                                MapMarker marker=Array.Find(snapshot.Live.exits,delegate(MapMarker e){return ExitKey(e)==pending.Exit.key;});
                                if(marker==null)return Failed("Exit disappeared while waiting at door",now);
                                try {
                                    NavigationRoute next=planner(snapshot,marker);
                                    if(next.ApproachOnly)return Failed("Door changed but exit passage is still blocked",now);
                                    pending.Route=next;pending.Nonce=0;pending.Acknowledged=false;pending.Waypoint=-1;
                                    pending.BestDistance=Single.MaxValue;pending.ProgressAt=now;completedAt=0;
                                    Status="Explorer: door cleared; continuing through "+ExitLabel(pending.Exit);
                                    return new ExploreCommand {Route=next};
                                }catch(InvalidDataException error){return Failed(error.Message,now);}
                            }
                            Status="Explorer: at door for "+ExitLabel(pending.Exit)+"; waiting for it to open";
                            if(now-completedAt>=8000)return Failed("Reached door; check key, switch or other opening requirement",now);
                            return new ExploreCommand();
                        }
                        Status="Explorer: at doorway; waiting to confirm a room change";
                        if(now-completedAt>=2500)return Failed("Doorway reached but no transition; gate, trigger or traversal needs checking",now);
                        return new ExploreCommand();
                    }
                    if(ai.state=="blocked_needs_manual" || ai.state=="calibration_blocked" || ai.state=="calibration_uncertain" || ai.state=="route_deviation")
                        return Recover(ai.state.Replace('_',' '),now);
                    if(ai.state=="jump_timeout" || ai.state=="time_limit")return Failed(ai.state.Replace('_',' '),now);
                    return Halt("Explorer stopped: "+(ai.state??"unknown controller state").Replace('_',' '));
                }
                if(now-pending.Started>3000)return Halt("Explorer stopped: movement controller did not acknowledge the route");
                return new ExploreCommand();
            }
            if(now<nextPlan)return new ExploreCommand();
            MapMarker selected=Choose(snapshot);
            if(selected==null)return Halt("Explorer stopped: no reachable forward exits or useful return routes remain. Check blocked routes or move manually.");
            string selectedKey=ExitKey(selected);ExploreExit chosen=room.exits.Find(delegate(ExploreExit e){return e.key==selectedKey;});
            ++chosen.attempts;Dirty=true;
            try {
                NavigationRoute route=planner(snapshot,selected);
                if(route==null || route.Points.Count==0)throw new InvalidDataException("Empty exit route");
                pending=new Pending {Exit=chosen,Started=now,FirstStarted=now,Route=route,ProgressAt=now};completedAt=0;candidateGeneration=-1;
                Status="Explorer: "+(route.ApproachOnly?"approaching blocked door for ":chosen.destination.HasValue?"following known route via ":"trying ")+ExitLabel(chosen);
                return new ExploreCommand {Route=route};
            } catch(InvalidDataException error) {
                Block(chosen,error.Message);nextPlan=now+300;Status="Explorer: no surface route to "+ExitLabel(chosen)+"; checking another exit";
                return new ExploreCommand();
            }
        }
        private string ExitLabel(ExploreExit exit) { return "exit "+(room.exits.IndexOf(exit)+1)+" in room "+room.level; }
        internal string Describe(uint level,MapMarker marker) {
            ExploreRoom target=FindRoom(level);string key=ExitKey(marker);
            ExploreExit exit=target==null?null:target.exits.Find(delegate(ExploreExit e){return e.key==key;});
            if(exit==null)return "Untried";
            if(exit.absent)return "Unavailable in last room snapshot";
            if(room==target && pending!=null && pending.Exit==exit && pending.RetryAt!=0)return "Local recovery toward this exit";
            if(room==target && pending!=null && pending.Exit==exit && pending.Route.ApproachOnly)return "Door approach - waiting for clearance before crossing";
            if(IsBlocked(exit))return "Blocked: "+exit.blocked;
            if(exit.destination.HasValue)return "Confirmed -> room "+exit.destination.Value;
            if(room==target && arrivals.Contains(key))return "Return route candidate - used after local objectives and forward exits";
            return exit.blocked.Length==0?"Untried":"Retry available after progress change";
        }
        internal void Save(string directory) {
            if(!Dirty)return;
            string path=Path.Combine(directory,"exploration-history.json"),temp=path+".tmp";
            using(FileStream output=File.Create(temp))new DataContractJsonSerializer(typeof(ExploreHistory)).WriteObject(output,History);
            if(File.Exists(path))File.Replace(temp,path,null);else File.Move(temp,path);Dirty=false;
        }
        internal static NavigationExplorer Load(string directory) {
            NavigationExplorer explorer=new NavigationExplorer();string path=Path.Combine(directory,"exploration-history.json");
            if(!File.Exists(path))return explorer;
            try {
                using(FileStream input=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.Read)) {
                    if(input.Length>4*1024*1024)throw new InvalidDataException("Exploration history is too large.");
                    explorer.History=(ExploreHistory)new DataContractJsonSerializer(typeof(ExploreHistory)).ReadObject(input);
                }
                ExploreHistory h=explorer.History;
                if(h!=null && h.arrivalKeys==null)h.arrivalKeys=new List<string>();
                if(h!=null && (h.arrivalKeys.Count>64 || h.arrivalKeys.Exists(delegate(string key){return String.IsNullOrEmpty(key)||key.Length>256;})))
                    throw new InvalidDataException("Invalid arrival history.");
                if(h==null || h.schema!=1 || h.rooms==null || h.rooms.Count>512 || h.facts==null || h.facts.Count>8192 || h.unlockRevision<0 || h.unlockRevision>100000)
                    throw new InvalidDataException("Unsupported exploration history.");
                HashSet<uint> levels=new HashSet<uint>();HashSet<string> facts=new HashSet<string>();int count=0;
                foreach(string fact in h.facts)if(String.IsNullOrEmpty(fact)||fact.Length>512||!facts.Add(fact))throw new InvalidDataException("Invalid exploration progress.");
                foreach(ExploreRoom r in h.rooms) {
                    if(r==null || !levels.Add(r.level) || r.exits==null || r.exits.Count>64)throw new InvalidDataException("Invalid room history.");
                    HashSet<string> keys=new HashSet<string>();count+=r.exits.Count;
                    foreach(ExploreExit e in r.exits) {
                        if(e==null || String.IsNullOrEmpty(e.key) || e.key.Length>256 || !keys.Add(e.key) || e.blocked==null || e.blocked.Length>240 ||
                            e.blockedContext==null || e.blockedContext.Length>64 || e.attempts<0 || e.traversals<0)
                            throw new InvalidDataException("Invalid exit history.");
                        PositionKey(e.position);
                    }
                }
                if(count>8192)throw new InvalidDataException("Too many remembered exits.");
                foreach(ExploreRoom r in h.rooms)foreach(ExploreExit e in r.exits)
                    if(e.destination.HasValue && !levels.Contains(e.destination.Value))throw new InvalidDataException("Unknown remembered destination.");
                explorer.Status="Explorer off - remembered "+h.rooms.Count+" rooms";return explorer;
            } catch(SerializationException error) { throw new InvalidDataException("Invalid exploration history JSON.",error); }
        }
    }
}
