import hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from scripts import prepare_native_shadow_filter as filter_source
from scripts.native_timing_spans import rewrite_source
from scripts.prepare_native_collision import Source

class NativeShadowFilterSourceTests(unittest.TestCase):
 def fixture(self,extra=''):
  body='#include "recomp.h"\nRECOMP_FUNC void synthetic(uint8_t* rdram, recomp_context* ctx) {\n'
  for i in range(4):
   pc=0x80010000+i*4
   body+=f'    // 0x{pc:08X}: synthetic\n    jfg_phase9_execution_probe_predecoded(0U, 0x{pc:08x}U, 0x24210001U, ctx);\n    ctx->r1 = U64(ADD32(ctx->r1, 1));\n'
  body+=extra+'\n}\n';source,counts=rewrite_source(body)
  return source,Source('shadow_filter','synthetic.c','synthetic',hashlib.sha256(source.encode()).hexdigest(),counts['spans'])
 def run_case(self,source,spec):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'baseline').mkdir();(root/'baseline'/spec.filename).write_text(source)
   with patch.object(filter_source,'SPEC',spec):
    result=filter_source.generate(root,root/'private/out.inc')
   return result,(root/'private/out.inc').read_text()
 def test_integer_operations_retained(self):
  source,spec=self.fixture();receipt,body=self.run_case(source,spec)
  self.assertEqual(body.count('ctx->r1 = U64(ADD32(ctx->r1, 1));'),4)
  self.assertEqual(receipt['source_sha256'],spec.sha256)
 def test_rejects_changed_source(self):
  source,spec=self.fixture()
  with self.assertRaises(ValueError):self.run_case(source+'\n',spec)
 def test_rejects_even_a_known_collision_callee(self):
  source,spec=self.fixture('    LOOKUP_FUNC(0x00317174)(rdram, ctx);\n')
  with self.assertRaisesRegex(ValueError,'closed leaf'):self.run_case(source,spec)
if __name__=='__main__':unittest.main()
