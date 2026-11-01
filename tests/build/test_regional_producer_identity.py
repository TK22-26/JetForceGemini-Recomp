"""Generator freshness follows actual local imports and non-Python inputs."""
from pathlib import Path
import tempfile,unittest
from scripts.regional.producer_identity import module_path,python_closure,source_paths

class ProducerClosureTests(unittest.TestCase):
    def test_transitive_and_relative_imports_follow_actual_domain_order(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            files={'scripts/__init__.py':'', 'scripts/build/start.py':'from scripts.regional import nested\n',
                'scripts/build/regional/__init__.py':'', 'scripts/build/regional/nested.py':'from .leaf import answer\n',
                'scripts/build/regional/leaf.py':'from scripts.helper import value\n',
                'scripts/diagnostics/helper.py':'value=1\n','scripts/helper.py':'raise RuntimeError("CLI shim")\n'}
            for name,text in files.items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
            actual={p.relative_to(root).as_posix() for p in python_closure(root,['scripts.start'])}
            self.assertEqual(actual,set(files)-{'scripts/helper.py'})
            self.assertEqual(module_path(root,'scripts.helper'),root/'scripts/diagnostics/helper.py')
            # Parsing must not import or execute any producer code.
            (root/'scripts/diagnostics/helper.py').write_text('raise RuntimeError("not executed")\n')
            self.assertEqual(actual,{p.relative_to(root).as_posix() for p in python_closure(root,['scripts.start'])})

    def test_missing_explicit_local_import_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'scripts/build').mkdir(parents=True)
            (root/'scripts/__init__.py').write_text('')
            (root/'scripts/build/start.py').write_text('import scripts.missing\n')
            with self.assertRaisesRegex(ValueError,'Missing local producer module'):
                python_closure(root,['scripts.start'])

    def test_real_closure_covers_subprocesses_templates_and_transitive_helpers(self):
        root=Path(__file__).resolve().parents[2]
        actual={p.relative_to(root).as_posix() for p in source_paths()}
        self.assertTrue({'scripts/__init__.py','scripts/build/native_program_identity.py',
            'scripts/build/prepare_generated_sources.py','scripts/build/generate_from_rom.py',
            'scripts/build/prepare_n64recomp_context_dump.py','scripts/build/apply_n64recomp_patchset.py',
            'src/bootstrap/production-audio-adapter.cpp','src/bootstrap/brokered-rsp.hpp',
            'include/jfg/boot/original_timing_fast.h','dependencies.lock.json',
            'patches/n64recomp/series.json'}<=actual)

if __name__=='__main__':unittest.main()
