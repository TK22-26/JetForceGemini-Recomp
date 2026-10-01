import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.autonomy import interval_experiment as experiment
from scripts.autonomy import state_word_experiment as words
from scripts.autonomy.supervisor import SupervisorError, canonical_bytes, file_sha256
from tests.test_autonomy_interval_experiment import proposal


class IntervalRefreshTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        self.state = self.repo / 'tools/private/autonomy'
        self.state.mkdir(parents=True)
        self.store = MagicMock()
        self.store.status_projection.return_value = {'jobs': []}
        self.parent_id = words.identity('point-plan-', 'entry')
        self.base = words.identity(experiment.PLAN_PREFIX, self.parent_id)
        self.refreshed = self.base + experiment.OPERAND_SUFFIX
        self.unsupported = dict(proposal(), operation='needs-instrumentation', probe=None, selection=None, prediction=None)
        self.parent = {'plan_id': self.parent_id, 'entry_plan_id': 'entry', 'plan': self.unsupported,
            'point_runtime': {'binding': words.pin(self.write('binding.json')),
                              'reference': {'capture_seal': self.state / 'reference/result.json'}},
            'window': [7, 8], 'history': [], 'baseline_id': 'baseline',
            'baseline_packet': {'source_commit': 'a' * 40,
                'pin_files': {key: str(self.write(key)) for key in ('native', 'rom', 'emulator')}},
            'diagnosis': {'next_test': 'branch at 0x80000114'}}
        for key in ('plan_seal', 'plan_message', 'diagnosis_message', 'baseline_seal'):
            self.parent[key] = self.write(key)
        self.facts = {'schema': 1, 'known_counts': [], 'retained_probe': proposal()['probe'],
            'point_facts': {'candidates': [], 'prior_observations': [],
                'runtime_calibration': {'qualification': {'passed': True}, 'measurements': {}}}}
        self.new_facts = {**copy.deepcopy(self.facts), 'schema': 2, 'instruction_context': {
            'sites': [{'pc': '0x80000114', 'operand_register': 15, 'load_base_register': 14,
                'load_offset': 8, 'link_call_pc': '0x80000100', 'callee': '0x80000400',
                'conditional_raw_ra': '0x80000108'}], 'execution_observed': False}}
        self.packets, self.seals = {}, {}
        self.addCleanup(patch.stopall)
        patch('scripts.autonomy.supervisor._git_ok', return_value='a' * 40).start()
        patch.object(experiment, 'enqueue_packet', side_effect=self.enqueue).start()
        patch.object(experiment, '_sealed_result', side_effect=lambda store, state, name, prefix: self.seals[name]).start()
        self.facts_mock = patch.object(experiment, 'facts_for', side_effect=lambda context, operands=False:
                                      copy.deepcopy(self.new_facts if operands else self.facts)).start()
        self.parent_mock = patch.object(experiment.point_experiment, 'plan_context', return_value=self.parent).start()
        experiment.queue_plan(self.store, self.repo, self.state, None, self.parent_id)
        self.seal(self.base, self.unsupported)
        self.context = experiment.plan_context(self.store, self.repo, self.state, self.base)

    def write(self, name, value=None):
        path = self.state / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical_bytes({} if value is None else value))
        return path

    def enqueue(self, store, state, packet, agent):
        self.packets[packet['job_id']] = packet
        self.write('packets/' + packet['job_id'] + '.json', packet)
        self.store.status_projection.return_value['jobs'].append({'job_id': packet['job_id'], 'state': 'queued'})

    def seal(self, name, plan):
        packet = self.packets[name]
        message = self.write('attempts/' + name + '/0001/last-message.txt', plan)
        digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
        job = {'spec': {'inputs': ['packet:' + digest], 'prerequisites': packet['prerequisites'], 'pins': {}}}
        result = {'packet_sha256': digest, 'pins': {}, 'experiment_plan_sha256': file_sha256(message),
                  'experiment_schema_sha256': file_sha256(experiment.interval_plan.SCHEMA_FILE)}
        seal = self.write('attempts/' + name + '/0001/result.json', result)
        self.seals[name] = job, result, seal
        for row in self.store.status_projection.return_value['jobs']:
            if row['job_id'] == name:
                row['state'] = 'passed'

    def refresh(self):
        return experiment.queue_refresh(self.store, self.repo, self.state, None, self.context)

    def test_refresh_keeps_old_bytes_and_pins_predecessor_with_new_facts(self):
        old_packet = (self.state / 'packets' / (self.base + '.json')).read_bytes()
        old_facts = experiment.facts_path(self.state, self.parent_id).read_bytes()
        self.assertEqual(self.refresh(), self.refreshed)
        packet = self.packets[self.refreshed]
        self.assertEqual(packet['prerequisites'], [self.parent_id, 'baseline', self.base])
        self.assertIn(words.pin(self.context['plan_seal']), packet['evidence_files'])
        self.assertIn(words.pin(self.context['plan_message']), packet['evidence_files'])
        new_path = experiment.facts_path(self.state, self.parent_id, operands=True)
        self.assertIn(words.pin(new_path), packet['evidence_files'])
        self.assertEqual(json.loads(new_path.read_text()), self.new_facts)
        self.assertIn('conditional_raw_ra', packet['prompt'])
        self.assertIn('NOT observed execution', packet['prompt'])
        self.assertEqual(old_packet, (self.state / 'packets' / (self.base + '.json')).read_bytes())
        self.assertEqual(old_facts, experiment.facts_path(self.state, self.parent_id).read_bytes())
        self.assertEqual(packet['retry_budget'], 0)
        self.assertEqual(packet['allowed_paths'], [])

    def test_refresh_requires_new_sites_and_available_round_budget(self):
        self.new_facts['instruction_context']['sites'] = []
        self.assertIsNone(self.refresh())
        self.context['plan_packet']['experiment_contract']['round'] = 4
        self.facts_mock.reset_mock()
        self.assertIsNone(self.refresh())
        self.facts_mock.assert_not_called()
        self.assertNotIn(self.refreshed, self.packets)

    def test_no_second_refresh_or_failed_job_retry(self):
        self.refresh()
        for status in ('queued', 'running', 'failed', 'blocked', 'passed'):
            for row in self.store.status_projection.return_value['jobs']:
                if row['job_id'] == self.refreshed:
                    row['state'] = status
            self.assertIsNone(self.refresh())
            self.assertEqual(experiment.preferred_plan_id(self.packets, self.parent_id), self.refreshed)
            if status != 'passed':
                self.assertEqual(experiment.next_job(self.store, self.repo, self.state, None, self.parent_id), self.refreshed)
        self.seal(self.refreshed, self.unsupported)
        context = experiment.plan_context(self.store, self.repo, self.state, self.refreshed)
        self.assertIsNone(experiment.queue_refresh(self.store, self.repo, self.state, None, context))

    def test_pause_supported_plan_and_historical_point_cannot_refresh(self):
        self.context['plan'] = proposal()
        self.assertIsNone(self.refresh())
        self.context['plan'] = self.unsupported
        (self.state / 'PAUSED').touch()
        self.assertIsNone(self.refresh())
        (self.state / 'PAUSED').unlink()
        self.store.status_projection.return_value['jobs'].append({'job_id': self.parent_id + '-history-v2', 'state': 'passed'})
        self.assertIsNone(self.refresh())

    def test_consumer_recomputes_both_fact_versions_with_one_full_parent_walk(self):
        self.refresh()
        self.seal(self.refreshed, proposal())
        self.parent_mock.reset_mock()
        self.facts_mock.reset_mock()
        context = experiment.plan_context(self.store, self.repo, self.state, self.refreshed)
        self.parent_mock.assert_called_once()
        self.assertEqual(len(self.facts_mock.call_args_list), 2)
        self.assertEqual(context['plan'], proposal())
        self.assertIs(context['point_context'], self.parent)

    def test_repinning_forged_source_facts_cannot_satisfy_consumer(self):
        self.refresh()
        self.seal(self.refreshed, proposal())
        path = experiment.facts_path(self.state, self.parent_id, operands=True)
        original_pin = words.pin(path)
        forged = copy.deepcopy(self.new_facts)
        forged['instruction_context']['sites'][0]['conditional_raw_ra'] = '0x80000999'
        path.write_bytes(canonical_bytes(forged))
        packet = self.packets[self.refreshed]
        packet['evidence_files'] = [words.pin(path) if pin == original_pin else pin for pin in packet['evidence_files']]
        self.write('packets/' + self.refreshed + '.json', packet)
        self.seal(self.refreshed, proposal())
        with self.assertRaisesRegex(SupervisorError, 'checked predecessor facts'):
            experiment.plan_context(self.store, self.repo, self.state, self.refreshed)

    def test_changed_snapshot_facts_or_original_supported_plan_reject_refresh(self):
        self.refresh()
        self.seal(self.refreshed, proposal())
        self.new_facts['instruction_context']['sites'] = []
        with self.assertRaisesRegex(SupervisorError, 'checked predecessor facts'):
            experiment.plan_context(self.store, self.repo, self.state, self.refreshed)
        self.seal(self.base, proposal())
        # Re-pin the changed predecessor: even valid hashes cannot make a
        # supported plan eligible for the unsupported-only successor.
        packet = self.packets[self.refreshed]
        for key in ('plan_seal', 'plan_message'):
            path = self.context[key]
            packet['evidence_files'] = [words.pin(path) if pin['path'] == str(path) else pin for pin in packet['evidence_files']]
        self.write('packets/' + self.refreshed + '.json', packet)
        self.seal(self.refreshed, proposal())
        with self.assertRaisesRegex(SupervisorError, 'unsupported predecessor'):
            experiment.plan_context(self.store, self.repo, self.state, self.refreshed)

    def test_instruction_decoder_is_in_measurement_dependency_closure(self):
        original = experiment.file_sha256
        before = experiment.tool_sha()
        with patch.object(experiment, 'file_sha256', side_effect=lambda path:
                '0' * 64 if Path(path) == Path(experiment.instruction_context.__file__) else original(path)):
            self.assertNotEqual(experiment.tool_sha(), before)


if __name__ == '__main__':
    unittest.main()
