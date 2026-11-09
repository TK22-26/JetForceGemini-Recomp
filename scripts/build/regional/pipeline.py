"""Shared CPU generation stages for every exact revision; no native admission."""
from pathlib import Path
from dataclasses import asdict
from argparse import Namespace
import hashlib,json,subprocess,tomllib
from scripts.rom_profiles import identify_rom
from scripts.validate_elf import parse_sections,parse_symbols
from scripts.prepare_n64recomp_context_dump import build_context_dump_config
from scripts.regional.elf_metadata import qualify as qualify_elf
from scripts.regional.context_model import from_context
from scripts.regional.linker_layout import derive_layout
from scripts.regional.symbol_inventory import reconcile
from scripts.regional.relocation_inventory import derive
from scripts.regional.exception_bindings import qualify as qualify_exceptions
from scripts.regional.generation_input import prepare as prepare_input
from scripts.regional.runtime_manifest import emit
from scripts.regional.normalization import normalize
from scripts.transform_private_n64recomp_inputs import parse_headers
from scripts.prepare_generated_sources import prepare as prepare_sources

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def prove_original_sections(rom,model,elf,elf_sections):
    image=Path(elf).read_bytes()
    for section in model.sections:
        name='.overlay_'+str(section.overlay_slot) if section.overlay_slot is not None else '.'+section.id
        matches=[s for s in elf_sections if s.name==name and s.allocated and s.section_type!='NOBITS']
        if len(matches)!=1 or matches[0].address!=section.linked_vram or matches[0].size<section.initialized_size:raise ValueError('Original ELF section ownership differs from the program model')
        candidate=matches[0];size=section.initialized_size
        if candidate.offset+size>len(image) or image[candidate.offset:candidate.offset+size]!=rom[section.rom_start:section.rom_start+size]:raise ValueError('Original ELF loaded section bytes differ from the selected ROM')

def generate_cpu(rom,elf,linker_map,recompiler,recomp_header,workspace,run):
    """Caller owns pinned tool construction; this stage records actual inputs.

    `run(name, argv, cwd)` must raise on failure and retain a private log. It
    executes inside the caller's existing supervision, never a detached job.
    """
    profile,_,_=identify_rom(rom);workspace=Path(workspace);elf=Path(elf);linker_map=Path(linker_map);recompiler=Path(recompiler);recomp_header=Path(recomp_header)
    for name in ('metadata','context','program','normalized','prepared-cpu','cpu-generation.json'):
        if (workspace/name).exists():raise ValueError('CPU generation requires fresh stage outputs')
    inputs={'source_elf_sha256':sha(elf),'linker_map_sha256':sha(linker_map),'compiler_sha256':sha(recompiler),'compiler_header_sha256':sha(recomp_header)}
    qualified,recovery=qualify_elf(rom,elf,workspace/'metadata')
    context=workspace/'context';context.mkdir();configuration,context_counts=build_context_dump_config(qualified,context/'unused')
    (context/'input.toml').write_text(configuration,encoding='utf-8');run('context-dump',[str(recompiler),str(context/'input.toml'),'--dump-context'],context)
    code=tomllib.loads((context/'dump.toml').read_text());data=tomllib.loads((context/'data_dump.toml').read_text());map_text=linker_map.read_text()
    layout=derive_layout(rom,map_text,code);model=from_context(rom,sha(qualified),code,data,map_text,parse_headers(rom,layout),layout)
    sections=parse_sections(subprocess.check_output(['mips-linux-gnu-readelf','-SW',str(qualified)],text=True,timeout=60));symbols=parse_symbols(subprocess.check_output(['mips-linux-gnu-readelf','-sW',str(qualified)],text=True,timeout=60))
    model,counts=reconcile(model,sections,symbols);prove_original_sections(rom,model,qualified,sections)
    inventory=derive(rom,model,layout);exceptions=qualify_exceptions(rom,model,inventory);program=workspace/'program'
    contract=prepare_input(rom,model,layout,exceptions,sections,symbols,program);emit(program,sections,symbols)
    run('generate-cpu',[str(recompiler),str(program/'recompile-private.toml')],program)
    normalized=workspace/'normalized';normalization=normalize(Namespace(program_input=program/'input-manifest.json',raw_generated=program/'generated',symbols=program/'symbols-private.toml',original_context=None,runtime_manifest=program/'runtime-link-private.json',recomp_header=recomp_header,output=normalized))
    prepare_sources(normalized,workspace/'prepared-cpu',require_normalizer_revision=True)
    after={'source_elf_sha256':sha(elf),'linker_map_sha256':sha(linker_map),'compiler_sha256':sha(recompiler),'compiler_header_sha256':sha(recomp_header)}
    if after!=inputs:raise ValueError('Generation source or compiler inputs changed during the stage')
    result={'schema_version':1,'kind':'jfg-regional-cpu-generation','complete':True,'scope':'CPU generation only; native gameplay not qualified','revision_id':profile.revision_id,'rom_sha1':profile.sha1,'model_sha256':model.fingerprint(),'generation_input_sha256':sha(program/'input-manifest.json'),'generated_manifest_sha256':sha(normalized/'sources.json'),'inputs':inputs,'metadata_qualification_sha256':sha(workspace/'metadata/qualification.json'),'counts':counts,'context_counts':context_counts,'normalization':normalization,'original_sections_verified':len(model.sections)}
    (workspace/'cpu-generation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return model,result
