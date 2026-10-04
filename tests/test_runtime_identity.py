import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('runtime_identity',Path(__file__).resolve().parents[1]/'scripts/runtime_identity.py')
identity=importlib.util.module_from_spec(spec);spec.loader.exec_module(identity)

class IdentityTests(unittest.TestCase):
    def test_pe_codeview_excludes_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'test.exe'
            data=bytearray(1024);data[:2]=b'MZ';struct.pack_into('<I',data,60,128)
            data[128:132]=b'PE\0\0';struct.pack_into('<HH',data,132,0x8664,1)
            struct.pack_into('<H',data,148,240);struct.pack_into('<H',data,152,0x20b)
            struct.pack_into('<II',data,312,0x1000,28)
            struct.pack_into('<IIII',data,400,512,0x1000,512,512)
            struct.pack_into('<IIII',data,524,2,64,0x1040,576)
            data[576:600]=b'RSDS'+bytes(range(16))+struct.pack('<I',7)
            data[600:628]=b'C:\\PRIVATE-CANARY\\game.pdb\0'
            path.write_bytes(data)
            self.assertEqual(identity.codeview(path),bytes(range(16)).hex()+'-00000007')
            struct.pack_into('<I',data,544-8,10000000);path.write_bytes(data)
            with self.assertRaises(ValueError):identity.codeview(path)
    def test_rejects_non_pe(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'test.exe';path.write_bytes(b'not an executable')
            with self.assertRaises(ValueError):identity.codeview(path)

if __name__=='__main__':unittest.main()
