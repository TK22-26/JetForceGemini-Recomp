"""Qualify original ELF code metadata without changing any loaded section bytes.

The reviewed catalog describes missing boundaries and non-CPU payloads. It is
not an address map: every recovery span is anchored by a known original body
and exact original hashes. Inputs and generated metadata remain private.
"""
from pathlib import Path
import hashlib,json,struct,subprocess
from scripts.rom_profiles import identify_rom,PROFILES_BY_ID
from scripts.validate_elf import parse_header,parse_sections,parse_symbols
from scripts.regional.json_contract import loads

ROOT=Path(__file__).resolve().parents[3]
RECIPES=ROOT/'config/roms/elf-metadata.json'
def sha(data):return hashlib.sha256(data).hexdigest()
def inspect(path,option):
    return subprocess.check_output(['mips-linux-gnu-readelf',option,str(path)],text=True,timeout=60)

def edit_symbols(original,edits):
    """Change only explicitly expected ELF32 symbol fields; reject stale inputs."""
    data=bytearray(original)
    if len(data)<52 or data[:7]!=b'\x7fELF\x01\x02\x01':raise ValueError('Expected ELF32 big-endian metadata')
    offset=struct.unpack_from('>I',data,32)[0];stride,count=struct.unpack_from('>HH',data,46)
    if stride!=40 or not count or offset+stride*count>len(data):raise ValueError('ELF section headers are truncated')
    sections=[struct.unpack_from('>10I',data,offset+i*stride) for i in range(count)];changed=set()
    for section in sections:
        if section[1]!=2:continue
        if section[9]!=16 or section[5]%16 or section[4]+section[5]>len(data) or section[6]>=count:raise ValueError('Invalid ELF symbol table')
        strings=sections[section[6]]
        if strings[1]!=3 or strings[4]+strings[5]>len(data):raise ValueError('Invalid ELF string table')
        names=data[strings[4]:strings[4]+strings[5]]
        for at in range(section[4],section[4]+section[5],16):
            index,value,size,info,other,owner=struct.unpack_from('>IIIBBH',data,at)
            if index>=len(names):raise ValueError('Invalid ELF symbol name offset')
            end=names.find(0,index)
            if end<0:raise ValueError('Unterminated ELF symbol name')
            name=names[index:end].decode('utf-8')
            if name not in edits:continue
            expected,replacement=edits[name]
            if name in changed or (value,size,info&15,owner)!=tuple(expected):raise ValueError('ELF symbol no longer matches its qualification: '+name)
            if len(replacement)!=4 or any(type(v) is not int or v<0 for v in replacement):raise ValueError('Invalid symbol edit')
            value,size,kind,owner=replacement
            if value>0xffffffff or size>0xffffffff or kind>15 or owner>65535:raise ValueError('Symbol edit overflows ELF32')
            struct.pack_into('>IIIBBH',data,at,index,value,size,(info&0xf0)|kind,other,owner);changed.add(name)
    if changed!=set(edits):raise ValueError('A qualified ELF symbol was not found')
    return bytes(data)

def prove_loaded_bytes(before,before_sections,after,after_sections):
    metadata=lambda rows:[(s.name,s.section_type,s.address,s.size,s.flags) for s in rows if s.allocated]
    if metadata(before_sections)!=metadata(after_sections):raise ValueError('Allocated section metadata changed')
    for left,right in zip([s for s in before_sections if s.allocated],[s for s in after_sections if s.allocated]):
        if left.section_type=='NOBITS':continue
        if left.offset+left.size>len(before) or right.offset+right.size>len(after) or before[left.offset:left.offset+left.size]!=after[right.offset:right.offset+right.size]:raise ValueError('Loaded ELF bytes changed')

