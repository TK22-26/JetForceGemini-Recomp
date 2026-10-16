import unittest
from scripts.analyze_function_profile import analyze,ROOT
def row(kind,values):
 return "1000\t"+kind+"\t"+"\t".join(f"{x:x}" for x in values)+"\n"
KEY=[100,20,98,19,7]
def fixture():
 return [row("update-work",[100,20,1,0,100,1000,100]),
  row("function-profile",KEY+[2,ROOT,2,400,400,40,40,0,30,300,30,1]),
  row("function-profile",KEY+[ROOT,0,1,1000,600,100,60,100,100,1000,100,1]),
  row("function-profile-end",KEY+[2,1,3,2,0])]
class FunctionProfileTests(unittest.TestCase):
 def test_exclusive_percentages_and_slow_update(self):
  result=analyze(fixture());self.assertEqual(result["updates"],1)
  self.assertEqual(sum(x["exclusive_cpu_percent"] for x in result["functions"]),100)
  self.assertEqual(result["slowest_updates"][0]["calls"],3)
  self.assertEqual(result["slowest_updates"][0]["update_active_ms"],.9)
 def test_incomplete_capture(self):
  self.assertEqual(analyze(fixture()[:-1])["diagnostics"]["unfinished_edges"],2)
 def test_missing_edge(self):
  result=analyze(fixture()[:1]+fixture()[2:])
  self.assertEqual(result["updates"],0);self.assertEqual(result["diagnostics"]["missing_rows_or_calls"],1)
 def test_bad_sums_rejected(self):
  data=fixture();data[1]=row("function-profile",KEY+[2,ROOT,2,400,400,40,41,0,30,300,30,1])
  with self.assertRaisesRegex(ValueError,"do not sum"):analyze(data)
 def test_invalid_and_capacity_are_explicit(self):
  data=fixture();data[-1]=row("function-profile-end",KEY+[2,0,3,2,1])
  self.assertEqual(analyze(data)["diagnostics"]["invalid_counters_or_overflow"],1)
  self.assertEqual(analyze(["limit\tbyte-limit\n"])["diagnostics"]["trace_limit"],1)
 def test_window_and_symbol_names(self):
  self.assertEqual(analyze(fixture(),last_vi=100)["updates"],0)
  report=analyze(fixture(),names={2:"child"})
  self.assertEqual(report["functions"][1]["name"],"child")
 def test_host_emission_and_completed_gpu_are_correlated(self):
  data=[row("gpu-workload-time",[98,19,10,1000,100,100,0]).replace("1000\t","0\t",1)]
  data+=fixture()[:-1]+[row("function-profile-host",KEY+[1,200,2,4,10000]),fixture()[-1],
   row("function-profile-emission",KEY+[1,40000,123])]
  report=analyze(data);update=report["slowest_updates"][0]
  self.assertEqual(update["host"]["process_cycles"],200)
  self.assertEqual(update["host"]["baton_wake_ms"],.01)
  self.assertEqual(update["profiler_emission"]["wall_ms"],.04)
  self.assertTrue(update["gpu_completed_observations"]["gpu-workload-time"]["valid"])
 def test_submission_detail_preserves_repeated_scene_keys(self):
  base=fixture()
  a=row("submit",[100,20,1,100,0,0,0,50,0]).replace("1000\t","200\t",1)
  b=row("submit",[100,20,1,100,0,0,0,50,0]).replace("1000\t","500\t",1)
  da=row("submit-detail",[100,20,1,30,20,10,10,5,3,2,99,44])
  db=row("submit-detail",[100,20,1,40,10,20,10,5,3,2,88,33])
  result=analyze([a,da,b,db]+base)["slowest_updates"][0]["graphics"]
  self.assertEqual(result["profiled_submissions"],2)
  self.assertEqual(result["history_prepare_ms"],.07)
  self.assertEqual(result["vertices_loaded"],187)
  self.assertEqual(result["history_stages_ms"]["geometry_keys"],.03)
 def test_truncated_or_malformed_rows(self):
  self.assertEqual(analyze([fixture()[1].rstrip()])["diagnostics"]["partial_record"],1)
  with self.assertRaises(ValueError):analyze(["0\tfunction-profile\txyz\n"])
if __name__=="__main__":unittest.main()
