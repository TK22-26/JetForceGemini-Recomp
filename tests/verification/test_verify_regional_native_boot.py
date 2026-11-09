import copy,json,unittest
from scripts.verify_regional_native_boot import require_matching_identities,validate_original_os_result
from scripts.rom_profiles import PROFILES_BY_CODE
from tests.build.test_program_bundle import identity

class RegionalBootIdentityTests(unittest.TestCase):
    def test_every_target_requires_exact_program_corpus_and_oracle_identity(self):
        for code,profile in PROFILES_BY_CODE.items():
            runtime=identity(code)
            corpus=dict(version=7,revision_id=profile.revision_id,program_model_sha256=runtime['program_model_sha256'],generation_input_sha256=runtime['generation_input_sha256'])
            oracle=dict(revision_id=profile.revision_id,rom_sha1=profile.sha1)
            require_matching_identities(profile,runtime,corpus,oracle)
            for bad in ({},dict(oracle,rom_sha1='0'*40),dict(oracle,revision_id='other')):
                with self.subTest(code=code),self.assertRaises(ValueError):require_matching_identities(profile,runtime,corpus,bad)
            bad=copy.deepcopy(corpus);bad['generation_input_sha256']='0'*64
            with self.assertRaises(ValueError):require_matching_identities(profile,runtime,bad,oracle)
            other=identity('pal' if code=='us' else 'us')
            with self.assertRaises(ValueError):require_matching_identities(profile,other,corpus,oracle)


class OriginalOsObservationTests(unittest.TestCase):
    def sample(self):
        return dict(kind='jfg-phase9-original-os-probe',acceptance=False,status='retrace-target',poll_target=0,
            retrace_target=200,vi_retraces=200,controller_samples=70,completed_updates=0,cpu_count=12345678,
            instructions=1234567,graphics_tasks=90,decoded_audio_tasks=80,unsupported_accesses=0,
            runtime_snapshot_complete=False,state_hash='0123456789abcdef'*4)
    def test_current_backend_and_exact_boundary(self):
        value=self.sample();self.assertEqual(validate_original_os_result(json.dumps(value),200),value)
        for key,bad in [('kind','jfg-phase6-native-boot'),('poll_target',1),('vi_retraces',201),('retrace_target',199),
                ('acceptance',True),('runtime_snapshot_complete',True),('unsupported_accesses',1),
                ('unsupported_accesses',False),('instructions',True),('cpu_count',0),('cpu_count',2**64),
                ('controller_samples',-1),('state_hash','not-a-hash')]:
            wrong=dict(value);wrong[key]=bad
            with self.subTest(key=key,bad=bad),self.assertRaises(ValueError):validate_original_os_result(json.dumps(wrong),200)
    def test_duplicate_extra_and_nonobject_records_rejected(self):
        value=json.dumps(self.sample())
        for bad in (value+value,'[]',value.replace('"acceptance": false','"acceptance": false, "acceptance": true')):
            with self.assertRaises(ValueError):validate_original_os_result(bad,200)
        for count in (True,2,6001):
            with self.assertRaises(ValueError):validate_original_os_result(value,count)

if __name__=='__main__':unittest.main()
