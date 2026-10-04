using System;
using System.Collections.Generic;
using System.IO;
namespace JfgLauncher {
 internal static class BoxJumpTests {
  private static int checks;
  private static void Check(bool ok,string text){if(!ok)throw new Exception("Box jump: "+text);checks++;}
  private static void Reject(Action action,string text){bool failed=false;try{action();}catch(InvalidDataException){failed=true;}Check(failed,text);}
  private static MapSnapshot Fixture() {
   MapSnapshot m=NavigationCollisionTests.Fixture();
   var vertices=new List<float[]>(m.Mesh.vertices);
   vertices.AddRange(new float[][]{new float[]{60,60,-80},new float[]{180,60,-80},new float[]{60,60,80},new float[]{180,60,80}});
   var faces=new List<MapFace>(m.Mesh.triangles);
   faces.Add(new MapFace{v=new int[]{4,6,5},normal=new float[]{0,1,0}});
   faces.Add(new MapFace{v=new int[]{5,6,7},normal=new float[]{0,1,0}});
   m.Mesh.vertices=vertices.ToArray();m.Mesh.triangles=faces.ToArray();
   m.Live.box_jump=new MapJump {calibrated=true,velocity=17.5f,gravity=1,apex=153,fit_error=0};
   return m;
  }
  internal static int Run() {
   checks=0;MapSnapshot m=Fixture();JumpLanding target=new JumpLanding{Point=new HeightPoint(100,60,0)};
   JumpPlan p=BoxJumpPlanner.Plan(m,target);
   Check(p.Arc.Count>20 && Math.Abs(p.Arc[p.Arc.Count-1].Y-60)<.01f,"arc misses raised landing");
   Check(p.Arc[0].Y==0 && p.Duration>17.5f,"landing must be on descending branch");
   Check(BoxJumpPlanner.Candidates(m).Count>0,"raised supported surface not found");
   Reject(delegate{BoxJumpPlanner.Plan(m,new JumpLanding{Point=new HeightPoint(65,60,0)});},"landing edge has insufficient footprint");
   m.Live.box_jump.calibrated=false;Reject(delegate{BoxJumpPlanner.Plan(m,target);},"uncalibrated jump accepted");m.Live.box_jump.calibrated=true;
   m.Live.actors=new MapActor[]{new MapActor{address=0x80102000,position=new float[]{40,0,0}}};
   m.Live.collision.models=new MapCollisionModel[]{new MapCollisionModel{address=0x80102000,enabled=true,lower=new float[]{30,0,-80},upper=new float[]{60,300,80}}};
   Reject(delegate{BoxJumpPlanner.Plan(m,target);},"wall on arc ignored");
   m.Live.collision.models[0].lower=new float[]{-100,180,-100};m.Live.collision.models[0].upper=new float[]{200,220,100};
   Reject(delegate{BoxJumpPlanner.Plan(m,target);},"overhead body collision ignored");
   m=Fixture();m.Live.box_jump.apex=50;Reject(delegate{BoxJumpPlanner.Plan(m,target);},"unreachable height accepted");
   m=Fixture();m.Live.generation=2;Reject(delegate{BoxJumpPlanner.ValidateArc(m,p);},"stale room generation accepted");
   m=Fixture();m.Live.box_jump.gravity=Single.NaN;Reject(delegate{BoxJumpPlanner.Plan(m,target);},"invalid physics profile accepted");

   m=Fixture();m.Live.player.position=new float[]{-300,0,0};float[] original=m.Live.player.position;
   JumpApproach approach=BoxJumpPlanner.Approach(m,target);
   Check(approach.Walk!=null && approach.Walk.Points.Count>0,"distant landing lacks walking approach");
   Check(Object.ReferenceEquals(m.Live.player.position,original),"candidate search changed live player state");
   Check(Math.Abs(approach.Jump.Start.Y)<.1f && approach.Jump.Target.Y==60,"approach mixed floor levels");
   m=Fixture();m.Live.player.position=new float[]{-300,0,0};original=m.Live.player.position;
   Reject(delegate{BoxJumpPlanner.Approach(m,new JumpLanding{Point=new HeightPoint(100,1000,0)});},"unsupported approach accepted");
   Check(Object.ReferenceEquals(m.Live.player.position,original),"rejected search changed live player state");

   m=Fixture();for(int i=4;i<8;i++)m.Mesh.vertices[i][1]=160;
   var wallVertices=new List<float[]>(m.Mesh.vertices);wallVertices.Add(new float[]{60,0,-80});wallVertices.Add(new float[]{60,0,80});
   var wallFaces=new List<MapFace>(m.Mesh.triangles);
   wallFaces.Add(new MapFace{v=new int[]{8,9,6},normal=new float[]{-1,0,0}});
   wallFaces.Add(new MapFace{v=new int[]{8,6,4},normal=new float[]{-1,0,0}});
   m.Mesh.vertices=wallVertices.ToArray();m.Mesh.triangles=wallFaces.ToArray();
   Reject(delegate{BoxJumpPlanner.Plan(m,new JumpLanding{Point=new HeightPoint(100,160,0)});},
       "height alone inferred a ledge grab instead of requiring an intermediate platform");
   m=Fixture();for(int i=4;i<8;i++)m.Mesh.vertices[i][1]=160;
   Reject(delegate{BoxJumpPlanner.Plan(m,new JumpLanding{Point=new HeightPoint(100,160,0)});},"unsupported ledge contact accepted");
   m=Fixture();m.Mesh.vertices[4]=new float[]{268,60,-32};m.Mesh.vertices[5]=new float[]{332,60,-32};m.Mesh.vertices[6]=new float[]{268,60,32};m.Mesh.vertices[7]=new float[]{332,60,32};
   bool narrow=false;foreach(JumpLanding candidate in BoxJumpPlanner.Candidates(m))if(Math.Abs(candidate.Point.X-300)<1 && Math.Abs(candidate.Point.Z)<1)narrow=true;
   Check(narrow,"shared-edge centre of a narrow box was missed");
   // A shallow pitched top is a standing surface, not a ledge-grab contact.
   // Four units over 64 used to be discarded by the flat-triangle filter.
   m=Fixture();
   m.Mesh.vertices[4]=new float[]{268,64,-32};m.Mesh.vertices[5]=new float[]{332,60,-32};
   m.Mesh.vertices[6]=new float[]{268,64,32};m.Mesh.vertices[7]=new float[]{332,64,32};
   bool tilted=false;
   foreach(JumpLanding candidate in BoxJumpPlanner.Candidates(m))
       if(Math.Abs(candidate.Point.X-300)<1&&Math.Abs(candidate.Point.Z)<1) {
           tilted=true;Check(Math.Abs(candidate.Point.Y-62)<.1f,"landing height did not follow its sloped triangle");
           Check(BoxJumpPlanner.Patch(m,candidate.Point,32,0),"sloped top lacks continuous foot support");
       }
   Check(tilted,"gently sloped intermediate box was omitted");
   m=Fixture();m.Mesh.vertices[4][1]=60;m.Mesh.vertices[5][1]=100;m.Mesh.vertices[6][1]=60;m.Mesh.vertices[7][1]=100;
   Check(BoxJumpPlanner.Candidates(m).Count==0,"steep surface became a box landing");


   m=Fixture();m.Live.player.position=new float[]{35,0,0};
   var cv=new List<float[]>(m.Mesh.vertices);cv.Add(new float[]{60,0,-80});cv.Add(new float[]{60,0,80});
   var cf=new List<MapFace>(m.Mesh.triangles);
   cf.Add(new MapFace{v=new int[]{8,9,6},normal=new float[]{-1,0,0}});cf.Add(new MapFace{v=new int[]{8,6,4},normal=new float[]{-1,0,0}});
   m.Mesh.vertices=cv.ToArray();m.Mesh.triangles=cf.ToArray();
   JumpPlan close=BoxJumpPlanner.Plan(m,target);
   Check(close.Lift>0,"close box skipped vertical takeoff clearance");
   Check(Math.Abs(close.Arc[1].X-close.Start.X)<.01f,"vertical takeoff moved through the box side");
   m=Fixture();
   m.Mesh.vertices[4]=new float[]{60,60,-160};m.Mesh.vertices[5]=new float[]{600,60,-160};
   m.Mesh.vertices[6]=new float[]{60,60,160};m.Mesh.vertices[7]=new float[]{600,60,160};
   bool edgeEntry=false;
   foreach(var entry in BoxJumpPlanner.Candidates(m,true))
       if(entry.Point.X>=88&&entry.Point.X<=110&&Math.Abs(entry.Point.Z)<40)edgeEntry=true;
   Check(edgeEntry,"long platform edge lacks intermediate entry samples");
   m=Fixture();var seq=BoxJumpPlanner.Sequence(m,target);
   Check(seq.Count==1&&seq[0].Surface==target.Surface,"single reachable platform route was not retained");
   m=Fixture();p=BoxJumpPlanner.Plan(m,target);
   m.Live.player.position=new float[]{125,60,0};m.Live.box_jump.state="jump_missed_landing";
   Check(BoxJumpPlanner.SupportedLanding(m,p),"clear connected landing rejected for missing the centroid");
   m.Live.player.position=new float[]{170,60,0};
   Check(!BoxJumpPlanner.SupportedLanding(m,p),"landing near unsupported edge accepted");
   m.Live.player.position=new float[]{125,0,0};
   Check(!BoxJumpPlanner.SupportedLanding(m,p),"landing on lower storey accepted");
   m.Live.player.position=new float[]{125,60,0};m.Live.box_jump.state="jump_timeout";
   Check(!BoxJumpPlanner.SupportedLanding(m,p),"timed-out trial accepted as landed");

   m=Fixture();var twoVerts=new List<float[]>(m.Mesh.vertices);
   twoVerts.AddRange(new float[][]{new float[]{192,180,-80},new float[]{320,180,-80},new float[]{192,180,80},new float[]{320,180,80}});
   var twoFaces=new List<MapFace>(m.Mesh.triangles);
   twoFaces.Add(new MapFace{v=new int[]{8,10,9},normal=new float[]{0,1,0}});
   twoFaces.Add(new MapFace{v=new int[]{9,10,11},normal=new float[]{0,1,0}});
   m.Mesh.vertices=twoVerts.ToArray();m.Mesh.triangles=twoFaces.ToArray();
   original=m.Live.player.position;
   var stairs=BoxJumpPlanner.Sequence(m,new JumpLanding{Point=new HeightPoint(224,180,0),Radius=8});
   Check(stairs.Count>=2&&Math.Abs(stairs[0].Point.Y-60)<.01f&&Math.Abs(stairs[stairs.Count-1].Point.Y-180)<.01f,"platform sequence skipped required intermediate height");
   Check(Object.ReferenceEquals(original,m.Live.player.position),"platform search mutated live player position");
   m=Fixture();m.Live.box_jump=null;
   Reject(delegate {BoxJumpPlanner.Sequence(m,target);},"sequence without calibration caused an unhandled error");
   string pending=Path.Combine(Path.GetTempPath(),"jfg-box-wait-"+Guid.NewGuid().ToString("N"));
   Directory.CreateDirectory(pending);
   try {
     File.WriteAllText(Path.Combine(pending,"live.json"),"{\"schema\":1,\"generation\":1,\"mesh_ready\":false,\"player\":null}");
     using(BoxJumpWindow window=new BoxJumpWindow(pending)) {
       window.Show();System.Windows.Forms.Application.DoEvents();bool waiting=false;
       foreach(System.Windows.Forms.Control control in window.Controls)if(control is System.Windows.Forms.Label && control.Text.Contains("Waiting for gameplay"))waiting=true;
       Check(waiting,"pre-game map state caused an exception instead of a waiting message");window.Close();
     }
   }finally {File.Delete(Path.Combine(pending,"live.json"));Directory.Delete(pending);}
   return checks;
  }
 }
}