def qualify_body_alias_groups(groups, functions, payload, section_index):
    """Coalesce proven split metadata into one body with zero-size entry aliases.

    Every source symbol extent and byte hash must match. Loaded instructions are
    never modified, and symbols outside the explicitly covered group reject it.
    """
    edits = {}; records = []; spans = []
    for group in groups:
        if set(group) != {"body_symbol", "span_size", "span_sha256", "members"}:
            raise ValueError("Invalid shared-body metadata group")
        members = group["members"]
        if not isinstance(members, list) or len(members) < 2:
            raise ValueError("Shared body needs explicit source members")
        matched = []; end_offset = 0; start = None
        for row in members:
            if set(row) != {"symbol", "offset", "size", "sha256"} or any(type(row[k]) is not int or row[k] < 0 or row[k] % 4 for k in ("offset", "size")) or not row["size"] or row["offset"] != end_offset:
                raise ValueError("Shared body members must cover a contiguous aligned span")
            found = [symbol for symbol in functions if symbol.name == row["symbol"] and symbol.size == row["size"]]
            if len(found) != 1:
                raise ValueError("Shared body source symbol is absent or ambiguous")
            symbol = found[0]
            if start is None: start = symbol.value
            if symbol.value != start + row["offset"] or sha(payload(symbol.value, symbol.size)) != row["sha256"]:
                raise ValueError("Shared body member differs from original proof")
            matched.append(symbol); end_offset += symbol.size
        if members[0]["symbol"] != group["body_symbol"] or type(group["span_size"]) is not int or group["span_size"] != end_offset or sha(payload(start, end_offset)) != group["span_sha256"]:
            raise ValueError("Shared body full span differs from proof")
        end = start + end_offset
        if any(a < end and start < b for a, b in spans):
            raise ValueError("Shared body groups overlap")
        if any(symbol not in matched and symbol.value < end and start < symbol.value + max(1, symbol.size) for symbol in functions):
            raise ValueError("Shared body overlaps an unclassified executable symbol")
        spans.append((start, end))
        for index, symbol in enumerate(matched):
            if symbol.name in edits: raise ValueError("Repeated shared body symbol")
            edits[symbol.name] = ([symbol.value, symbol.size, 2, section_index],
                                  [symbol.value, end_offset if index == 0 else 0, 2, section_index])
        records.append({"body_symbol": group["body_symbol"], "size": end_offset,
                        "sha256": group["span_sha256"], "aliases": [row["symbol"] for row in members[1:]]})
    return edits, records


