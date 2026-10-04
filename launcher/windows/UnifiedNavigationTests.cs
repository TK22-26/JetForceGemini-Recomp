using System;
using System.IO;
using System.Collections.Generic;
using System.Globalization;
using System.Runtime.Serialization.Json;
using System.Threading;
namespace JfgLauncher {
 internal static class UnifiedNavigationTests {
  private static int checks;
  private static void Check(bool value,string why){if(!value)throw new Exception("Unified navigation: "+why);++checks;}
  private static void Reject(Action action,string why){try{action();}catch(InvalidDataException){++checks;return;}throw new Exception(why);}
  private static MapSnapshot Stairs() {
   var map=NavigationCollisionTests.Fixture();map.Live.player.position=new float[]{-800,0,0};
   var vertices=new List<float[]>(map.Mesh.vertices);var faces=new List<MapFace>(map.Mesh.triangles);
   // A remote slope raises this connected ground component's maximum to 119.
   // It does not make the nearby 70-high first stair a downward traversal.
   vertices.Add(new[]{1000f,119f,1100f});
   faces.Add(new MapFace{v=new[]{2,4,3},normal=new[]{0f,1f,0f}});
   for(int step=0;step<3;step++) {
    float x=60+step*160,y=70+step*70;int i=vertices.Count;
    vertices.AddRange(new[]{new[]{x,y,-120f},new[]{x+160,y,-120f},new[]{x,y,120f},new[]{x+160,y,120f},new[]{x,y-70,-120f},new[]{x,y-70,120f}});
    faces.Add(new MapFace{v=new[]{i,i+2,i+1},normal=new[]{0f,1f,0f}});faces.Add(new MapFace{v=new[]{i+1,i+2,i+3},normal=new[]{0f,1f,0f}});
    faces.Add(new MapFace{v=new[]{i+4,i+5,i},normal=new[]{-1f,0f,0f}});faces.Add(new MapFace{v=new[]{i,i+5,i+2},normal=new[]{-1f,0f,0f}});
   }
   map.Mesh.vertices=vertices.ToArray();map.Mesh.triangles=faces.ToArray();
   map.Live.progression=new MapProgression{schema=1,inventory=new MapInventory{known=true,character=1,red_key=false,weapons_mask=1},nodes=new[]{
    new MapInteraction{address=777,action="talk",label="Guide",kind="npc",status="available",requirement="None",reward="Red key",npc_catalog_known=true,traversal="unknown",position=new[]{470f,210f,0f},talk_radius=72,talk_lower=-40,talk_upper=80,
      offers=new[]{new MapNpcOffer{id="4:0",kind="item",scope="current_character",conditions=new MapNpcCondition[0],consumed_items=new int[0],status="available",action=0,item=1,reward="Red key"}}}}};
   map.Live.box_jump=new MapJump{button=32768,calibrated=true,velocity=17.5f,gravity=1,apex=153,fit_error=0};return map;
  }
  private static void Write(string directory,string name,object value,Type type) {
   string file=Path.Combine(directory,name),temp=file+".fixture";
   using(var output=File.Create(temp))new DataContractJsonSerializer(type).WriteObject(output,value);
   for(int i=0;;i++)try{if(File.Exists(file))File.Replace(temp,file,null);else File.Move(temp,file);break;}
    catch(IOException){if(i==10)throw;Thread.Sleep(10);}
  }
  private static void Publish(string directory,MapSnapshot map) {
   map.Live.timestamp_ms=NavigationExplorer.Clock;++map.Live.update;
   Write(directory,"live.json",map.Live,typeof(MapLive));
  }
  // This command-protocol simulator tests orchestration and observed completion.
  // It is deliberately not a claim about game physics or live stair traversal.
  private static void NpcExecution(string directory,bool rejectLanding) {
   Directory.CreateDirectory(directory);var map=Stairs();map.Live.box_jump.calibrated=false;
   Write(directory,"mesh.json",map.Mesh,typeof(MapGeometry));Publish(directory,map);
   var runner=new NavigationRunner(directory);Exception failure=null;bool done=false;
   var thread=new Thread(delegate(){try{runner.RunNpc(777,map.Live.progression.nodes[0].offers[0],32768);}catch(Exception e){failure=e;}finally{Volatile.Write(ref done,true);}});
   thread.IsBackground=true;thread.Start();long until=NavigationExplorer.Clock+25000,seen=-1;int jumps=0,calibrations=0,talks=0,walks=0;
   try {
    while(!Volatile.Read(ref done)&&NavigationExplorer.Clock<until) {
     string command=Path.Combine(directory,"ai-command.txt");
     if(File.Exists(command)) {
      string text=ReadCommand(command);
      string[] words=text.Split(new[]{' ','\r','\n'},StringSplitOptions.RemoveEmptyEntries);
      long nonce=Int64.Parse(words[3],CultureInfo.InvariantCulture);
      if(nonce!=seen) {
       seen=nonce;
       if(words[0]=="JFGNAV3") {
        int count=Int32.Parse(words[6]);
        if(count>0){++walks;int end=9+(count-1)*3;map.Live.player.position=new[]{Single.Parse(words[end],CultureInfo.InvariantCulture),Single.Parse(words[end+1],CultureInfo.InvariantCulture),Single.Parse(words[end+2],CultureInfo.InvariantCulture)};}
        map.Live.navigation_ai=new MapAi{nonce=nonce,state=count>0?"approach_complete":"stopped",count=count,waypoint=count};
       }else if(words[0]=="JFGJUMP2") {
        int mode=Int32.Parse(words[5]);Check(words[10]=="32768","NPC jump ignored selected Expert controls");
        if(mode==0){++calibrations;map.Live.box_jump.calibrated=true;}
        else {++jumps;map.Live.player.position=new[]{Single.Parse(words[6],CultureInfo.InvariantCulture),Single.Parse(words[7],CultureInfo.InvariantCulture)+(rejectLanding?40:0),Single.Parse(words[8],CultureInfo.InvariantCulture)};}
        map.Live.box_jump.nonce=nonce;map.Live.box_jump.state=mode==0?"calibrated":"jump_landed";
        map.Live.navigation_ai=new MapAi{nonce=nonce,state=map.Live.box_jump.state};
       }else if(words[0]=="JFGINTERACT1") {
        int mode=Int32.Parse(words[5]);
        if(mode==0)map.Live.player.position=new[]{Single.Parse(words[6],CultureInfo.InvariantCulture),Single.Parse(words[7],CultureInfo.InvariantCulture),Single.Parse(words[8],CultureInfo.InvariantCulture)};
        else {++talks;map.Live.progression.nodes[0].offers[0].status="owned";map.Live.progression.inventory.red_key=true;}
        map.Live.navigation_ai=new MapAi{nonce=nonce,state=mode==0?"precision_complete":"action_complete"};
       }
      }
     }
     Publish(directory,map);Thread.Sleep(25);
    }
   }finally{runner.Cancelled=true;thread.Join(3000);}
   Check(!thread.IsAlive,"runner did not cancel promptly");
   if(rejectLanding) {
    Check(failure is InvalidDataException&&failure.Message.Contains("Landing was not confirmed"),"incorrect landing accepted: "+failure);
    Check(jumps==1&&talks==0,"continued chain or talked after rejected landing");
   }else {
    Check(failure==null,"NPC shared runner failed: "+failure);
    Check(calibrations==1&&jumps>=2&&walks>=2&&talks==1,"NPC did not walk, calibrate, chain jumps, approach, and confirm reward");
   }
  }
  private static string ReadCommand(string path) {
   for(int retry=0;retry<20;retry++)try {
    using(var file=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.ReadWrite|FileShare.Delete))
    using(var reader=new StreamReader(file))return reader.ReadToEnd();
   }catch(IOException){Thread.Sleep(5);}
   throw new IOException("Command file remained unavailable during the fixture.");
  }
  private static void ExitExecution(string directory,bool loadGap) {
   Directory.CreateDirectory(directory);
   var marker=new MapMarker{address=900,position=new[]{500f,0f,0f},destination_code=999,normal=new[]{1f,0f,0f}};
   var map=NavigationExplorerTests.Room(1,1,marker);map.Live.timestamp_ms=NavigationExplorer.Clock;
   Write(directory,"mesh.json",map.Mesh,typeof(MapGeometry));Publish(directory,map);
   var history=new NavigationExplorer();var explorer=new AutonomousExplorer(directory,history);
   explorer.Start(map,NavigationExplorer.Clock);long until=NavigationExplorer.Clock+7000,nearAt=0;bool changed=false;
   try {
    while(NavigationExplorer.Clock<until) {
     Publish(directory,map);explorer.Tick(map,NavigationExplorer.Clock);
     string path=Path.Combine(directory,"ai-command.txt");
     if(!changed&&File.Exists(path)) {
      string text=ReadCommand(path);
      var words=text.Split(new[]{' ','\r','\n'},StringSplitOptions.RemoveEmptyEntries);
      if(words[0]=="JFGNAV3"&&Int32.Parse(words[6])>0) {
       map.Live.navigation_ai=new MapAi{nonce=Int64.Parse(words[3]),active=true,state="following"};
       map.Live.player.position=new[]{490f,0f,0f};
       if(nearAt==0)nearAt=NavigationExplorer.Clock;
      }
      if(nearAt!=0&&NavigationExplorer.Clock-nearAt>350) {
       if(loadGap)explorer.MissingMap(NavigationExplorer.Clock);
       map=NavigationExplorerTests.Room(2,2,new MapMarker{address=901,position=new[]{0f,0f,0f},normal=new[]{1f,0f,0f},destination_code=1});
       map.Live.timestamp_ms=NavigationExplorer.Clock;
       Write(directory,"mesh.json",map.Mesh,typeof(MapGeometry));Publish(directory,map);changed=true;
      }
     }
     if(history.History.rooms[0].exits[0].destination.HasValue)break;
     if(!explorer.Running)throw new Exception("Shared exit executor stopped: "+explorer.Status);
     Thread.Sleep(25);
    }
   }finally{explorer.Stop("test completed");for(int i=0;i<100&&explorer.Busy;i++)Thread.Sleep(25);}
   Check(!explorer.Busy,"exit executor did not relinquish ownership");
   Check(history.History.rooms[0].exits[0].destination==2,"shared exit executor lost observed transition (load gap="+loadGap+")");
  }
  internal static int Run(string directory) {
   checks=0;var map=Stairs();var goal=new HeightPoint(470,210,0);
   Reject(delegate{NavigationRoute.Plan(map,new[]{goal.X,goal.Y,goal.Z});},"walking primitive crossed tall stairs");
   Check(NavigationPlanner.ToPoint(map,new HeightPoint(140,70,0)).PlatformGoal.HasValue,"remote ground high point hid a low stair");
   var point=NavigationPlanner.ToPoint(map,goal);Check(point.PlatformGoal.HasValue,"generic destination excluded jumps");
   var exit=new MapMarker{address=999,position=new[]{470f,210f,0f},destination_code=2};
   var exitPlan=NavigationPlanner.ToExit(map,exit);Check(exitPlan.PlatformGoal.HasValue&&exitPlan.ExitTarget==exit,"exit has different traversal capability");
   Reject(delegate{exitPlan.Send(directory,1,false,false);},"unvalidated platform plan sent as a walking line");
   var npc=map.Live.progression.nodes[0];var approaches=NavigationPlanner.NpcApproaches(map,npc);
   Check(approaches.Count>0&&NavigationPlanner.ToPoint(map,approaches[0].Staging).PlatformGoal.HasValue,"NPC staging requires a walking-only connection");
   map.Live.timestamp_ms=NavigationExplorer.Clock;
   var sequence=BoxJumpPlanner.Sequence(map,new JumpLanding{Point=goal});
   Check(sequence.Count>=2,"distant staircase did not produce intermediate landings");
   var first=BoxJumpPlanner.Approach(map,sequence[0]);Check(first.Walk!=null,"long walk to the stair foot was rejected as a long jump");
   map.Live.progression.inventory.character=2;Reject(delegate{NavigationPlanner.ToPoint(map,goal);},"unmeasured hover profile accepted");
   map.Live.progression.inventory.character=1;
   map.Live.progression.nodes=new[]{new MapInteraction{address=999,condition_known=true,condition_met=false}};
   Reject(delegate{NavigationPlanner.ToExit(map,exit);},"platform fallback bypassed exit prerequisite");
   map=Stairs();BoxJumpPlanner.PlanningCancelled=delegate{return true;};bool cancelled=false;
   try{BoxJumpPlanner.Sequence(map,new JumpLanding{Point=goal});}catch(OperationCanceledException){cancelled=true;}finally{BoxJumpPlanner.PlanningCancelled=null;}
   Check(cancelled,"platform search ignored cancellation");
   NpcExecution(Path.Combine(directory,"unified-npc"),false);
   NpcExecution(Path.Combine(directory,"unified-rejected-landing"),true);
   ExitExecution(Path.Combine(directory,"unified-exit"),false);
   ExitExecution(Path.Combine(directory,"unified-exit-load-gap"),true);
   return checks;
  }
 }
}
