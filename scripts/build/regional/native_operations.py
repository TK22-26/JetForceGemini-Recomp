"""Select private native variants by qualified semantic operation and corpus."""
from pathlib import Path
import hashlib,json,re
from scripts.regional.json_contract import loads
OPERATIONS=("overlay.collision.accessor","native.collision_split","native.collision_line",
 "overlay.shadows.filter","sdk.osWritebackDCacheAll","native.exception_entry",
 "native.sp_status_set","native.sp_pc_set","native.sp_dma","native.sp_busy",
 "native.sp_status_get","os.scheduler_park","sdk.__osDispatchThread","game.Arctanf","game.mathDiffAngle","game.Sinf","game.Cosf")
def digest(raw):return hashlib.sha256(raw).hexdigest()
def create(root,authoritative,support,descriptor,bindings):
 sections={s['id']:s for s in descriptor['model']['sections']}
 rows={}
 for group,is_body in ((authoritative,True),(support,False)):
  for row in group:
   symbol=str(row['name'])+('_recomp' if is_body else '')
   rows[(int(row['section']),int(row['offset']))]=(symbol,('baseline/' if is_body else 'support/')+symbol+'.c')
 operations={}
 for name in OPERATIONS:
  ref=bindings['code'][name];section=sections[ref['section']]
  symbol,path=rows[(section['source_index'],ref['offset'])]
  raw=(root/path).read_bytes()
  operations[name]={'reference':ref,'source':path,'symbol':symbol,
   'entry_pc':section['linked_vram']+ref['offset'],'source_sha256':digest(raw),
   'original_body_sha256':bindings['evidence'][name]['original_body_sha256']}
 return {'schema_version':1,'revision_id':descriptor['revision_id'],
  'descriptor_sha256':digest((root/'game-descriptor.json').read_bytes()),
  'bindings_sha256':digest((root/'game-bindings.json').read_bytes()),'operations':operations}
def validate(root,manifest,descriptor,bindings):
 raw=(root/'native-operations.json').read_bytes()
 if digest(raw)!=manifest['native_operations_sha256']:raise ValueError('Native operations digest differs')
 doc=loads(raw)
 if set(doc)!={'schema_version','revision_id','descriptor_sha256','bindings_sha256','operations'} or doc['schema_version']!=1 or doc['revision_id']!=descriptor['revision_id'] or doc['descriptor_sha256']!=manifest['game_descriptor_sha256'] or doc['bindings_sha256']!=manifest['game_bindings_sha256'] or set(doc['operations'])!=set(OPERATIONS):raise ValueError('Native operations corpus differs')
 sections={s['id']:s for s in descriptor['model']['sections']}
 for name,row in doc['operations'].items():
  ref=bindings['code'][name]
  if set(row)!={'reference','source','symbol','entry_pc','source_sha256','original_body_sha256'} or row['reference']!=ref or row['entry_pc']!=sections[ref['section']]['linked_vram']+ref['offset'] or row['original_body_sha256']!=bindings['evidence'][name]['original_body_sha256']:raise ValueError('Native operation owner differs: '+name)
  if not re.fullmatch(r'(?:baseline/fn_[0-9]{3}_[0-9]{4}_recomp|support/fn_[0-9]{3}_[0-9]{4})\.c',row['source']) or Path(row['source']).stem!=row['symbol']:raise ValueError('Native operation source path differs')
  source=(root/row['source']).read_bytes()
  if digest(source)!=row['source_sha256']:raise ValueError('Native operation source digest differs: '+name)
  text=source.decode('utf-8')
  if text.count('RECOMP_FUNC void '+row['symbol']+'(')!=1:raise ValueError('Native operation entry differs')
  probes=re.findall(r'jfg_phase9_execution_probe_predecoded\(0x[0-9a-f]+U, 0x([0-9a-f]+)U,',text,re.I)
  if not probes or int(probes[0],16)!=row['entry_pc']:raise ValueError('Native operation first instruction differs')
 return doc
def load(root):
 from scripts.prepare_generated_sources import _load_manifest,_validate_normalizer_revision
 from scripts.regional.bindings import validate_document
 root=Path(root).resolve();manifest=_load_manifest(root/'sources.json');_validate_normalizer_revision(manifest)
 if manifest['version']!=7:raise ValueError('Native operation requires regional corpus')
 docs=[]
 for key in ('game_descriptor','game_bindings'):
  raw=(root/manifest[key]).read_bytes()
  if digest(raw)!=manifest[key+'_sha256']:raise ValueError('Native operation binding digest differs')
  docs.append(loads(raw))
 descriptor,bindings=docs;validate_document(bindings,descriptor)
 return validate(root,manifest,descriptor,bindings),bindings,descriptor
def source(root,operations,name):
 row=operations['operations'][name]
 return (root/row['source']).read_text(encoding='utf-8'),row