def qualify(rom,elf,output,*,recipes_path=RECIPES):
    profile,_,_=identify_rom(rom);elf=Path(elf).resolve(strict=True);output=Path(output).resolve()
    if output.exists():raise ValueError('Metadata output must be new')
    recipes=loads(Path(recipes_path).read_bytes())
    if set(recipes)!={'schema_version','kind','qualification','revisions'} or type(recipes['schema_version']) is not int or recipes['schema_version']!=2 or recipes['kind']!='jfg-qualified-elf-metadata-recipes' or set(recipes['revisions'])!=set(PROFILES_BY_ID):raise ValueError('Unknown ELF metadata recipe catalog')
    recipe=recipes['revisions'][profile.revision_id]
    if set(recipe)!={'recover_groups','non_cpu_payloads','absolute_entry','body_alias_groups'}:raise ValueError('Incomplete ELF metadata recipe')
    original=elf.read_bytes();header=parse_header(inspect(elf,'-h'))
    if tuple(header.get(k) for k in ('class','endianness','machine','type'))!=('ELF32','big','MIPS','EXEC'):raise ValueError('Wrong original ELF format')
    sections=parse_sections(inspect(elf,'-SW'));symbols=parse_symbols(inspect(elf,'-sW'))
    mains=[s for s in sections if s.name=='.main' and 'X' in s.flags]
    if len(mains)!=1:raise ValueError('Original ELF has no unique resident section')
    main=mains[0];rom_starts=[s.value for s in symbols if s.name=='main_ROM_START' and s.defined]
    if len(rom_starts)!=1:raise ValueError('Original ELF has no unique resident ROM coordinate')
    rom_start=rom_starts[0]
    if main.offset+main.size>len(original) or rom_start+main.size>len(rom) or original[main.offset:main.offset+main.size]!=rom[rom_start:rom_start+main.size]:raise ValueError('Original ELF resident bytes do not match the selected ROM')
    def payload(address,size):
        if type(address) is not int or type(size) is not int or size<=0 or address<main.address or address+size>main.address+main.size:raise ValueError('Metadata span leaves resident image')
        return original[main.offset+address-main.address:main.offset+address-main.address+size]
    functions=[s for s in symbols if s.symbol_type=='FUNC' and s.section==str(main.index)];edits,shared_bodies=qualify_body_alias_groups(recipe['body_alias_groups'],functions,payload,main.index);additions=[];ranges=[];recovered=[]
    for group in recipe['recover_groups']:
        if set(group)!={'name','following_symbol','following_size','following_sha256','span_size','span_sha256','bodies'}:raise ValueError('Invalid metadata recovery group')
        anchors=[s for s in functions if s.name==group['following_symbol'] and s.size==group['following_size']]
        if len(anchors)!=1 or sha(payload(anchors[0].value,anchors[0].size))!=group['following_sha256']:raise ValueError('Original following body does not match recovery proof')
        end=anchors[0].value;start=end-group['span_size'];span=payload(start,group['span_size'])
        if start%4 or len(span)%4 or sha(span)!=group['span_sha256']:raise ValueError('Original recovery span differs')
        if any(s.value<end and s.value+max(1,s.size)>start for s in functions):raise ValueError('Recovery overlaps existing CPU function metadata')
        covered=bytearray(len(span))
        for body in group['bodies']:
            if set(body)!={'name','offset','size','body_sha256'} or any(type(body[k]) is not int or body[k]<0 or body[k]%4 for k in ('offset','size')) or body['size']==0 or body['offset']+body['size']>len(span):raise ValueError('Invalid recovered boundary')
            a=body['offset'];b=a+body['size'];name=body['name'];address=start+a
            if not isinstance(name,str) or not name or any(s.name==name for s in symbols) or name in edits or any(covered[a:b]):raise ValueError('Duplicate/overlapping recovered function')
            if sha(span[a:b])!=body['body_sha256']:raise ValueError('Recovered body hash differs')
            covered[a:b]=b'\x01'*body['size'];ranges.append((address,address+body['size']));additions.append((name,address-main.address));edits[name]=([address,0,2,main.index],[address,body['size'],2,main.index]);recovered.append({'name':name,'size':body['size'],'sha256':body['body_sha256']})
        if any(byte and not covered[i] for i,byte in enumerate(span)):raise ValueError('Recovery leaves nonzero bytes unclassified')
    ranges.sort()
    if any(a[1]>b[0] for a,b in zip(ranges,ranges[1:])):raise ValueError('Recovery groups overlap')
    classified=[]
    for row in recipe['non_cpu_payloads']:
        if set(row)!={'size','sha256'}:raise ValueError('Invalid non-CPU payload recipe')
        candidates=[s for s in functions if s.size==row['size'] and sha(payload(s.value,s.size))==row['sha256']]
        if len(candidates)!=1:raise ValueError('Non-CPU payload has no unique original symbol')
        s=candidates[0]
        if s.name in edits:raise ValueError('Duplicate payload classification')
        edits[s.name]=([s.value,s.size,2,main.index],[s.value,s.size,1,main.index]);classified.append(row)
    entry=recipe['absolute_entry']
    if entry is not None:
        if set(entry)!={'symbol','size','sha256'}:raise ValueError('Invalid cartridge entry metadata recipe')
        rows=[s for s in symbols if s.name==entry['symbol'] and s.section=='ABS' and s.symbol_type=='FUNC' and s.value==int.from_bytes(rom[8:12],'big') and s.size==entry['size']]
        if len(rows)!=1 or sha(payload(rows[0].value,rows[0].size))!=entry['sha256']:raise ValueError('Original cartridge entry differs')
        s=rows[0];edits[s.name]=([s.value,s.size,2,65521],[s.value,s.size,2,main.index])
    output.mkdir(parents=True);temporary=output/'symbols-added.elf';target=output/'qualified.elf';command=['mips-linux-gnu-objcopy']
    for name,offset in additions:command+=['--add-symbol',name+'=.main:'+hex(offset)+',global,function']
    subprocess.run(command+[str(elf),str(temporary)],check=True,timeout=60)
    target.write_bytes(edit_symbols(temporary.read_bytes(),edits));modified=target.read_bytes()
    prove_loaded_bytes(original,sections,modified,parse_sections(inspect(target,'-SW')))
    if elf.read_bytes()!=original:raise ValueError('Original ELF changed during qualification')
    result={'schema_version':1,'kind':'jfg-qualified-elf-metadata','revision_id':profile.revision_id,'rom_sha1':profile.sha1,'source_elf_sha256':sha(original),'output_elf_sha256':sha(modified),'recipes_sha256':sha(Path(recipes_path).read_bytes()),'recovered_bodies':recovered,'shared_bodies':shared_bodies,'non_cpu_payloads':classified,'entry_owned':entry is not None,'loaded_sections_unchanged':True,'source_unchanged':True,'acceptance':False}
    (output/'qualification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return target,result
