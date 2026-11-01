import copy,json,tempfile,unittest
from pathlib import Path
from scripts import program_bundle as bundle
from scripts.rom_profiles import PROFILES_BY_CODE

def identity(code='us'):
    p=PROFILES_BY_CODE[code]
    parts={k:'4'*64 for k in bundle.BUILD_FIELDS if k!='build_sha256'}
    parts['build_sha256']=bundle.hashlib.sha256(bundle.canonical(dict(parts,revision_id=p.revision_id))).hexdigest()
    return dict(schema_version=2,kind='jfg-native-program-identity',revision_id=p.revision_id,rom_sha1=p.sha1,rom_size=p.size,
        descriptor_abi=1,binding_abi=3,program_model_sha256='1'*64,generation_input_sha256='2'*64,
        initial_tv_mode=0 if code=='pal' else 1,qualification='candidate',build_identity='msvc-x64',build=parts)

class ProgramBundleTests(unittest.TestCase):
    def manifest(self,directory,code='us'):
        files=[]
        for name in bundle.GAME_FILES:
            path=directory/name;path.write_bytes(b'synthetic host executable '+name.encode())
            files.append(dict(name=name,size=path.stat().st_size,sha256=bundle.digest(path)))
        value=dict(schema_version=1,kind='jfg-native-program-bundle',identity=identity(code),
            provenance={k:'3'*64 for k in ('source_inputs_sha256','generator_sha256','dependencies_sha256','build_receipt_sha256')},files=files)
        (directory/bundle.MANIFEST_NAME).write_text(json.dumps(value))
        return value
    def test_all_regional_identities_require_matching_catalog_abi_and_tv(self):
        for code in ('us','pal','jpn'):
            value=identity(code);self.assertEqual(bundle.validate_identity(value).code,code)
            for key,bad in [('rom_sha1','0'*40),('rom_size',123),('initial_tv_mode',2),('descriptor_abi',0),('binding_abi',True),('qualification','released')]:
                wrong=dict(value);wrong[key]=bad
                with self.assertRaises(ValueError):bundle.validate_identity(wrong)
    def test_changed_build_part_cannot_retain_the_same_compatibility_key(self):
        value=identity();value['build']['configuration_sha256']='5'*64
        with self.assertRaisesRegex(ValueError,'inconsistent'):bundle.validate_identity(value)
    def test_sidecar_cannot_relabel_us_as_pal(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d);self.manifest(path,'pal')
            with self.assertRaisesRegex(ValueError,'embedded'):bundle.verify(path,query=lambda p:identity('us'))
    def test_changed_library_incomplete_duplicate_traversal_fail(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d);value=self.manifest(path)
            self.assertEqual(bundle.verify(path,query=lambda p:identity())['identity'],identity())
            (path/'SDL2.dll').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'changed'):bundle.verify(path,query=lambda p:identity())
            for files in (value['files'][:-1],value['files']+[value['files'][0]],[dict(value['files'][0],name='../escape')]+value['files'][1:]):
                wrong=copy.deepcopy(value);wrong['files']=files
                with self.assertRaises(ValueError):bundle.validate_manifest(wrong)
    def test_wrong_selected_revision_and_duplicate_json_fail(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d);self.manifest(path)
            with self.assertRaisesRegex(ValueError,'another ROM'):bundle.verify(path,'jfg-pal-r0',query=lambda p:identity())
            (path/bundle.MANIFEST_NAME).write_text('{"schema_version":1,"schema_version":2}')
            with self.assertRaises(ValueError):bundle.read(path/bundle.MANIFEST_NAME)

if __name__=='__main__':unittest.main()
