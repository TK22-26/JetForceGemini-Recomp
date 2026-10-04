using System;
using System.Collections.Generic;
using System.IO;
using System.Globalization;
using System.Text;
using System.Threading;

namespace JfgLauncher {
    // A platform goal is a request for measured traversal, never a walking
    // shortcut. Only NavigationRunner may execute it after calibration/arc checks.
    internal static class NavigationPlanner {
        private static NavigationRoute Platforms(MapSnapshot map,HeightPoint goal,string failure) {
            if(!BoxJumpPlanner.NeedsPlatformTraversal(map,goal))
                throw new InvalidDataException(failure);
            if(map.Live.progression!=null&&map.Live.progression.inventory!=null&&map.Live.progression.inventory.character==2)
                throw new InvalidDataException("Lupus hover traversal needs a verified movement profile.");
            float floor;
            if(!BoxJumpPlanner.Floor(map.Mesh,goal.X,goal.Z,goal.Y,180,out floor))
                throw new InvalidDataException("Destination has no supported landing surface.");
            goal.Y=floor+BoxJumpPlanner.Offset(map);
            var route=new NavigationRoute{Level=map.Live.level,Generation=map.Live.generation,PlatformGoal=goal};
            route.Points.Add(goal);return route;
        }
        internal static NavigationRoute ToPoint(MapSnapshot map,HeightPoint goal) {
            try{return NavigationRoute.Plan(map,new[]{goal.X,goal.Y,goal.Z});}
            catch(InvalidDataException error){return Platforms(map,goal,error.Message);}
        }
        internal static NavigationRoute ToExit(MapSnapshot map,MapMarker exit) {
            string requirement=NavigationRoute.ExitRequirement(map,exit);
            if(requirement!=null)throw new InvalidDataException(requirement);
            NavigationRoute route;
            try{route=NavigationRoute.PlanExit(map,exit);}
            catch(InvalidDataException error){route=Platforms(map,new HeightPoint(exit.position),error.Message);}
            route.ExitTarget=exit;return route;
        }
        internal static List<ChestApproach> NpcApproaches(MapSnapshot map,MapInteraction npc) {
            if(npc==null||npc.talk_radius<=8)throw new InvalidDataException("NPC conversation bounds are unavailable.");
            var result=new List<ChestApproach>();var centre=new HeightPoint(npc.position);
            var pos=new HeightPoint(map.Live.player.position);
            float dx=pos.X-centre.X,dz=pos.Z-centre.Z,len=(float)Math.Sqrt(dx*dx+dz*dz);
            if(len<1){dx=0;dz=1;len=1;}dx/=len;dz/=len;
            for(int sample=0;sample<12;sample++) {
                double angle=sample*Math.PI/6;
                float x=(float)(dx*Math.Cos(angle)-dz*Math.Sin(angle)),z=(float)(dx*Math.Sin(angle)+dz*Math.Cos(angle));
                float radius=Math.Max(10,npc.talk_radius*.55f),floor;
                var target=new HeightPoint(centre.X+x*radius,centre.Y,centre.Z+z*radius);
                if(!BoxJumpPlanner.Floor(map.Mesh,target.X,target.Z,centre.Y,64,out floor))continue;
                target.Y=floor+BoxJumpPlanner.Offset(map);
                if(target.Y-centre.Y<=npc.talk_lower||target.Y-centre.Y>=npc.talk_upper)continue;
                var stage=new HeightPoint(target.X+x*40,target.Y,target.Z+z*40);
                if(!BoxJumpPlanner.Floor(map.Mesh,stage.X,stage.Z,target.Y,24,out floor))continue;
                stage.Y=floor+BoxJumpPlanner.Offset(map);
                if(NavigationRoute.ClearWalk(map,new MapLayers(map.Mesh).Floors,stage,target,0))
                    result.Add(new ChestApproach{Target=target,Staging=stage});
            }
            return result;
        }
    }
    internal sealed class NavigationProgress {
        internal NavigationRoute Route;
        internal long Nonce;
    }
    internal sealed class NavigationTransition : Exception { }
    // One owner writes commands during a trial. Cancellation is checked before
    // each heartbeat, and the worker always emits its final stop after exiting.
    internal sealed class NavigationRunner {
        internal volatile bool Cancelled;
        internal Action<string> Report=delegate {};
        private readonly string directory;
        private MapSnapshot map;
        internal volatile MapSnapshot LastObservation;
        internal volatile NavigationProgress Progress;
        internal volatile NavigationRoute CurrentRoute;
        private MapMarker expectedExit;
        private bool AtExit(MapSnapshot value) {
            return expectedExit!=null&&value!=null&&value.Live.player!=null&&
                BoxJumpPlanner.Horizontal(new HeightPoint(value.Live.player.position),new HeightPoint(expectedExit.position))<200&&
                Math.Abs(value.Live.player.position[1]-expectedExit.position[1])<200;
        }
        private uint level;private long generation,nonce,started,manual;
        private bool bound;
        private uint npcAddress;
        private MapNpcOffer npcOffer;
        private int dialogueSerial;
        internal NavigationRunner(string path){directory=path;nonce=NavigationExplorer.Clock;}
        private MapSnapshot Raw() {
            if(Cancelled)throw new OperationCanceledException();
            var previous=map;
            // Windows export replacement can briefly hide an otherwise live
            // file. Retry only that I/O window, still honoring cancellation.
            for(int retry=0;;retry++)try {
                if(Cancelled)throw new OperationCanceledException();
                map=MapSnapshot.Load(directory,map==null?null:map.Mesh);break;
            }catch(IOException){if(retry>=10)throw;Thread.Sleep(20);}
            if(!map.IsLive)throw new InvalidDataException("Map updates stopped.");
            if(bound&&map.Live.navigation_ai!=null&&map.Live.navigation_ai.manual_inputs!=manual)
                throw new InvalidDataException("Manual input detected; autonomous action stopped.");
            if(bound&&(map.Live.level!=level||map.Live.generation!=generation)) {
                if(AtExit(previous)&&Progress!=null&&previous.Live.navigation_ai!=null&&previous.Live.navigation_ai.nonce==Progress.Nonce)
                    throw new NavigationTransition();
                throw new InvalidDataException("Room changed during an action.");
            }
            if(bound&&NavigationExplorer.Clock-started>180000)throw new InvalidDataException("Action reached its three-minute limit.");
            if(map.Live.player.motion!=null&&map.Live.player.motion.known&&
               (map.Live.player.motion.hang_entry||map.Live.player.motion.grab_entry))
                throw new InvalidDataException("Ledge grab detected; no verified release action.");
            // Publish only a detached observation, never the mutable snapshot
            // temporarily used by the platform search for candidate positions.
            LastObservation=new MapSnapshot{Live=new MapLive{level=map.Live.level,generation=map.Live.generation,
                timestamp_ms=map.Live.timestamp_ms,update=map.Live.update,navigation_ai=map.Live.navigation_ai,
                player=new MapPlayer{position=(float[])map.Live.player.position.Clone()}}};
            if(bound&&AtExit(map)&&!map.Live.clearing_active&&!map.Live.scripted_camera&&!DialogueFlow.Active(map)&&
               Progress!=null&&map.Live.navigation_ai!=null&&map.Live.navigation_ai.nonce==Progress.Nonce)
                throw new NavigationTransition();
            return map;
        }
        private void Bind() {
            BoxJumpPlanner.PlanningCancelled=delegate{return Cancelled;};
            Raw();level=map.Live.level;generation=map.Live.generation;started=NavigationExplorer.Clock;
            manual=map.Live.navigation_ai==null?0:map.Live.navigation_ai.manual_inputs;bound=true;
        }
        private bool RewardOwned() {
            if(npcOffer==null)return false;
            var node=Find(npcAddress);
            if(node.offers!=null)foreach(var value in node.offers)
                if(value.action==npcOffer.action&&value.status=="owned")return true;
            return false;
        }
        private void Dialogue() {
            long deadline=NavigationExplorer.Clock+60000,nextInput=0;int inputs=0;
            Report("Dialogue: waiting for ready text or the selected reward choice...");
            while(NavigationExplorer.Clock<deadline) {
                Raw();
                if(!DialogueFlow.Active(map)) {
                    if(map.Live.clearing_active){++dialogueSerial;return;}
                    Thread.Sleep(100);continue;
                }
                var d=map.Live.dialogue;
                if(d.ready&&NavigationExplorer.Clock>=nextInput) {
                    bool owned=RewardOwned();
                    if(npcOffer!=null&&!owned) {
                        bool available=false;var npc=Find(npcAddress);
                        if(npc.offers!=null)foreach(var value in npc.offers)
                            if(value.action==npcOffer.action&&value.status=="available")available=true;
                        if(!available)throw new InvalidDataException("NPC reward prerequisites changed during dialogue.");
                    }
                    int action=DialogueFlow.Select(d,npcOffer,owned);
                    if(action>=0) {
                        if(++inputs>64)throw new InvalidDataException("Dialogue did not finish within the input limit.");
                        if(Cancelled)throw new OperationCanceledException();
                        DialogueFlow.Send(directory,map.Live,Next(),action);nextInput=NavigationExplorer.Clock+650;
                    }
                }
                Thread.Sleep(100);
            }
            throw new InvalidDataException("Dialogue did not return gameplay control within one minute.");
        }
        private MapSnapshot Read() {
            Raw();if(DialogueFlow.Active(map)){Dialogue();Raw();}
            if(map.Live.scripted_camera&&!map.Live.clearing_active) {
                new NavigationRoute{Level=level,Generation=generation}.Send(directory,Next(),false,true);
                long until=NavigationExplorer.Clock+15000;
                while(map.Live.scripted_camera&&!map.Live.clearing_active&&NavigationExplorer.Clock<until) {
                    Thread.Sleep(100);Raw();if(DialogueFlow.Active(map)){Dialogue();Raw();}
                }
                if(!map.Live.clearing_active)throw new InvalidDataException("Scripted camera did not return controls.");
                ++dialogueSerial;
            }
            BoxJumpPlanner.NeedLive(map);return map;
        }
        private void Finish() {
            CurrentRoute=null;BoxJumpPlanner.PlanningCancelled=null;
            if(bound)try{new NavigationRoute{Level=level,Generation=generation}.Send(directory,Next(),false,true);}
                catch(IOException){}catch(UnauthorizedAccessException){}
            try{File.Delete(Path.Combine(directory,"ai-dialogue.txt"));}catch(IOException){}catch(UnauthorizedAccessException){}
        }
        internal void RunDialogue() {
            try{Bind();Dialogue();Report("Dialogue finished; gameplay control returned.");}
            finally{Finish();}
        }
        private void Traverse(HeightPoint goal,int button) {
            Read();
            var route=expectedExit==null?NavigationPlanner.ToPoint(map,goal):NavigationPlanner.ToExit(map,expectedExit);
            if(!route.PlatformGoal.HasValue){Walk(route);return;}
            goal=route.PlatformGoal.Value;
            if(map.Live.box_jump==null||!map.Live.box_jump.calibrated||map.Live.box_jump.button!=button) {
                Report("Measuring jump capability on the current floor...");Jump(0,null,button);Delay(500);
            }
            var steps=BoxJumpPlanner.Sequence(map,new JumpLanding{Point=goal});
            for(int i=0;i<steps.Count;i++) {
                Report("Platform "+(i+1)+"/"+steps.Count+": approaching takeoff...");
                JumpPlan plan=null;
                for(int retry=0;retry<3;retry++) {
                    Read();var approach=BoxJumpPlanner.Approach(map,steps[i]);
                    if(approach.Walk!=null)Walk(approach.Walk);
                    Delay(800);
                    try{plan=BoxJumpPlanner.Plan(map,steps[i]);break;}catch(InvalidDataException){if(retry==2)throw;}
                }
                Report("Jump "+(i+1)+"/"+steps.Count+"; checking landing state...");Jump(1,plan,button);
            }
            Read();route=expectedExit==null?NavigationPlanner.ToPoint(map,goal):NavigationPlanner.ToExit(map,expectedExit);
            if(route.PlatformGoal.HasValue)throw new InvalidDataException("Landing did not connect to the destination approach.");
            Walk(route);
        }
        internal void RunRoute(NavigationRoute route,int button) {
            try {
                Bind();expectedExit=route.ExitTarget;
                if(route.Level!=level||route.Generation!=generation)throw new InvalidDataException("Room changed before route execution.");
                Traverse(route.Points[route.Points.Count-1],button);
            }catch(NavigationTransition) {
                // Room history independently verifies the destination; this only
                // releases the movement worker at the expected doorway.
                Report("Movement released; waiting for destination confirmation.");
            }finally{Finish();}
        }
        internal void RunTraversal(float[] goal,int button) {
            try{Bind();Traverse(new HeightPoint(goal),button);Report("Platform route complete; replanning exit.");}
            finally{Finish();}
        }
        internal void RunNpc(uint address,MapNpcOffer reward,int button) {
            try {
                Bind();npcAddress=address;npcOffer=reward;
                var npc=Find(address);
                if(AutonomousExplorer.UsefulOffer(npc)==null)throw new InvalidDataException("NPC reward is no longer available.");
                ChestApproach access=null;NavigationRoute route=null;
                foreach(var candidate in NavigationPlanner.NpcApproaches(map,npc)) {
                    try {
                        var proposed=NavigationPlanner.ToPoint(map,candidate.Staging);
                        if(route==null||!proposed.PlatformGoal.HasValue){access=candidate;route=proposed;}
                        if(!proposed.PlatformGoal.HasValue)break;
                    }catch(InvalidDataException){}
                }
                if(route==null)throw new InvalidDataException("No supported approach to NPC "+npc.label+".");
                Report("Approaching "+npc.label+" for "+reward.reward+"...");
                Traverse(access.Staging,button);Delay(600);Interaction(0,access.Target);Delay(300);
                HeightPoint pos;
                for(int attempt=0;attempt<3;attempt++) {
                    Read();if(RewardOwned()){Report("NPC reward confirmed: "+reward.reward);return;}
                    npc=Find(address);pos=new HeightPoint(map.Live.player.position);
                    if(BoxJumpPlanner.Horizontal(pos,new HeightPoint(npc.position))>=npc.talk_radius||
                       pos.Y-npc.position[1]<=npc.talk_lower||pos.Y-npc.position[1]>=npc.talk_upper)
                        throw new InvalidDataException("Player is outside NPC conversation bounds.");
                    Report("Talking to "+npc.label+"; verifying "+reward.reward+"...");
                    Interaction(1,pos);Delay(1500);
                }
                if(!RewardOwned())throw new InvalidDataException("Conversation finished without the expected NPC reward.");
                Report("NPC reward confirmed: "+reward.reward);
            }finally{Finish();}
        }
        private CharacterInventory CurrentItems() {
            var inventory=map.Live.inventory_tracker;
            if(inventory==null||!inventory.known)throw new InvalidDataException("Key pickup needs live inventory telemetry.");
            inventory.Validate();
            foreach(var c in inventory.characters)if(c.id==inventory.current)return c;
            throw new InvalidDataException("Current character inventory is unavailable.");
        }
        internal static bool GainedItem(bool[] before,bool[] after) {
            if(before==null||after==null||before.Length!=after.Length)return false;
            for(int i=0;i<before.Length;i++)if(!before[i]&&after[i])return true;
            return false;
        }
        internal void RunPickup(uint address,int button) {
            try {
                Bind();Read();var node=Find(address);
                if(node.action!="collect"||node.kind!="key")throw new InvalidDataException("Unsupported progression pickup.");
                var initial=CurrentItems();int character=initial.id;var before=(bool[])initial.items.Clone();
                var target=new HeightPoint(node.position);float floor;
                if(!BoxJumpPlanner.Floor(map.Mesh,target.X,target.Z,target.Y,96,out floor))
                    throw new InvalidDataException("Key has no verified supporting floor.");
                target.Y=floor+BoxJumpPlanner.Offset(map);
                Report("Collecting "+node.label+"; checking inventory...");
                Traverse(target,button);Delay(500);
                var current=CurrentItems();
                if(current.id!=character||!GainedItem(before,current.items))
                    throw new InvalidDataException("Pickup approach finished without a new item flag.");
                Report("Key pickup confirmed by inventory.");
            }finally{Finish();}
        }
        private long Next(){return nonce=Math.Max(nonce+1,NavigationExplorer.Clock);}
        private void Delay(int ms) {for(int n=0;n<ms;n+=100){Thread.Sleep(Math.Min(100,ms-n));Read();}}
        private void InteractionSend(int mode,HeightPoint point) {
            if(Cancelled)throw new OperationCanceledException();
            string text=String.Format(CultureInfo.InvariantCulture,"JFGINTERACT1 {0} {1} {2} {3} {4} {5:R} {6:R} {7:R}\n",
                level,generation,nonce,NavigationExplorer.Clock,mode,point.X,point.Y,point.Z);
            string file=Path.Combine(directory,"ai-command.txt"),temp=file+".tmp";
            File.WriteAllText(temp,text,new UTF8Encoding(false));
            for(int i=0;;i++)try{if(File.Exists(file))File.Replace(temp,file,null);else File.Move(temp,file);break;}
                catch(IOException){if(i==5)throw;Thread.Sleep(10);}
                catch(UnauthorizedAccessException){if(i==5)throw;Thread.Sleep(10);}
        }
        private void Interaction(int mode,HeightPoint target) {
            Next();int beforeDialogue=dialogueSerial;long until=NavigationExplorer.Clock+12000;
            while(NavigationExplorer.Clock<until) {
                Read();if(mode==1&&dialogueSerial!=beforeDialogue)return;
                var ai=map.Live.navigation_ai;
                if(ai!=null&&ai.nonce==nonce&&!ai.active) {
                    if(ai.state!=(mode==0?"precision_complete":"action_complete"))
                        throw new InvalidDataException("Interaction stopped: "+ai.state);
                    return;
                }
                if(mode==0&&!NavigationRoute.ClearWalk(map,new MapLayers(map.Mesh).Floors,new HeightPoint(map.Live.player.position),target,0))
                    throw new InvalidDataException("Body clearance changed during interaction approach.");
                InteractionSend(mode,target);Thread.Sleep(100);
            }throw new InvalidDataException("Interaction timed out.");
        }
        private void RecordFailure(NavigationRoute route,string reason) {
            try {
                File.AppendAllText(Path.Combine(directory,"route-events.tsv"),NavigationExplorer.Clock+"\t"+level+"\t"+generation+"\t"+reason.Replace('\n',' ').Replace('\t',' ')+"\n");
                File.Copy(Path.Combine(directory,"live.json"),Path.Combine(directory,"last-route-stop.json"),true);
            }catch(IOException){}catch(UnauthorizedAccessException){}
        }
        private void Walk(NavigationRoute route) {
            var goal=route.Points[route.Points.Count-1];
            for(int retry=0;;retry++)try{WalkAttempt(route);return;}
            catch(InvalidDataException error) {
                if(Cancelled||error.Message.Contains("Manual")||error.Message.Contains("manual_takeover")||
                   error.Message.Contains("Map updates")||error.Message.Contains("Room changed"))throw;
                RecordFailure(route,error.Message);
                new NavigationRoute{Level=level,Generation=generation}.Send(directory,Next(),false,true);
                if(retry>=4)throw new InvalidDataException("Local recovery limit: "+error.Message);
                Report("Movement stopped; settling and replanning ("+(retry+1)+"/4): "+error.Message);
                Delay(700);
                var replacement=NavigationRoute.Plan(map,new[]{goal.X,goal.Y,goal.Z});
                replacement.ApproachGate=route.ApproachGate;replacement.GatePosition=route.GatePosition;replacement.ExitTarget=route.ExitTarget;
                route=replacement;
            }
        }
        private void WalkAttempt(NavigationRoute route) {
            CurrentRoute=route;
            Next();int beforeDialogue=dialogueSerial;long until=NavigationExplorer.Clock+45000;
            long dispatched=NavigationExplorer.Clock,progressAt=dispatched;int waypoint=-1;float best=Single.MaxValue;bool acknowledged=false;
            while(NavigationExplorer.Clock<until) {
                Read();
                if(dialogueSerial!=beforeDialogue) {
                    beforeDialogue=dialogueSerial;var end=route.Points[route.Points.Count-1];
                    var replacement=NavigationRoute.Plan(map,new float[]{end.X,end.Y,end.Z});
                    replacement.ApproachGate=route.ApproachGate;replacement.GatePosition=route.GatePosition;replacement.ExitTarget=route.ExitTarget;
                    route=replacement;CurrentRoute=route;Next();
                    until=NavigationExplorer.Clock+45000;dispatched=progressAt=NavigationExplorer.Clock;waypoint=-1;best=Single.MaxValue;acknowledged=false;
                }
                var ai=map.Live.navigation_ai;
                if(ai!=null&&ai.nonce==nonce) {
                    acknowledged=true;
                    if(!ai.active) {
                        if(ai.state!="approach_complete")throw new InvalidDataException("Walking stopped: "+ai.state);
                        Progress=new NavigationProgress{Route=route,Nonce=nonce};return;
                    }
                    if(ai.waypoint>=0&&ai.waypoint<route.Points.Count) {
                        float distance=BoxJumpPlanner.Horizontal(new HeightPoint(map.Live.player.position),route.Points[ai.waypoint]);
                        if(ai.waypoint!=waypoint||distance<best-3){waypoint=ai.waypoint;best=distance;progressAt=NavigationExplorer.Clock;}
                        if(NavigationExplorer.Clock-progressAt>1800)throw new InvalidDataException("No progress toward waypoint; possible wall or gate.");
                    }
                }
                if(!acknowledged&&NavigationExplorer.Clock-dispatched>3000)throw new InvalidDataException("Movement controller did not acknowledge the route.");
                string problem=route.CheckRemaining(map,ai!=null&&ai.nonce==nonce?ai.waypoint:0);
                if(problem!=null)throw new InvalidDataException(problem);
                if(Cancelled)throw new OperationCanceledException();
                Progress=new NavigationProgress{Route=route,Nonce=nonce};
                route.Send(directory,nonce,false,false);Thread.Sleep(100);
            }throw new InvalidDataException("Walking approach timed out.");
        }
        private void Jump(int mode,JumpPlan plan,int button) {
            CurrentRoute=null;
            Next();long until=NavigationExplorer.Clock+12000;
            HeightPoint target=plan==null?new HeightPoint(map.Live.player.position):plan.Target;
            var action=new NavigationRoute{Level=level,Generation=generation,PlatformGoal=target,ExitTarget=expectedExit};
            action.Points.Add(target);Progress=new NavigationProgress{Route=action,Nonce=nonce};
            while(NavigationExplorer.Clock<until) {
                Read();var jump=map.Live.box_jump;
                if(jump!=null&&jump.nonce==nonce&&!jump.active) {
                    if(mode==0) {if(!jump.calibrated||jump.button!=button)throw new InvalidDataException("Calibration stopped: "+jump.state);}
                    else if(!BoxJumpPlanner.SupportedLanding(map,plan))throw new InvalidDataException("Landing was not confirmed: "+jump.state);
                    return;
                }
                if(plan!=null)BoxJumpPlanner.ValidateArc(map,plan);
                if(Cancelled)throw new OperationCanceledException();
                BoxJumpPlanner.Send(directory,map.Live,nonce,mode,target,plan==null?12:plan.Radius,button,plan==null?0:plan.Lift);
                Thread.Sleep(100);
            }throw new InvalidDataException("Jump timed out.");
        }
        private MapInteraction Find(uint address) {
            if(map.Live.progression!=null&&map.Live.progression.nodes!=null)
                foreach(var node in map.Live.progression.nodes)if(node.address==address)return node;
            throw new InvalidDataException("Selected interaction actor is no longer present.");
        }
        private bool Owns(int weapon) {
            var p=map.Live.progression;
            return p!=null&&p.inventory!=null&&p.inventory.known&&p.inventory.weapons_mask.HasValue&&
                (p.inventory.weapons_mask.Value&(1<<weapon))!=0;
        }
        private void LeaveChest(ChestApproach access,string reward) {
            Read();
            // The opening point intentionally uses body clearance rather than
            // the wider running margin. Return along the verified approach
            // before handing control back to room-wide route planning.
            Report("Reward confirmed; stepping back into the clear route...");
            Interaction(0,access.Staging);Delay(300);
            Report("Complete: "+reward+" confirmed in inventory; approach released.");
        }
        internal void Run(uint address,int button) {
            try {
                Bind();Read();
                var chest=Find(address);int weapon=chest.reward_weapon;
                if(weapon<0||weapon>14)throw new InvalidDataException("Prototype requires a weapon chest with an observable inventory reward.");
                if(Owns(weapon))throw new InvalidDataException("This weapon is already owned. Use a copy of a save before pickup.");
                Report("Refreshing chest opening geometry...");
                Interaction(1,new HeightPoint(map.Live.player.position));Delay(600);chest=Find(address);
                var access=ChestPlanner.Approach(map,chest);
                Report("Planning walk or supported platforms to "+chest.reward+"...");
                Traverse(access.Staging,button);
                Read();access=ChestPlanner.Approach(map,Find(address));
                Report("Walking to the chest...");
                Walk(NavigationRoute.Plan(map,new float[]{access.Staging.X,access.Staging.Y,access.Staging.Z}));Delay(800);
                Report("Precise final approach...");Interaction(0,access.Target);Delay(300);
                for(int attempt=0;attempt<3;attempt++) {
                    Read();if(Owns(weapon)){LeaveChest(access,chest.reward);return;}
                    var liveChest=Find(address);var a=liveChest.activation;var pos=new HeightPoint(map.Live.player.position);
                    if(a==null||!a.known||BoxJumpPlanner.Horizontal(pos,new HeightPoint(a.point))>=a.radius||
                        pos.Y<a.point[1]-4||pos.Y>a.point[1]+a.max_height)
                        throw new InvalidDataException("Player stopped outside the chest activation region.");
                    if(!map.Live.player.yaw.HasValue)throw new InvalidDataException("Player facing is unavailable.");
                    int angle=(map.Live.player.yaw.Value-a.facing+32768)&65535;
                    if(Math.Abs(angle-32768)>8192)throw new InvalidDataException("Player is not facing the chest; manual adjustment needed.");
                    Report("Opening chest; checking inventory...");Interaction(1,pos);Delay(5000);
                }
                if(!Owns(weapon))throw new InvalidDataException("Chest action finished without the expected inventory reward.");
                LeaveChest(access,chest.reward);
            } finally {
                Finish();
            }
        }
    }
}
