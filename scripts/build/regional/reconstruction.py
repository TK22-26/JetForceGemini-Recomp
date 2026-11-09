"""One exact-ROM reconstruction owner with explicit pinned extraction recipes."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess,sys
from scripts.rom_profiles import identify_rom,PAL_ROM,JAPAN_ROM
from scripts.regional_overlays import expand_regional_overlays

ROOT=Path(__file__).resolve().parents[3]
def regional_splat(text: str, region: str) -> str:
    profiles = {"pal": PAL_ROM, "jpn": JAPAN_ROM}
    if region not in profiles or "sha1: " + profiles[region].sha1 not in text:
        raise ValueError("Regional metadata does not match the pinned ROM profile.")
    # Retain original instructions directly. The pinned regional C headers are incomplete.
    text = re.sub(r"(\[0x[0-9A-Fa-f]+, )c(,)", r"\1asm\2", text)
    if region == "jpn":
        marker = "[0x9E4D0, bin]"
        if text.count(marker) != 1:
            raise ValueError("Unexpected Japanese executable-prefix metadata.")
        # BIN is emitted in DATA; TEXTBIN preserves its order before the audio ucode.
        text = text.replace(marker, "[0x9E4D0, textbin]")
    return text


def pal_linker_symbols(text: str) -> str:
    # The basic PAL map contains five unused shared aliases. Some boundaries are
    # recovered below; the asset lookup table still has no independently verified
    # extent, so retain the qualified removal of all five unused aliases.
    boundaries = ("overlay_1_ROM_START", "assets_lut_ROM_START", "assets_lut_ROM_END",
                  "symbolsTable_offsets_ROM_START", "symbolsTable_symbol_names_ROM_START")
    lines = text.splitlines()
    removed = [line for line in lines if any(name in line for name in boundaries)]
    if len(removed) != 5:
        raise ValueError("Unexpected PAL shared linker aliases.")
    return "\n".join(line for line in lines if line not in removed) + "\n"


def reconstruct(rom,source,destination,jobs,run):
    profile,_,_=identify_rom(rom);source=Path(source).resolve(strict=True);destination=Path(destination)
    if destination.exists() or any(ch.isspace() for ch in str(destination)) or type(jobs) is not int or not 1<=jobs<=32:raise ValueError('Reconstruction needs a fresh space-free private workspace and 1..32 jobs')
    lock=json.loads((ROOT/'dependencies.lock.json').read_text());pin=next(v['commit'] for v in lock['repositories'] if v['id']=='jfg-decomp')
    if subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()!=pin:raise ValueError('Original reconstruction source does not match the dependency pin')
    run('clone-metadata',['git','clone','--no-hardlinks',str(source),str(destination)],destination.parent)
    run('decomp-submodules',['git','submodule','update','--init','--recursive'],destination)
    (destination/'baseroms').mkdir(exist_ok=True);(destination/'baseroms'/('baserom.'+profile.code+'.z64')).write_bytes(rom)
    if profile.code in ('pal','jpn'):
        yaml=destination/'ver/splat'/('jfg.'+profile.code+'.yaml');yaml.write_text(expand_regional_overlays(regional_splat(yaml.read_text(),profile.code),rom,profile.code))
        if profile.code=='pal':
            symbols=destination/'ver/symbols/undefined_syms.txt';symbols.write_text(pal_linker_symbols(symbols.read_text()))
    run('python-environment',[sys.executable,'-m','venv',str(destination/'.venv')],destination)
    run('python-dependencies',[str(destination/'.venv/bin/python3'),'-m','pip','install','-r',str(destination/'requirements.txt')],destination)
    cache_ready=all((source/item).exists() for item in ('tools/ido-recomp/linux/cc','tools/n64crc','tools/objdiff/objdiff-cli'))
    if cache_ready:
        for item in ('ido-recomp','objdiff'):shutil.copytree(source/'tools'/item,destination/'tools'/item)
        shutil.copy2(source/'tools/n64crc',destination/'tools/n64crc')
    else:run('setup-metadata-tools',['make','-C','tools'],destination)
    run('extract-rom',['make','extract','VERSION='+profile.code,'COLOR=0'],destination)
    command=['make','-j'+str(jobs),'VERSION='+profile.code,'COLOR=0']
    if profile.code in ('pal','jpn'):
        src='src_'+profile.code;command+=['LIBULTRA_SRC_DIRS=','HASM_DIRS='+' '.join((src,src+'/hasm',src+'/hasm/ido'))]
    run('matching-elf',command,destination)
    directory=destination/('build' if profile.code=='us' else 'build_'+profile.code);rebuilt=directory/('jfg.'+profile.code+'.z64')
    if rebuilt.read_bytes()!=rom:raise ValueError('Original reconstruction is not byte-for-byte identical')
    elf=rebuilt.with_suffix('.elf');linker_map=rebuilt.with_suffix('.map')
    result={'schema_version':1,'kind':'jfg-original-reconstruction','revision_id':profile.revision_id,'rom_sha1':profile.sha1,'decomp_commit':pin,'extraction_recipe':profile.extraction_recipe,'matching_rom':True,'elf_sha256':hashlib.sha256(elf.read_bytes()).hexdigest(),'map_sha256':hashlib.sha256(linker_map.read_bytes()).hexdigest(),'tool_cache_reused':cache_ready,'native_playable':False}
    return elf,linker_map,result
