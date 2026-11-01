"""Complete private generation receipt shared by generation and Windows resume."""
from pathlib import Path
from scripts.regional.json_contract import loads
from scripts.native_program_identity import capture_tree,digest
from scripts.prepare_generated_sources import _load_manifest,_validate_normalizer_revision

FILES=("normalized/sources.json", "cpu-generation.json", "reconstruction.json", "audio/payloads.json", "audio/input.toml", "audio/program.bin", "audio/production-audio-adapter.cpp", "audio/brokered-rsp.hpp", "audio/brokered-jfg-audio-probe.cpp", "audio/jfg-audio-probe.cpp", "normalized/jfg_original_timing.h", "normalized/original-timing.json", "normalized/jfg_original_timing_fast.h", "normalized/funcs.h")

def capture(workspace):
    workspace=Path(workspace)
    return {'files':{name:digest(workspace/name) for name in FILES},'generated_files':capture_tree(workspace/'normalized')}

def verify(workspace,profile):
    workspace=Path(workspace);receipt=loads((workspace/'generation.json').read_bytes())
    if (receipt.get('schema_version'),receipt.get('kind'),receipt.get('complete'),receipt.get('revision_id'),receipt.get('rom_sha1'))!=(3,'jfg-regional-generation',True,profile.revision_id,profile.sha1):
        raise ValueError('Resume requires a completed shared generation for this exact ROM revision')
    current=capture(workspace)
    if any(receipt.get(k)!=v for k,v in current.items()):raise ValueError('Generated source or support input changed; regenerate in a fresh workspace')
    manifest=_load_manifest(workspace/'normalized/sources.json');_validate_normalizer_revision(manifest)
    if manifest['version']!=7 or (manifest['revision_id'],manifest['program_model_sha256'],manifest['generation_input_sha256'])!=(profile.revision_id,receipt['model_sha256'],receipt['generation_input_sha256']):
        raise ValueError('Generation receipt and CPU corpus disagree')
    from scripts.rom_profiles import identify_rom
    canonical=(workspace/'original-private.z64').read_bytes()
    if identify_rom(canonical)[0].revision_id!=profile.revision_id:raise ValueError('Canonical input copy changed')
    return receipt
