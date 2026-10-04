using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using System.Threading;
using System.Windows.Forms;

namespace JfgLauncher {
    internal sealed class ChestApproach {
        internal HeightPoint Target, Staging;
    }
    internal static class ChestPlanner {
        internal static ChestApproach Approach(MapSnapshot map,MapInteraction chest) {
            if(chest==null||chest.action!="open_chest"||chest.activation==null||!chest.activation.known)
                throw new InvalidDataException("Chest activation geometry is unavailable. Press A once during gameplay, then refresh.");
            var a=chest.activation;var centre=new HeightPoint(a.point);var actor=new HeightPoint(chest.position);
            float dx=centre.X-actor.X,dz=centre.Z-actor.Z,len=(float)Math.Sqrt(dx*dx+dz*dz);
            if(len<1||a.radius<=6)throw new InvalidDataException("No supported chest approach direction.");
            dx/=len;dz/=len;float y;
            // Stand inside the activation circle, on its side away from the
            // chest. Do not plan toward the solid centre of the chest model.
            var target=new HeightPoint(centre.X+dx*(a.radius-5),centre.Y,centre.Z+dz*(a.radius-5));
            if(!BoxJumpPlanner.Floor(map.Mesh,target.X,target.Z,centre.Y,8,out y))
                throw new InvalidDataException("Chest opening point has no supporting floor.");
            target.Y=y+BoxJumpPlanner.Offset(map);
            var stage=new HeightPoint(target.X+dx*60,target.Y,target.Z+dz*60);
            float stageY;
            if(!BoxJumpPlanner.Floor(map.Mesh,stage.X,stage.Z,target.Y,64,out stageY))
                throw new InvalidDataException("Chest staging point has no supporting floor.");
            stage.Y=stageY+BoxJumpPlanner.Offset(map);
            var floors=new MapLayers(map.Mesh).Floors;
            if(!NavigationRoute.ClearWalk(map,floors,stage,target,0))
                throw new InvalidDataException("Chest opening point lacks body clearance.");
            return new ChestApproach{Target=target,Staging=stage};
        }
    }
    // One owner writes commands during a trial. Cancellation is checked before
    // each heartbeat, and the worker always emits its final stop after exiting.
    internal sealed class ChestTrial {
        internal volatile bool Cancelled;
        internal Action<string> Report=delegate {};
        private readonly string directory;
        private MapSnapshot map;
        private uint level;private long generation,nonce,started,manual;
        private bool bound;
        private uint npcAddress;
        private MapNpcOffer npcOffer;
        private int dialogueSerial;
        internal ChestTrial(string path){directory=path;nonce=NavigationExplorer.Clock;}
        private MapSnapshot Raw() {
            if(Cancelled)throw new OperationCanceledException();
            map=MapSnapshot.Load(directory,map==null?null:map.Mesh);
            if(!map.IsLive)throw new InvalidDataException("Map updates stopped.");
            if(bound&&(map.Live.level!=level||map.Live.generation!=generation))throw new InvalidDataException("Room changed during an action.");
            if(bound&&map.Live.navigation_ai!=null&&map.Live.navigation_ai.manual_inputs!=manual)
                throw new InvalidDataException("Manual input detected; autonomous action stopped.");
            if(bound&&NavigationExplorer.Clock-started>180000)throw new InvalidDataException("Action reached its three-minute limit.");
            if(map.Live.player.motion!=null&&map.Live.player.motion.known&&
               (map.Live.player.motion.hang_entry||map.Live.player.motion.grab_entry))
                throw new InvalidDataException("Ledge grab detected; no verified release action.");
            return map;
        }
        private void Bind() {
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
            BoxJumpPlanner.NeedLive(map);return map;
        }
        private void Finish() {
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
            NavigationRoute ground=null;
            try{ground=NavigationRoute.Plan(map,new float[]{goal.X,goal.Y,goal.Z});}
            catch(InvalidDataException error){Report("Checking platforms: "+error.Message);}
            if(ground!=null){Walk(ground);return;}
            if(!BoxJumpPlanner.NeedsPlatformTraversal(map,goal))
                throw new InvalidDataException("Walking route is blocked or geometry is incomplete; no verified elevated platform requires a jump.");
            if(map.Live.progression!=null&&map.Live.progression.inventory!=null&&map.Live.progression.inventory.character==2)
                throw new InvalidDataException("Lupus hover traversal needs its own verified movement profile.");
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
                Report("Jump "+(i+1)+"/"+steps.Count+"; checking landing state...");
                Jump(1,plan,button);
            }
            Read();Walk(NavigationRoute.Plan(map,new float[]{goal.X,goal.Y,goal.Z}));
        }
        internal void RunTraversal(float[] goal,int button) {
            try{Bind();Traverse(new HeightPoint(goal),button);Report("Platform route complete; replanning exit.");}
            finally{Finish();}
        }
        internal void RunNpc(uint address,MapNpcOffer reward) {
            try {
                Bind();npcAddress=address;npcOffer=reward;
                var npc=Find(address);
                if(AutonomousExplorer.UsefulOffer(npc)==null)throw new InvalidDataException("NPC reward is no longer available.");
                if(npc.talk_radius<=8)throw new InvalidDataException("NPC conversation bounds are unavailable.");
                var centre=new HeightPoint(npc.position);
                var pos=new HeightPoint(map.Live.player.position);
                float dx=pos.X-centre.X,dz=pos.Z-centre.Z,len=(float)Math.Sqrt(dx*dx+dz*dz);
                if(len<1){dx=0;dz=1;len=1;}dx/=len;dz/=len;
                NavigationRoute route=null;HeightPoint target=new HeightPoint();HeightPoint stage=new HeightPoint();
                for(int sample=0;sample<12;sample++) {
                    double angle=sample*Math.PI/6;
                    float x=(float)(dx*Math.Cos(angle)-dz*Math.Sin(angle));
                    float z=(float)(dx*Math.Sin(angle)+dz*Math.Cos(angle));
                    float radius=Math.Max(10,npc.talk_radius*.55f),floor;
                    target=new HeightPoint(centre.X+x*radius,centre.Y,centre.Z+z*radius);
                    if(!BoxJumpPlanner.Floor(map.Mesh,target.X,target.Z,centre.Y,64,out floor))continue;
                    target.Y=floor+BoxJumpPlanner.Offset(map);
                    if(target.Y-centre.Y<=npc.talk_lower||target.Y-centre.Y>=npc.talk_upper)continue;
                    stage=new HeightPoint(target.X+x*40,target.Y,target.Z+z*40);
                    if(!NavigationRoute.ClearWalk(map,new MapLayers(map.Mesh).Floors,stage,target,0))continue;
                    try{route=NavigationRoute.Plan(map,new float[]{stage.X,stage.Y,stage.Z});break;}catch(InvalidDataException){}
                }
                if(route==null)throw new InvalidDataException("No clear supported approach to NPC "+npc.label+".");
                Report("Approaching "+npc.label+" for "+reward.reward+"...");
                Walk(route);Delay(600);Interaction(0,target);Delay(300);
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
                        throw new InvalidDataException("Chest interaction stopped: "+ai.state);
                    return;
                }
                if(mode==0&&!NavigationRoute.ClearWalk(map,new MapLayers(map.Mesh).Floors,new HeightPoint(map.Live.player.position),target,0))
                    throw new InvalidDataException("Body clearance changed during chest approach.");
                InteractionSend(mode,target);Thread.Sleep(100);
            }throw new InvalidDataException("Chest interaction timed out.");
        }
        private void Walk(NavigationRoute route) {
            Next();int beforeDialogue=dialogueSerial;long until=NavigationExplorer.Clock+45000;
            while(NavigationExplorer.Clock<until) {
                Read();
                if(dialogueSerial!=beforeDialogue) {
                    beforeDialogue=dialogueSerial;var end=route.Points[route.Points.Count-1];
                    route=NavigationRoute.Plan(map,new float[]{end.X,end.Y,end.Z});Next();
                    until=NavigationExplorer.Clock+45000;
                }
                var ai=map.Live.navigation_ai;
                if(ai!=null&&ai.nonce==nonce&&!ai.active) {
                    if(ai.state!="approach_complete")throw new InvalidDataException("Walking stopped: "+ai.state);return;
                }
                string problem=route.CheckRemaining(map,ai!=null&&ai.nonce==nonce?ai.waypoint:0);
                if(problem!=null)throw new InvalidDataException(problem);
                if(Cancelled)throw new OperationCanceledException();
                route.Send(directory,nonce,false,false);Thread.Sleep(100);
            }throw new InvalidDataException("Walking approach timed out.");
        }
        private void Jump(int mode,JumpPlan plan,int button) {
            Next();long until=NavigationExplorer.Clock+12000;
            HeightPoint target=plan==null?new HeightPoint(map.Live.player.position):plan.Target;
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
    internal sealed class ChestTrialWindow:Form {
        private readonly string directory;
        private readonly ComboBox chests=new ComboBox{DropDownStyle=ComboBoxStyle.DropDownList,Width=330};
        private readonly ComboBox controls=new ComboBox{DropDownStyle=ComboBoxStyle.DropDownList,Width=165};
        private readonly Button run=new Button{Text="Run chest route",AutoSize=true};
        private readonly Label status=new Label{Dock=DockStyle.Fill,Padding=new Padding(12)};
        private ChestTrial trial;
        [System.Runtime.InteropServices.DllImport("user32.dll",CharSet=System.Runtime.InteropServices.CharSet.Unicode)]
        private static extern IntPtr FindWindow(string name,string title);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool SetForegroundWindow(IntPtr window);
        internal ChestTrialWindow(string path) {
            directory=path;Text="Weapon chest route prototype";ClientSize=new System.Drawing.Size(650,200);
            var bar=new FlowLayoutPanel{Dock=DockStyle.Top,Height=85};
            var refresh=new Button{Text="Refresh chests",AutoSize=true};var stop=new Button{Text="Stop",AutoSize=true};
            controls.Items.AddRange(new object[]{"Normal (C-Up jump)","Expert (A jump)"});controls.SelectedIndex=0;
            bar.Controls.AddRange(new Control[]{chests,refresh,controls,run,stop});Controls.Add(status);Controls.Add(bar);
            status.Text="Use a copied save. Start on open ground, choose a weapon chest, then keep the game focused. Manual movement cancels the trial.";
            refresh.Click+=delegate{if(trial==null)RefreshChests();};
            stop.Click+=delegate{if(trial!=null)trial.Cancelled=true;};
            run.Click+=delegate {
                var chest=chests.SelectedItem as MapInteraction;if(chest==null||trial!=null)return;
                int button=controls.SelectedIndex==0?8:32768;
                IntPtr game=FindWindow("JfgPhase8LiveRt64Window",null);
                if(game==IntPtr.Zero||!SetForegroundWindow(game)){status.Text="Focus the running game and try again.";return;}
                var current=new ChestTrial(directory);trial=current;run.Enabled=false;chests.Enabled=false;controls.Enabled=false;
                current.Report=delegate(string text){if(!IsDisposed&&IsHandleCreated)try{BeginInvoke((Action)delegate{status.Text=text;});}catch(InvalidOperationException){}};
                var worker=new System.ComponentModel.BackgroundWorker();
                worker.DoWork+=delegate{current.Run(chest.address,button);};
                worker.RunWorkerCompleted+=delegate(object sender,System.ComponentModel.RunWorkerCompletedEventArgs e){
                    worker.Dispose();trial=null;if(IsDisposed)return;run.Enabled=true;chests.Enabled=true;controls.Enabled=true;
                    if(e.Error!=null)status.Text=e.Error is OperationCanceledException?"Chest trial stopped.":e.Error.Message;
                };worker.RunWorkerAsync();
            };
            FormClosing+=delegate{if(trial!=null)trial.Cancelled=true;};
            Shown+=delegate{RefreshChests();};
        }
        private void RefreshChests() {
            try {
                var map=MapSnapshot.Load(directory,null);BoxJumpPlanner.NeedLive(map);
                chests.Items.Clear();
                if(map.Live.progression!=null)foreach(var node in map.Live.progression.nodes)
                    if(node.action=="open_chest"&&node.reward_weapon>=0)chests.Items.Add(node);
                if(chests.Items.Count>0)chests.SelectedIndex=0;else status.Text="No weapon chests in the current room.";
            } catch(Exception error) {
                if(!(error is IOException)&&!(error is InvalidDataException)&&!(error is UnauthorizedAccessException)&&!(error is System.Runtime.Serialization.SerializationException))throw;
                status.Text=error.Message;
            }
        }
    }
}
