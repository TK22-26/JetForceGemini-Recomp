"""ROM-free integration checks for actual Windows faults and live freeze capture."""
import argparse
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--fixture',required=True,type=Path)
    parser.add_argument('--capture',required=True,type=Path)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='jfg-support-fixture-') as temporary:
        root=Path(temporary)
        env=dict(os.environ,JFG_SUPPORT_LOG=str(root/'native.log'))
        crash=subprocess.run([str(args.fixture),'crash'],env=env,timeout=15,capture_output=True)
        assert crash.returncode==17,crash
        log=(root/'crash.log').read_text()
        assert 'native_exception=0xc0000005' in log,log
        frames=[s for s in log.splitlines() if s.startswith('frame=')]
        assert len(frames)>=3,log
        assert any('jfg-support-fixture.exe/' in s for s in frames),log
        assert str(root) not in log and 'capture=complete' in log
        with subprocess.Popen([str(args.fixture),'hang'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) as game:
            try:
                assert game.stdout.readline().strip()=='alive'
                kernel=ctypes.WinDLL('kernel32',use_last_error=True)
                kernel.GetProcessTimes.argtypes=[wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
                times=[wintypes.FILETIME() for _ in range(4)]
                assert kernel.GetProcessTimes(int(game._handle),*[ctypes.byref(t) for t in times])
                created=(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime
                result=subprocess.run([str(args.capture),str(game.pid),str(created)],capture_output=True,text=True,timeout=12)
                assert result.returncode==0,result.stdout+result.stderr
                assert 'snapshot=hang-v1' in result.stdout and 'capture=complete' in result.stdout,result.stdout
                assert result.stdout.count('frame=')>=3 and '/jfg-support-fixture.exe/' in result.stdout,result.stdout
                assert 'capture_scope=direct' in result.stdout
                assert len(result.stdout)<65536
                wrong=subprocess.run([str(args.capture),str(game.pid),str(created+1)],capture_output=True,timeout=12)
                assert wrong.returncode==3,wrong
                time.sleep(1.2)
                before=(root/'breadcrumbs.log').read_text()
                time.sleep(1.2)
                after=(root/'breadcrumbs.log').read_text()
                assert before!=after,'Process stopped making progress after capture'
                assert re.fullmatch(r'(breadcrumb=\d+/\d+/\d+/\d+\n)+',after)
                (args.capture.parent/'support-fixture-hang.log').write_text(result.stdout)
                (args.capture.parent/'support-fixture-crash.log').write_text(log)
            finally:
                game.terminate();game.wait(timeout=10)
    print('Windows support capture: fault context, multiple frames, hang snapshot, identity rejection, continued progress passed')

if __name__=='__main__':main()
