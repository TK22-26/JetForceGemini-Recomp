import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from scripts.diagnostics import proton_mouse_capture as capture

class ProtonMouseCaptureTests(unittest.TestCase):
    def test_only_pointer_function_prefixes_are_kept(self):
        line=b'123.456:00ab:00cd:trace:cursor:grab_clipping_window clipping to (1,2)-(2,3)\n'
        self.assertEqual(capture.filtered(line),('grab_clipping_window',line))
        for bad in (b'00ab:trace:event:X11DRV_KeyPress key SECRET\n',
                    b'00ab:trace:win:window_message title="trace:win:NtUserClipCursor SECRET"\n',
                    b'noise trace:cursor:grab_clipping_window SECRET\n',
                    line+b'x'*3000):
            self.assertIsNone(capture.filtered(bad))

    def test_policy_excludes_unrelated_registry_and_free_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'pfx').mkdir()
            (root/'pfx/user.reg').write_text('[Software\\\\Wine\\\\X11 Driver]\n"GrabPointer"="N"\n"Password"="SECRET"\n"Graphics"="/private/path"\n[Software\\\\Private]\n"GrabPointer"="SECRET"\n')
            self.assertEqual(capture.policy(root),{'Software\\\\Wine\\\\X11 Driver':{'GrabPointer':'N'}})

    def test_trace_bound_exit_status_and_report_allowlist(self):
        with tempfile.TemporaryDirectory(prefix='JFG capture spaces ') as tmp:
            root=Path(tmp);(root/'game').mkdir();(root/'game/JFG-Launcher.exe').write_bytes(b'fixture')
            report=root/'game/userdata/reports/session';report.mkdir(parents=True)
            for name in ('native.log','jfg.flash','game.z64'):(report/name).write_text('fixture-'+name)
            child="import sys;sys.stdout.write(('01:trace:cursor:grab_clipping_window rect\\n'*100)+'01:trace:event:X11DRV_KeyPress SECRET\\n'+'x'*10000+'01:trace:cursor:grab_clipping_window SECRET\\n');sys.exit(7)"
            with contextlib.redirect_stdout(io.StringIO()),patch.object(capture,'MAX_TRACE',600):
                code=capture.capture(root,[sys.executable,'-c',child])
            self.assertEqual(code,7)
            out=next(p for p in (root/'mouse-captures').iterdir() if p.is_dir())
            data=(out/'pointer-trace.log').read_bytes();self.assertLessEqual(len(data),600);self.assertNotIn(b'SECRET',data)
            receipt=json.loads((out/'receipt.json').read_text());self.assertGreater(receipt['function_counts']['grab_clipping_window'],0)
            self.assertFalse(receipt['resolution_claimed'])
            self.assertTrue((out/'game-reports/session/native.log').exists())
            self.assertFalse(any(p.suffix in ('.flash','.z64') for p in out.rglob('*')))
            self.assertTrue(out.with_suffix('.tar.gz').is_file())

    def test_command_arguments_are_not_shell_evaluated(self):
        with tempfile.TemporaryDirectory(prefix='JFG argument spaces ') as tmp:
            root=Path(tmp);(root/'game').mkdir();(root/'game/JFG-Launcher.exe').write_bytes(b'fixture')
            value='literal; $(not-a-command) with spaces'
            child='import sys;sys.exit(0 if sys.argv[1] == '+repr(value)+' else 9)'
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(capture.capture(root,[sys.executable,'-c',child,value]),0)

    def test_install_backs_up_tools_and_preserves_game(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source=base/'source';source.mkdir();root=base/'target spaces';(root/'game').mkdir(parents=True)
            (root/'game/JFG-Launcher.exe').write_bytes(b'owner game')
            for name in ('capture-proton-mouse.sh','proton_mouse_capture.py'):
                (source/name).write_text('new '+name);(root/name).write_text('old '+name)
            with contextlib.redirect_stdout(io.StringIO()):options=capture.install(source,root)
            self.assertIn(' -- %command% --portable --region usa',options)
            self.assertEqual((root/'game/JFG-Launcher.exe').read_bytes(),b'owner game')
            self.assertEqual(len(list((root/'mouse-capture-tools-backups').glob('*/proton_mouse_capture.py'))),1)
            with contextlib.redirect_stdout(io.StringIO()):capture.install(source,root)
            self.assertEqual(len(list((root/'mouse-capture-tools-backups').glob('*/proton_mouse_capture.py'))),1)

    def test_symlink_destination_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);outside=root/'outside';outside.mkdir();install=root/'install';install.mkdir()
            try:(install/'mouse-captures').symlink_to(outside,target_is_directory=True)
            except OSError as error:self.skipTest(str(error))
            with self.assertRaises(ValueError):capture.safe_file(install.resolve(),'mouse-captures')
            self.assertTrue(outside.exists())

    def test_missing_install_source_does_not_partly_replace_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source=base/'source';source.mkdir();root=base/'target';(root/'game').mkdir(parents=True)
            (root/'game/JFG-Launcher.exe').write_bytes(b'owner game')
            (source/'capture-proton-mouse.sh').write_text('new');(root/'capture-proton-mouse.sh').write_text('old')
            with self.assertRaises(ValueError):capture.install(source,root)
            self.assertEqual((root/'capture-proton-mouse.sh').read_text(),'old')

    def test_usb_copy_is_exact_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);archive=root/'capture.tar.gz';archive.write_bytes(b'fixture archive')
            target=capture.copy_capture(archive,root/'usb-results')
            self.assertEqual(target.read_bytes(),archive.read_bytes())
            with self.assertRaises(FileExistsError):capture.copy_capture(archive,root/'usb-results')
            with self.assertRaises(ValueError):capture.copy_capture(archive,root/'missing-drive/results')
            self.assertFalse((root/'missing-drive').exists())

    def test_missing_x11_display_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            capture.sample_x11(root,capture.threading.Event(),{})
            status=json.loads((root/'x11-status.json').read_text())
            self.assertFalse(status['available']);self.assertEqual(status['samples'],0)

if __name__=='__main__':unittest.main()
