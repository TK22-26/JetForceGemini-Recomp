using System;
using System.IO;
using System.Threading;
namespace JfgLauncher {
    internal static class AutonomousExplorerTests {
        private static int checks;
        private static void Check(bool value,string why){if(!value)throw new Exception("Autonomous AI: "+why);++checks;}
        private static void Reject(Action action,string why){try{action();}catch(InvalidDataException){++checks;return;}throw new Exception(why);}
        internal static int Run() {
            var d=new MapDialogue{known=true,active=true,ready=false,rows=new MapDialogueChoice[0]};
            Check(DialogueFlow.Select(d,null,false)==-1,"wait while text is scrolling");
            d.ready=true;Check(DialogueFlow.Select(d,null,false)==0,"advance ready forced tutorial text");
            d.choices=true;d.rows=new[]{new MapDialogueChoice{action=0x5000},new MapDialogueChoice{action=0}};
            var reward=new MapNpcOffer{id="4:0/38:1",kind="item",status="available",action=0,item=1,reward="Red key"};
            Check(DialogueFlow.Select(d,reward,false)==2,"select red key rather than leaving");
            d.selected=1;Check(DialogueFlow.Select(d,reward,false)==0,"confirm selected reward");
            Check(DialogueFlow.Select(d,reward,true)==1,"leave after observed reward");
            d.selected=0;Check(DialogueFlow.Select(d,reward,true)==0,"confirm known close");
            d.rows=new[]{new MapDialogueChoice{action=0x2012},new MapDialogueChoice{action=0x5000}};
            reward.id="2:0/8:0/18:0";
            Check(DialogueFlow.Select(d,reward,false)==0,"follow nested choice table by action");
            d.rows=new[]{new MapDialogueChoice{action=0x1003}};
            Reject(delegate{DialogueFlow.Select(d,null,false);},"unknown choice must stop");
            d.selected=5;Reject(d.Validate,"invalid menu selection");
            var npc=new MapInteraction{action="talk",offers=new[]{reward}};
            Check(AutonomousExplorer.UsefulOffer(npc)==reward,"include available NPC item");
            reward.kind="weapon";Check(AutonomousExplorer.UsefulOffer(npc)==reward,"include NPC weapon");
            reward.kind="ship_part";Check(AutonomousExplorer.UsefulOffer(npc)==reward,"include progression ship part");
            reward.status="owned";Check(AutonomousExplorer.UsefulOffer(npc)==null,"do not repeat owned reward");
            reward.status="blocked";Check(AutonomousExplorer.UsefulOffer(npc)==null,"respect unmet prerequisites");
            reward.status="available";reward.cost=5;Check(AutonomousExplorer.UsefulOffer(npc)==null,"do not buy incidental services");
            reward.cost=0;reward.kind="item";
            Check(AutonomousExplorer.ObjectivePriority(npc)<AutonomousExplorer.ObjectivePriority(new MapInteraction{action="open_chest"}),"key NPC should precede weapon chests");
            Check(AutonomousExplorer.ObjectivePriority(new MapInteraction{action="collect",kind="key"})==0,"prioritize loose keys");
            Check(NavigationRunner.GainedItem(new[]{false,true},new[]{true,true}),"new key bit not detected");
            Check(!NavigationRunner.GainedItem(new[]{false,true},new[]{false,true}),"unchanged inventory counted as key collection");
            var marker=new MapMarker{address=123,position=new float[]{500,0,0},normal=new float[]{1,0,0},destination_code=2};
            var map=NavigationExplorerTests.Room(1,1,marker);long now=NavigationExplorer.Clock;
            map.Live.timestamp_ms=now;map.Live.dialogue=new MapDialogue{rows=new MapDialogueChoice[0]};
            reward=new MapNpcOffer{id="4:0/38:0",kind="item",status="available",action=0,item=1,reward="Red key"};
            npc=new MapInteraction{address=321,action="talk",position=new float[]{100,0,0},talk_radius=100,offers=new[]{reward}};
            map.Live.progression.nodes=new[]{npc};int executions=0;
            var explorer=new AutonomousExplorer(Path.GetTempPath(),new NavigationExplorer(),
                delegate(NavigationRunner runner,string action,uint address,MapNpcOffer selected,float[] destination) {
                    ++executions;
                    if(action=="NPC reward") {selected.status="owned";map.Live.progression.inventory.red_key=true;}
                    else if(action=="dialogue") {map.Live.dialogue.active=false;map.Live.clearing_active=true;}
                    else throw new Exception("Unexpected action");
                });
            explorer.Start(map,now);
            var command=explorer.Tick(map,now);
            Check(command.Stop&&command.Route==null&&!explorer.MayHeartbeat,"NPC action takes control before walking");
            explorer.Tick(map,now);
            Check(!explorer.MayHeartbeat,"no walking heartbeat while action owns controller");
            for(int n=0;n<100&&explorer.Busy;n++)Thread.Sleep(5);
            command=explorer.Tick(map,now);
            Check(executions==1&&reward.status=="owned"&&explorer.Running,"reward verified and explorer resumes");
            if(command.Route==null)command=explorer.Tick(map,now+1000);
            Check(command.Route!=null,"walk toward exit after NPC reward");
            explorer.Dispatched(now,now);
            map.Live.dialogue=new MapDialogue{known=true,active=true,ready=true,rows=new MapDialogueChoice[0]};
            map.Live.clearing_active=false;
            command=explorer.Tick(map,now+1100);
            Check(command.Stop&&!explorer.MayHeartbeat,"forced tutorial dialogue preempts walking");
            explorer.Tick(map,now+1200);
            for(int n=0;n<100&&explorer.Busy;n++)Thread.Sleep(5);
            command=explorer.Tick(map,now+1300);
            Check(executions==2&&explorer.Running&&command.Route!=null,"resume route after forced dialogue");
            ++map.Live.navigation_ai.manual_inputs;
            command=explorer.Tick(map,now+1400);
            Check(command.Stop&&!explorer.Running,"manual input cancels unified system");
            var back=new MapMarker{address=444,position=new float[]{0,0,0},normal=new float[]{0,0,1},destination_code=4};
            var itemRoom=NavigationExplorerTests.Room(122,1,back);
            itemRoom.Live.timestamp_ms=now;itemRoom.Live.dialogue=new MapDialogue{rows=new MapDialogueChoice[0]};
            itemRoom.Live.progression.inventory.weapons_mask=1;
            itemRoom.Live.progression.nodes=new[]{new MapInteraction{address=445,action="open_chest",kind="weapon",
                position=new float[]{200,0,0},status="unopened",reward_weapon=10}};
            int opened=0;
            var itemExplorer=new AutonomousExplorer(Path.GetTempPath(),new NavigationExplorer(),
                delegate(NavigationRunner runner,string action,uint address,MapNpcOffer selected,float[] destination) {
                    if(action!="weapon chest")throw new Exception("Expected Fish Food chest");
                    ++opened;itemRoom.Live.progression.inventory.weapons_mask|=1024;
                    itemRoom.Live.progression.nodes[0].status="opened";
                });
            itemExplorer.Start(itemRoom,now);
            Check(itemExplorer.Tick(itemRoom,now).Stop&&opened==0,"left item room before collecting objective");
            itemExplorer.Tick(itemRoom,now);
            for(int n=0;n<100&&itemExplorer.Busy;n++)Thread.Sleep(5);
            command=itemExplorer.Tick(itemRoom,now);
            Check(opened==1&&command.Route!=null&&itemExplorer.TargetKey==NavigationExplorer.ExitKey(back),"did not return after Fish Food ownership");
            itemExplorer.Stop("test");
            var inventory=new InventoryTracker{known=true,current=1,shared=new bool[12],characters=new[]{
                new CharacterInventory{id=0,items=new bool[27]},new CharacterInventory{id=1,items=new bool[27],weapons=13},new CharacterInventory{id=2,items=new bool[27]}}};
            Check(InventoryCanvas.weapons[7]=="Sniper rifle"&&InventoryCanvas.weapons[10]=="Fish Food","weapon bit positions mislabeled");
            Check(InventoryCanvas.Item(9)=="Blue key"&&InventoryCanvas.Item(26)=="Ear plugs"&&InventoryCanvas.Item(27)=="Arcade chip","big-endian item bit labels");
            inventory.Validate(); // Older 27-bit exports remain readable.
            inventory.characters[1].items=new bool[28];inventory.characters[1].items[27]=true;inventory.Validate();
            using(var window=new InventoryWindow(Path.GetTempPath())) {
                window.Apply(inventory,true);Check(window.SelectedCharacter==1,"inventory selects Juno's actual ID 1");
                inventory.current=0;window.Apply(inventory,true);Check(window.SelectedCharacter==0,"inventory follows Vela ID 0");
                inventory.current=2;window.Apply(inventory,true);Check(window.SelectedCharacter==2,"inventory follows Lupus ID 2");
                window.Apply(null,false);
                inventory.characters[2].id=1;Reject(inventory.Validate,"duplicate character inventory rejected");
            }
            return checks;
        }
    }
}
