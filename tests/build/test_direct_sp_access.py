import hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from scripts import prepare_direct_sp_access as sp

class DirectSpSourceTests(unittest.TestCase):
 def source(self):
  return ('#include "recomp.h"\n#include "funcs.h"\n'
   'RECOMP_FUNC void synthetic(uint8_t* rdram, recomp_context* ctx) {\n'
   '    jfg_phase9_execution_probe_predecoded(1U, 2U, 3U, ctx);\n'
   '    MEM_W(-0X4, ctx->r29) = (int32_t)(ctx->r31);\n'
   '    ctx->r5 = U64(MEM_W(ctx->r14, 0X10));\n'
   '    LOOKUP_FUNC(0x80000000)(rdram, ctx);\n}\n')
 def test_word_operands_and_probes_preserved(self):
  text,counts=sp.rewrite(self.source(),'synthetic')
  self.assertEqual(counts,{'loads':1,'stores':1})
  self.assertIn('jfg_sp_store_word(rdram, ctx->r29, -0X4, (int32_t)(ctx->r31));',text)
  self.assertIn('ctx->r5 = U64(jfg_sp_load_word(rdram, ctx->r14, 0X10));',text)
  self.assertIn('jfg_phase9_execution_probe_predecoded(1U, 2U, 3U, ctx);',text)
  self.assertIn('LOOKUP_FUNC(0x80000000)(rdram, ctx);',text)
 def test_digest_rejection_does_not_overwrite_output(self):
  with tempfile.TemporaryDirectory()as d:
   root=Path(d);(root/'baseline').mkdir();source=self.source()
   (root/'baseline/synthetic.c').write_text(source+'\n');output=root/'out.inc';output.write_text('retained')
   with patch.object(sp,'SPECS',[('synthetic',hashlib.sha256(source.encode()).hexdigest(),0x80000000)]):
    with self.assertRaisesRegex(ValueError,'Pinned SP'):sp.generate(root,output)
   self.assertEqual(output.read_text(),'retained')
 def test_unknown_function_rejected(self):
  with self.assertRaisesRegex(ValueError,'one pinned routine'):sp.rewrite(self.source(),'other')
if __name__=='__main__':unittest.main()
