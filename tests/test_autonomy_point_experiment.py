import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.autonomy import point_plan, point_observation as observation, point_runtime, point_experiment, point_anchors
from scripts.autonomy import state_word_experiment as words, entry_plan, experiment_plan
from scripts.autonomy.supervisor import SupervisorError


def plan():
    return {"operation":"point-state", "hypothesis":"extra receive", "alternative":"same receive count", "reason":"measure calls",
            "probe":{"entry_pc":"0x80000200", "call_pc":"0x80000100", "pcs":["0x80000200","0x80000204","0x80000108"],
                     "words":["0x800a9e90","0x80000004"]},
            "prediction":{"kind":"event-count", "pc":"0x80000204", "update":7, "occurrence":None,
                          "register":None, "address":None, "relation":"different"}}


class PointPlanTests(unittest.TestCase):
    def test_schema_contract_and_explicit_unsupported(self):
        p=plan(); c=point_plan.contract([7,8],"1"*64)
        self.assertEqual(point_plan.validate(p,c),p)
        point_plan.validate(dict(p,operation="needs-instrumentation",probe=None,prediction=None),c)
        for field,value in (("argv",["exec"]),("output","outside"),("reason","x"*601)):
            with self.assertRaises(ValueError):
                point_plan.validate(dict(p,**{field:value}),c)

    def test_bounds_anchor_thread_and_device_reads(self):
        for key,value in (("pcs",["0x80000200"]),("words",[]),("words",["0xa0000000"]),
                          ("call_pc","0x80000101"),("pcs",["0x80000200"]*17)):
            p=plan(); p["probe"][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                point_plan.validate(p,point_plan.contract([7,8],"1"*64))

    def test_prediction_kinds_do_not_mix_fields(self):
        for kind in ("register","word"):
            p=plan(); p["prediction"].update(kind=kind,occurrence=1,
                 register=5 if kind=="register" else None,address="0x80000004" if kind=="word" else None)
            point_plan.validate(p,point_plan.contract([7,8],"1"*64))
        for key,value in (("occurrence",1),("update",9),("pc","0x80000004"),("register",True)):
            p=plan(); p["prediction"][key]=value
            with self.assertRaises(ValueError):
                point_plan.validate(p,point_plan.contract([7,8],"1"*64))

    def test_no_repeat_by_changing_prediction_or_adding_irrelevant_pc(self):
        original=plan(); p=plan()
        p["probe"]["pcs"].append("0x80000208")
        p["prediction"]["update"]=8
        with self.assertRaisesRegex(ValueError,"repeats"):
            point_plan.validate(p,point_plan.contract([7,8],"1"*64,[original]))
        p["prediction"]["pc"]="0x80000208"
        point_plan.validate(p,point_plan.contract([7,8],"1"*64,[original]))
        with self.assertRaisesRegex(ValueError,"round budget"):
            point_plan.validate(p,point_plan.contract([7,8],"1"*64,[original]*3))

    def test_mixed_history_does_not_reset_other_method_budgets(self):
        history=[plan(),{"operation":"state-words","observations":[{"address":"0x80000004","width":4}]}]
        self.assertEqual(point_plan.contract([7,8],"1"*64,history)["round"],2)
        self.assertEqual(entry_plan.contract([7,8],history)["round"],1)
        self.assertEqual(experiment_plan.contract([7,8],history)["round"],2)


class PointObservationTests(unittest.TestCase):
    def rows(self,oracle=False):
        rows=[]
        for pc in [0x80000200]+[0x80000204]*(2 if oracle else 1)+[0x80000108]:
            row={f"r{i}_{part}":0 for i in range(32) for part in ("lo","hi")}
            row.update(pc=pc,opcode=0,r29_lo=0x80001000,r31_lo=0x80000108,m800a9e90=0x800f92a0,
                       m80000004=4 if oracle else 3,controller_polls=17)
            row.update({"completed_updates":6,"frame":22,"consumed_vi":20} if oracle else {"update_candidate":7,"vi_retraces":20})
            rows.append(row)
        return rows

    def measure(self,p=None,mutation=None):
        p=plan() if p is None else p
        def read(path,*args,oracle):
            rows=self.rows(oracle)
            if oracle:
                if mutation=="caller": rows[0]["r31_lo"]=0
                if mutation=="poll": rows[0]["controller_polls"]+=1
                if mutation=="thread": rows[-1]["m800a9e90"]=0
                if mutation=="duplicate": rows.insert(0,rows[0].copy())
                if mutation=="opcode": rows[0]["opcode"]=1
            return rows
        def snapshot(directory,*args):
            image=bytearray(4*1024*1024)
            if mutation=="snapshot" and str(directory).startswith("capture"):
                image[0]=1
            return bytes(image),{}
        with patch.object(observation.phase9_point_probe,"read",side_effect=read), \
                patch.object(observation,"instruction_evidence",return_value=[]), \
                patch.object(observation,"_snapshot",side_effect=snapshot),patch.object(observation,"_records_at",return_value={7:{}}):
            return observation.measure(Path("capture"),Path("reference"),p,[7,7],traces_unchanged=mutation!="trace")

    def test_count_prediction_allows_different_internal_event_counts(self):
        result=self.measure()
        self.assertTrue(result["qualification"]["passed"])
        self.assertTrue(result["prediction_observed"])
        self.assertEqual(result["observations"][0]["native"],1)
        self.assertEqual(result["observations"][0]["oracle"],2)
        self.assertIn("raw_events",result)
        self.assertFalse(result["alignment_validated"])
        self.assertFalse(result["causal_fix_proved"])

    def test_anchor_value_is_not_invalidated_by_later_internal_path(self):
        p=plan(); p["prediction"].update(kind="word",pc="0x80000200",occurrence=1,address="0x80000004")
        result=self.measure(p)
        self.assertTrue(result["qualification"]["passed"])
        self.assertTrue(result["prediction_observed"])

    def test_missing_value_occurrence_is_inconclusive(self):
        p=plan(); p["prediction"].update(kind="register",occurrence=2,register=5)
        result=self.measure(p)
        self.assertFalse(result["qualification"]["passed"])
        self.assertIsNone(result["prediction_observed"])

    def test_invalid_correspondence_and_changed_observations_are_inconclusive(self):
        for mutation in ("caller","thread","poll","duplicate","snapshot","trace"):
            with self.subTest(mutation=mutation):
                result=self.measure(mutation=mutation)
                self.assertFalse(result["qualification"]["passed"])
                self.assertIsNone(result["prediction_observed"])

    def test_changed_instruction_bytes_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"opcodes"):
            self.measure(mutation="opcode")


