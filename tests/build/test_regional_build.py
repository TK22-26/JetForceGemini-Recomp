import tempfile,unittest
from pathlib import Path
from scripts.build_from_rom import prepare_play_profile,require_build_admission
from scripts.rom_profiles import PROFILES_BY_CODE
class RegionalBuildTests(unittest.TestCase):
    def test_compilation_does_not_admit_unqualified_play(self):
        for code in ('pal','jpn'):
            p=PROFILES_BY_CODE[code]
            with self.assertRaises(ValueError):require_build_admission(p)
            require_build_admission(p,candidate=True)
            with self.assertRaises(ValueError):require_build_admission(p,candidate=True,play=True)
    def test_save_namespaces_preserve_us_and_reject_ambiguous_regional_saves(self):
        with tempfile.TemporaryDirectory() as d:
            shared=Path(d)/'campaign';us,pal,jp=[PROFILES_BY_CODE[c] for c in ('us','pal','jpn')]
            self.assertEqual(prepare_play_profile(shared,us),shared)
            (shared/'jfg.flash').write_bytes(b'historical US save')
            target=prepare_play_profile(shared,pal)
            self.assertEqual(target,shared/'revisions'/pal.revision_id)
            self.assertEqual((target/'rom-revision.txt').read_bytes(),('jfg-save-namespace-1\n'+pal.revision_id+'\n'+pal.sha1+'\n').encode())
            (target/'rom-revision.txt').write_text('wrong revision')
            with self.assertRaises(ValueError):prepare_play_profile(shared,pal)
            japanese=shared/'revisions'/jp.revision_id;japanese.mkdir();(japanese/'jfg.flash').write_bytes(b'unmarked save')
            with self.assertRaises(ValueError):prepare_play_profile(shared,jp)
            self.assertEqual((shared/'jfg.flash').read_bytes(),b'historical US save')

    def test_profile_marker_requires_exact_shared_contract_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            us=PROFILES_BY_CODE['us'];target=prepare_play_profile(Path(d)/'campaign',us)
            marker=target/'rom-revision.txt';valid=marker.read_bytes()
            marker.write_bytes(valid.replace(b'\n',b'\r\n'))
            with self.assertRaises(ValueError):prepare_play_profile(target,us)
            self.assertEqual(marker.read_bytes(),valid.replace(b'\n',b'\r\n'))
