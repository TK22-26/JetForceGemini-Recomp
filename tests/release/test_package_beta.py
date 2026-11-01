import json, tempfile, unittest, zipfile
from unittest import mock
from tests.build.test_program_bundle import identity
from scripts import program_bundle
from pathlib import Path
from scripts import package_beta as beta

class BetaPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.runtime=self.root/'runtime';self.runtime.mkdir()
        self.launcher=self.root/'launcher.exe';self.launcher.write_bytes(b'MZsynthetic-launcher')
        for name in beta.RUNTIME_FILES:(self.runtime/name).write_bytes(b'MZsynthetic-runtime')
        self.receipt=self.runtime/'jfg-native-boot.exe.support'
        self.receipt.write_text('build_dirty=0\nbuild_source=fixture\nbuild_runtime_sha256='+beta.digest(self.runtime/beta.RUNTIME_FILES[0])+'\n')
        self.output=self.root/'out'
        self.description=self.enterContext(mock.patch.object(program_bundle,'describe',side_effect=lambda path:identity('us')))
        self.write_manifest(self.runtime,'us')
    def write_manifest(self,directory,code):
        value=dict(schema_version=1,kind='jfg-native-program-bundle',identity=identity(code),
            provenance={k:'3'*64 for k in ('source_inputs_sha256','generator_sha256','dependencies_sha256','build_receipt_sha256')},
            files=[dict(name=name,size=(directory/name).stat().st_size,sha256=beta.digest(directory/name)) for name in beta.GAME_FILES])
        (directory/program_bundle.MANIFEST_NAME).write_text(json.dumps(value))

    def package(self):return beta.package(self.launcher,self.runtime,self.output,'1.0.1-beta.1')
    def test_allowlist_excludes_private_files(self):
        for name in ('game.z64','jfg.flash','debug.pdb','texture.png'):(self.runtime/name).write_bytes(b'PRIVATE-CANARY')
        archive=self.package()
        with zipfile.ZipFile(archive) as z:
            self.assertIsNone(z.testzip())
            self.assertFalse({'game.z64','jfg.flash','debug.pdb','texture.png'} & set(z.namelist()))
            manifest=json.loads(z.read('jfg-package.json'))
            self.assertEqual(manifest['schema'],2)
            self.assertEqual([v['revision_id'] for v in manifest['runtimes']],['jfg-us-r0'])
            bundled=json.loads(z.read('runtimes/jfg-us-r0/jfg-program.json'))
            self.assertEqual({e['name'] for e in bundled['files']},set(beta.RUNTIME_FILES))
    def test_identity_mismatch_rejected(self):
        (self.runtime/beta.RUNTIME_FILES[0]).write_bytes(b'MZchanged')
        with self.assertRaisesRegex(ValueError,'changed|differs'):self.package()
    def test_dirty_runtime_rejected(self):
        self.receipt.write_text(self.receipt.read_text().replace('build_dirty=0','build_dirty=1'))
        with self.assertRaisesRegex(ValueError,'clean runtime'):self.package()
    def test_missing_library_rejected(self):
        (self.runtime/'SDL2.dll').unlink()
        with self.assertRaisesRegex(ValueError,'Incomplete|missing'):self.package()
    def test_destination_preserved(self):
        self.output.mkdir();(self.output/'sentinel').write_text('keep')
        with self.assertRaisesRegex(ValueError,'Preserve'):self.package()
        self.assertEqual((self.output/'sentinel').read_text(),'keep')
    def test_each_missing_crt_library_is_rejected(self):
        for name in beta.VC_RUNTIME_FILES:
            with self.subTest(name=name):
                path=self.runtime/name;data=path.read_bytes();path.unlink()
                with self.assertRaisesRegex(ValueError,'Incomplete|missing'):self.package()
                path.write_bytes(data)
    def test_explicit_crt_directory_is_used(self):
        crt=self.root/'redist';crt.mkdir()
        for name in beta.VC_RUNTIME_FILES:
            (self.runtime/name).unlink();(crt/name).write_bytes(b'MZredistributable')
        archive=beta.package(self.launcher,self.runtime,self.output,'1.0.1-beta.2',crt)
        with zipfile.ZipFile(archive) as z:
            for name in beta.VC_RUNTIME_FILES:self.assertEqual(z.read('runtimes/jfg-us-r0/'+name),b'MZredistributable')

    def test_duplicate_revision_is_rejected_before_output(self):
        with self.assertRaisesRegex(ValueError,'Duplicate runtime revision'):
            beta.package(self.launcher,[self.runtime,self.runtime],self.output,'1.0.1-beta.1')
        self.assertFalse(self.output.exists())
    def test_unadmitted_revision_cannot_be_published_by_renaming_a_folder(self):
        self.write_manifest(self.runtime,'pal');self.description.side_effect=lambda path:identity('pal')
        with self.assertRaisesRegex(ValueError,'admission is closed'):self.package()
        self.assertFalse(self.output.exists())
    def test_three_revision_package_preserves_each_embedded_identity(self):
        from scripts.rom_profiles import RomProfile
        runtimes=[self.runtime]
        for code in ('pal','jpn'):
            directory=self.root/code;directory.mkdir()
            for name in beta.RUNTIME_FILES:(directory/name).write_bytes(b'MZsynthetic-runtime')
            (directory/'jfg-native-boot.exe.support').write_bytes(self.receipt.read_bytes())
            self.write_manifest(directory,code);runtimes.append(directory)
        def describe(path):
            return json.loads((path.parent/program_bundle.MANIFEST_NAME).read_text())['identity']
        self.description.side_effect=describe
        # Isolated fixture admission only; production PAL/JP gates stay closed.
        with mock.patch.object(RomProfile,'native_supported',new_callable=mock.PropertyMock,return_value=True):
            archive=beta.package(self.launcher,runtimes,self.output,'1.0.1-beta.1')
        with zipfile.ZipFile(archive) as z:
            manifest=json.loads(z.read('jfg-package.json'))
            self.assertEqual(len(manifest['runtimes']),3)
            for entry in manifest['runtimes']:
                path='runtimes/'+entry['revision_id']+'/jfg-program.json'
                self.assertEqual(json.loads(z.read(path))['identity']['revision_id'],entry['revision_id'])
                self.assertEqual(beta.hashlib.sha256(z.read(path)).hexdigest(),entry['manifest_sha256'])