class PointWorkflowTests(unittest.TestCase):
    def test_unsupported_proposal_with_anchor_facts_is_not_retried(self):
        from unittest.mock import MagicMock
        store=MagicMock(); parent="entry-plan"
        job_id=words.identity("point-plan-",parent)
        store.status_projection.return_value={"jobs":[{"job_id":job_id,"state":"passed"}]}
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(point_experiment,"plan_context",return_value={"plan":{"operation":"needs-instrumentation"}}), \
                patch.object(point_experiment,"has_anchors",return_value=True), \
                patch.object(point_experiment,"queue_plan",side_effect=AssertionError("must not repeat")):
            self.assertEqual(point_experiment.next_job(store,None,Path(temporary),None,parent),job_id)

    def test_anchor_inventory_decodes_stable_retained_instructions_only(self):
        image=bytearray(4*1024*1024)
        image[0x100:0x104]=(0x0c000080).to_bytes(4,"big")
        image[0x200:0x204]=(0x27bdfff8).to_bytes(4,"big")
        with patch.object(point_anchors,"_records_at",return_value={7:{},8:{}}), \
                patch.object(point_anchors,"_snapshot",return_value=(bytes(image),{})):
            facts=point_anchors.inventory(Path("reference"),[7,8],{"next_test":"observe producer 0x80000200"})
        self.assertEqual(facts["candidates"],[{"entry_pc":"0x80000200","call_pc":"0x80000100","return_pc":"0x80000108",
                    "call_opcode":"0x0c000080","delay_slot":"0x00000000","entry_opcode":"0x27bdfff8"}])
        self.assertFalse(facts["alignment_validated"])
        changed=bytearray(image); changed[0x104]=1
        with patch.object(point_anchors,"_records_at",return_value={7:{}}), \
                patch.object(point_anchors,"_snapshot",side_effect=[(bytes(image),{}),(bytes(changed),{})]):
            self.assertEqual(point_anchors.inventory(Path("reference"),[7,7],{"next_test":"0x80000200"})["candidates"],[])

    def test_trace_seals_and_manifest_are_rechecked_on_consumption(self):
        from scripts.autonomy.update_job import point_trace_pins
        from scripts.phase95_bridge import digest
        from scripts.phase9_point_probe import PHASE
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); manifests=[]
            for side in ("native","oracle"):
                directory=root/side; directory.mkdir()
                clocks=["frame","completed_updates","controller_polls","consumed_vi"] if side=="oracle" else ["update_candidate","vi_retraces","controller_polls"]
                header=clocks+["pc","opcode"]+[f"r{i}_{part}" for i in range(32) for part in ("lo","hi")]+["m800a9e90","m80000004"]
                row=(["20","6","17","18"] if side=="oracle" else ["7","18","17"])+["0x80000200","0x00000000"]+["0x00000000"]*66
                path=directory/"point-probe.tsv"
                path.write_text("\t".join(header)+"\n"+"\t".join(row)+"\n"+("result\ttrue\t1\n" if side=="oracle" else ""))
                manifests.append({"point_probe":{"complete":True,"pcs":[int(x,16) for x in plan()["probe"]["pcs"]],
                    "words":[0x800a9e90,0x80000004],"phase":PHASE,"sha256":digest(path),"events":1}})
            packet={"point_probe":plan()["probe"],"focus_updates":[7,8]}
            self.assertEqual(set(point_trace_pins(packet,root,*manifests)),{"native/point-probe.tsv","oracle/point-probe.tsv"})
            manifests[0]["point_probe"]["events"]=2
            with self.assertRaisesRegex(SupervisorError,"count"):
                point_trace_pins(packet,root,*manifests)
            manifests[0]["point_probe"]["events"]=1
            path=root/"native/point-probe.tsv"; path.write_text(path.read_text()+"changed\n")
            with self.assertRaisesRegex(SupervisorError,"hash"):
                point_trace_pins(packet,root,*manifests)

    def test_missing_runtime_and_pause_do_not_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            state=Path(temporary)
            self.assertIsNone(point_runtime.load(None,None,state,{"baseline_id":"baseline"}))
            (state/"PAUSED").touch()
            self.assertIsNone(point_experiment.next_job(None,None,state,None,"parent"))
            self.assertEqual(point_experiment.advance(None,None,state,None),[])

    def test_cycles_stop_before_reading_files(self):
        for chain in (("p",),tuple(str(i) for i in range(words.MAX_PLAN_CHAIN))):
            with self.assertRaisesRegex(SupervisorError,"cyclic"):
                point_experiment.plan_context(None,None,None,"p",chain=chain)

    def test_point_history_uses_point_consumer(self):
        from unittest.mock import MagicMock
        store=MagicMock(); store.job.return_value={"spec":{"inputs":["point-experiment:fixture"]}}
        with patch.object(point_experiment,"checked_observation",return_value={"checked":True}) as checked:
            self.assertEqual(words.checked_observation(store,None,None,"observation"),{"checked":True})
            checked.assert_called_once()


if __name__ == "__main__":
    unittest.main()
