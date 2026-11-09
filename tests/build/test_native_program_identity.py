import tempfile,unittest
from pathlib import Path
from scripts.native_program_identity import capture_source,capture_tree,capture_dependencies,fingerprint,validate_options,header
class NativeBuildIdentityTests(unittest.TestCase):
    def test_source_content_change_invalidates_identity_without_git_commit(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();source=root/'runtime.cpp';source.write_text('first')
            first=capture_source(root,[source]);source.write_text('second')
            self.assertNotEqual(fingerprint(first),fingerprint(capture_source(root,[source])))
            with self.assertRaises(ValueError):capture_source(root,[source,source])
            with self.assertRaises(ValueError):capture_source(root,[])
            with self.assertRaises(ValueError):capture_source(root,[root/'missing.cpp'])
    def test_default_capture_covers_includes_shaders_and_new_source_extensions(self):
        from scripts.native_program_identity import SOURCE_FOLDERS
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for folder in SOURCE_FOLDERS:(root/folder).mkdir(parents=True,exist_ok=True)
            (root/'CMakeLists.txt').write_text('project(fixture)')
            (root/'dependencies.lock.json').write_text('{}')
            sources=['src/flying.inl','src/effect.hlsl','src/custom.new-language']
            for name in sources:(root/name).write_text('first')
            first=capture_source(root)
            for name in sources:self.assertIn(name,first)
            for name in sources:
                (root/name).write_text('second')
                self.assertNotEqual(fingerprint(first),fingerprint(capture_source(root)))
                (root/name).write_text('first')
            cache=root/'scripts/build/__pycache__';cache.mkdir();(cache/'cached.pyc').write_bytes(b'bytecode')
            (cache/'transient.other').write_bytes(b'cache residue')
            self.assertEqual(first,capture_source(root))

    def test_actual_cpu_and_dependency_bytes_invalidate_unchanged_manifest_and_pin(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);generated=root/'generated';generated.mkdir();(generated/'sources.json').write_text('{}')
            cpu=generated/'body.c';cpu.write_text('return 1;');first=capture_tree(generated)
            cpu.write_text('return 2;');self.assertNotEqual(first,capture_tree(generated))
            (root/'dependencies.lock.json').write_text('{}');library=root/'dependency.lib';library.write_bytes(b'first compiled library')
            header=root/'headers';header.mkdir();(header/'runtime.h').write_text('first header')
            spec=dict(schema_version=1,headers={'runtime':str(header)},artifacts={'renderer':str(library)},variants={})
            first=capture_dependencies(root,spec);library.write_bytes(b'changed compiled library')
            self.assertNotEqual(first,capture_dependencies(root,spec));first=capture_dependencies(root,spec)
            (header/'runtime.h').write_text('changed header');self.assertNotEqual(first,capture_dependencies(root,spec))
            library.unlink()
            with self.assertRaisesRegex(ValueError,'compiled dependency'):capture_dependencies(root,spec)

    def test_configuration_and_target_are_part_of_compatibility_key(self):
        options=dict(schema_version=1,platform='windows-x64',compiler=dict(id='MSVC',version='19.44',target='x64',flags='/O2'),configuration='Release',options={'JFG_NATIVE_PLAY_OPTIMIZATIONS':True})
        first=fingerprint(validate_options(options));options['options']['JFG_NATIVE_PLAY_OPTIMIZATIONS']=False
        self.assertNotEqual(first,fingerprint(validate_options(options)))
        self.assertEqual(fingerprint({'a':1,'b':2}),fingerprint({'b':2,'a':1}))
        options['configuration']='Unspecified'
        with self.assertRaises(ValueError):validate_options(options)
    def test_header_rejects_paths_and_unbounded_identity_instead_of_embedding_them(self):
        with self.assertRaises(ValueError):header({'source_sha256':'C:/private/rom.z64'})
if __name__=='__main__':unittest.main()
