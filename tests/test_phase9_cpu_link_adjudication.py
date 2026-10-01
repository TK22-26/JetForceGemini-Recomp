import copy
import json
from pathlib import Path
import tempfile
import unittest
from scripts.phase9_cpu_link_adjudication import ROOT, check_capture, classify
from scripts.phase95_bridge import digest, runtime_digest
from scripts.phase9_cpu_links_trace import HEADER, expected, parse_trace, payload_words


class LinkAdjudicationTests(unittest.TestCase):
    def setUp(self):
        good = dict(matches_vr4300_manual=True,mismatches=[],cases=[{'case':i} for i in range(12)])
        self.items = [dict(runtime_sha256='old',observed={**good,'matches_vr4300_manual':False,
                        'mismatches':[{'case':i} for i in range(12)]}),
                      dict(runtime_sha256='reference',observed=good),
                      dict(runtime_sha256='new',observed=good),dict(runtime_sha256='new',observed=good)]

    def test_exact_red_green_is_not_game_or_hardware_approval(self):
        result = classify(*self.items)
        self.assertEqual(result['baseline_failures'],12)
        for field in ('hardware_tested','game_cause_proved','oracle_promoted','clock_alignment_validated'):
            self.assertFalse(result[field])

    def test_changed_or_missing_red_green_evidence_rejects(self):
        for index in range(4):
            rows = copy.deepcopy(self.items)
            rows[index]['observed']['matches_vr4300_manual'] = index == 0
            with self.assertRaises(ValueError): classify(*rows)
        rows = copy.deepcopy(self.items)
        rows[0]['observed']['mismatches'].pop()
        with self.assertRaises(ValueError): classify(*rows)

    def test_claimed_pass_with_different_raw_cases_rejects(self):
        rows = copy.deepcopy(self.items)
        rows[2]['observed'] = copy.deepcopy(rows[2]['observed'])
        rows[2]['observed']['cases'][0]['value'] = 4
        with self.assertRaisesRegex(ValueError,'raw cases'): classify(*rows)

    def test_old_or_inconsistent_runtime_cannot_be_repair(self):
        for identities in (('old','old'),('new','different')):
            rows = copy.deepcopy(self.items)
            rows[2]['runtime_sha256'],rows[3]['runtime_sha256'] = identities
            with self.assertRaisesRegex(ValueError,'runtime identity'): classify(*rows)


class LinkCaptureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        emulator = self.directory/'emulator'
        emulator.mkdir()
        (emulator/'EmuHawk.exe').write_bytes(b'fixture, not an emulator')
        self.rom = self.directory/'payload.n64'
        data = bytearray(2*1024*1024)
        lines = ['\t'.join(HEADER)]
        for case in range(12):
            pc = 0x80000420 + case*0x70
            slot, link, taken = expected(case, pc)
            lines.append('\t'.join(f'{word:08x}' for word in
                (case, pc, slot >> 32, slot & 0xffffffff, link >> 32, link & 0xffffffff, taken)))
            for relative, word in payload_words(case, pc).items():
                offset = 0x1000 + pc - 0x80000400 + relative
                data[offset:offset+4] = word.to_bytes(4, 'big')
        self.rom.write_bytes(data)
        trace = self.directory/'cpu-links.tsv'
        trace.write_text('\n'.join([*lines, 'result\ttrue\t12'])+'\n')
        self.config = {'PreferredCores': {'N64': 'Mupen64Plus'},
            'CoreSyncSettings': {'BizHawk.Emulation.Cores.Nintendo.N64.N64': {'Core': 1}}}
        self.write_json('input-config.json', self.config)
        self.manifest = {'schema': 1, 'kind': 'jfg-phase9-cpu-links-microtest',
            'acceptance': False, 'core': 'Mupen64Plus', 'mupen_cpu_core_override': 1,
            'rom_sha256': digest(self.rom), 'config_sha256': digest(self.directory/'input-config.json'),
            'input_config_sha256': digest(self.directory/'input-config.json'),
            'script_sha256': digest(ROOT/'scripts/phase9_cpu_links_probe.lua'),
            'emulator_sha256': digest(emulator/'EmuHawk.exe'),
            'runtime_sha256': runtime_digest(emulator)}
        self.result = {**self.manifest, 'complete': True, 'exit_code': 0,
            'trace_sha256': digest(trace), 'observed': parse_trace(trace)}
        self.write_json('manifest.json', self.manifest)
        self.write_json('result.json', self.result)

    def write_json(self, name, value):
        (self.directory/name).write_text(json.dumps(value)+'\n')

    def check(self):
        return check_capture(self.directory, self.rom, 'Mupen64Plus', 1, {})

    def test_uses_archived_launch_config_not_emuhawk_exit_config(self):
        self.write_json('emulator/config.ini', {'PreferredCores': {'N64': 'Ares64'}})
        receipt, payload = self.check()
        self.assertEqual(receipt, self.result)
        self.assertEqual(payload['checked_instruction_words'], 228)

    def test_missing_or_changed_archive_rejects(self):
        config = self.directory/'input-config.json'
        original = config.read_bytes()
        config.unlink()
        with self.assertRaises(FileNotFoundError): self.check()
        config.write_bytes(original+b' ')
        with self.assertRaisesRegex(ValueError, 'identity'): self.check()

    def test_empty_manifest_cannot_match_vacuously(self):
        self.write_json('manifest.json', {})
        with self.assertRaisesRegex(ValueError, 'manifest identity'): self.check()

    def test_changed_runtime_rejects(self):
        (self.directory/'emulator/new.dll').write_bytes(b'unpinned library')
        with self.assertRaisesRegex(ValueError, 'producer changed'): self.check()

    def test_raw_observation_must_match_report(self):
        self.result['observed']['cases'][0]['link_lo'] += 4
        self.write_json('result.json', self.result)
        with self.assertRaisesRegex(ValueError, 'raw trace'): self.check()

    def test_resealed_wrong_interpreter_still_rejects(self):
        self.config['CoreSyncSettings']['BizHawk.Emulation.Cores.Nintendo.N64.N64']['Core'] = 0
        self.write_json('input-config.json', self.config)
        for field in ('config_sha256', 'input_config_sha256'):
            self.manifest[field] = digest(self.directory/'input-config.json')
            self.result[field] = self.manifest[field]
        self.write_json('manifest.json', self.manifest)
        self.write_json('result.json', self.result)
        with self.assertRaisesRegex(ValueError, 'interpreter configuration'): self.check()
