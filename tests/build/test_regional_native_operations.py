import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from scripts.regional.native_operations import OPERATIONS,create,validate
class NativeOperationsTests(unittest.TestCase):
 def fixture(self,root):
  descriptor={'revision_id':'test-revision','model':{'sections':[{'id':'resident','source_index':5,'linked_vram':0x80010000}]}}
  bindings={'code':{},'evidence':{}};rows=[];support=[]
  for index,name in enumerate(OPERATIONS):
   ref={'revision_id':'test-revision','section':'resident','offset':index*16};bindings['code'][name]=ref;bindings['evidence'][name]={'original_body_sha256':str(index).zfill(64)}
   alias=index==5;symbol=f'fn_005_{index:04d}';row={'name':symbol,'section':5,'offset':index*16};(support if alias else rows).append(row)
   symbol+=('' if alias else '_recomp');path=root/('support' if alias else 'baseline')/(symbol+'.c');path.parent.mkdir(exist_ok=True)
   path.write_text('RECOMP_FUNC void '+symbol+'(uint8_t* rdram,recomp_context* ctx) {\n'+f'jfg_phase9_execution_probe_predecoded(0x5U, 0x{0x80010000+index*16:08x}U, 0x0U, ctx);\n}}\n')
  for filename,doc in [('game-descriptor.json',descriptor),('game-bindings.json',bindings)]: (root/filename).write_text(json.dumps(doc))
  doc=create(root,rows,support,descriptor,bindings)
  manifest={'game_descriptor_sha256':doc['descriptor_sha256'],'game_bindings_sha256':doc['bindings_sha256']}
  return descriptor,bindings,doc,manifest
 def seal(self,root,doc,manifest):
  raw=json.dumps(doc).encode();(root/'native-operations.json').write_bytes(raw);manifest['native_operations_sha256']=hashlib.sha256(raw).hexdigest()
 def test_interior_alias_is_selected_and_other_revision_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);d,b,doc,m=self.fixture(root);self.seal(root,doc,m);validate(root,m,d,b)
   self.assertTrue(doc['operations']['native.exception_entry']['source'].startswith('support/'))
   doc['revision_id']='another-revision';self.seal(root,doc,m)
   with self.assertRaisesRegex(ValueError,'corpus'):validate(root,m,d,b)
 def test_changed_source_or_entry_cannot_be_resealed_as_same_operation(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);d,b,doc,m=self.fixture(root);self.seal(root,doc,m)
   row=doc['operations'][OPERATIONS[0]];path=root/row['source'];path.write_text(path.read_text().replace('0x80010000U','0x80010004U'))
   with self.assertRaisesRegex(ValueError,'source digest'):validate(root,m,d,b)
   row['source_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();self.seal(root,doc,m)
   with self.assertRaisesRegex(ValueError,'first instruction'):validate(root,m,d,b)
 def test_owner_and_path_are_checked(self):
  for field,value in [('original_body_sha256','0'*63+'f'),('source','../outside.c'),('entry_pc',0x80020000)]:
   with self.subTest(field=field),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);d,b,doc,m=self.fixture(root);doc['operations'][OPERATIONS[0]][field]=value;self.seal(root,doc,m)
    with self.assertRaises(ValueError):validate(root,m,d,b)
if __name__=='__main__':unittest.main()
