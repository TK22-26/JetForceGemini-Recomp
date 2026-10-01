#!/bin/sh
# Build a private synthetic CPU probe ROM using only the user's locally dumped
# N64 boot header/bootcode. Never commit or distribute the generated ROM.
set -eu

if [ "$#" -lt 3 ] || [ "$#" -gt 4 ]; then
  echo 'usage: phase9_cpu_rounding_build.sh ROM EXPECTED_SHA256 TAG [rounding|clock|queue|queue_threads|translation|cache|mask|rsp|vi|branch|links|eret|interrupt|dma]' >&2
  exit 2
fi
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
repo=$(CDPATH= cd -- "$script_dir/.." && pwd -P)
rom=$(realpath -- "$1")
expected=$2
tag=$3
probe=${4:-rounding}
case "$probe" in
  rounding|clock|queue|queue_threads|translation|cache|mask|rsp|vi|branch|links|eret|interrupt|interrupt_mask|dma|vi_manager|vi_phase|pi_timing|pi_word|pi_short|pi_bytes|pi_half|compare|si_overlap|flash|ai|ai_fifo) ;;
  *) echo 'invalid CPU probe kind' >&2; exit 2 ;;
esac
case "$tag" in
  ''|*[!A-Za-z0-9_-]*) echo 'invalid private output tag' >&2; exit 2 ;;
esac
case "$expected" in
  *[!a-f0-9]*|'') echo 'invalid expected SHA-256' >&2; exit 2 ;;
esac
if [ "${#expected}" -ne 64 ]; then
  echo 'expected SHA-256 must have 64 hex characters' >&2
  exit 2
fi
actual=$(sha256sum "$rom" | cut -d' ' -f1)
if [ "$actual" != "$expected" ]; then
  echo 'private source ROM SHA-256 mismatch' >&2
  exit 2
fi
output="$repo/tools/private/cpu-$probe-$tag"
if [ -e "$output" ]; then
  echo 'private output already exists' >&2
  exit 2
fi
mkdir -- "$output"
mips-linux-gnu-as -EB -mips3 -o "$output/payload.o" \
  "$script_dir/phase9_cpu_${probe}_micro.S"
mips-linux-gnu-ld -Ttext=0x80000400 -e _start \
  -o "$output/payload.elf" "$output/payload.o"
mips-linux-gnu-objcopy -O binary -j .text \
  "$output/payload.elf" "$output/payload.bin"
if [ "$(stat -c %s "$output/payload.bin")" -gt 4096 ]; then
  echo 'synthetic payload exceeds one ROM code page' >&2
  exit 2
fi
pages=1
if [ "$probe" = queue ] || [ "$probe" = queue_threads ] || [ "$probe" = translation ] || [ "$probe" = cache ] || [ "$probe" = mask ] || [ "$probe" = rsp ] || [ "$probe" = interrupt ] || [ "$probe" = interrupt_mask ] || [ "$probe" = vi_manager ]; then
  # Keep the original static routines for this private OS-call experiment.
  # Their instructions/data remain local and are never a distributed test.
  pages=512
fi
dd if="$rom" of="$output/cpu-$probe.n64" bs=4096 count="$pages" status=none
truncate -s 2097152 "$output/cpu-$probe.n64"
dd if="$output/payload.bin" of="$output/cpu-$probe.n64" \
  bs=1 seek=4096 conv=notrunc status=none
"$repo/tools/upstream/Jet-Force-Gemini/tools/n64crc" \
  "$output/cpu-$probe.n64"
echo "source_rom_sha256=$actual"
echo "payload_sha256=$(sha256sum "$output/payload.bin" | cut -d' ' -f1)"
echo "test_rom_sha256=$(sha256sum "$output/cpu-$probe.n64" | cut -d' ' -f1)"
echo "private_output=$output"
