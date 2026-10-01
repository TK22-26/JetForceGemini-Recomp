#!/usr/bin/env bash
set -euo pipefail

host_root=$1
run_root="$host_root/tools/results/phase4/v3-corrected-linux-gcc"
mkdir -p "$run_root"
tmp_root=$(mktemp -d -p /tmp jfg-v3-gcc.XXXXXX)
repo="$tmp_root/repo"
private_root="$tmp_root/private-normalized"
mkdir -p "$repo"
printf '%s\n' "$tmp_root" > "$run_root/temp-root.txt"
rsync -a --exclude='.git' --exclude='tools' "$host_root/" "$repo/"
cp -a \
  "$host_root/tools/results/phase4/generation-replay-real-final/normalized" \
  "$private_root"
cmake -S "$repo" -B "$tmp_root/build" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=/usr/bin/gcc \
  -DCMAKE_CXX_COMPILER=/usr/bin/g++ \
  -DJFG_ENABLE_GENERATED_CODE=ON \
  -DJFG_BUILD_G2_PRODUCERS=ON \
  -DJFG_BUILD_TESTS=OFF \
  -DJFG_BUILD_SYNTHETIC_GENERATED_TESTS=OFF \
  -DJFG_GENERATED_ROOT="$private_root" \
  -DJFG_G2_PRIVATE_AUDIO_ADAPTER_ROOT="$host_root/tools/results/phase4/private-audio-g2" \
  -DJFG_G2_PRIVATE_AUDIO_ORACLE_ROOT="$host_root/tools/results/phase4/g2-production-audio-oracle-v2" \
  -DJFG_G2_PRIVATE_AUDIO_RUNTIME_INCLUDE="$host_root/tools/upstream/N64ModernRuntime/librecomp/include" \
  -DJFG_G2_PRIVATE_GRAPHICS_ADAPTER_ROOT="$host_root/tools/results/phase4/g2-production-graphics-rt64-v2" \
  -DJFG_G2_PRIVATE_GRAPHICS_ORACLE_ROOT="$host_root/tools/results/phase4/g2-production-graphics-oracle-v2" \
  -DJFG_G2_PRIVATE_RT64_ROOT="$host_root/tools/upstream/rt64" \
  2>&1 | tee "$run_root/configure.log"
cmake --build "$tmp_root/build" --target jfg_g2_overlay_producer --parallel 8 \
  2>&1 | tee "$run_root/build.log"
cp "$tmp_root/build/jfg_g2_overlay_producer" "$run_root/jfg_g2_overlay_producer"
printf 'corrected-tree-gcc-build=passed\n' > "$run_root/result.txt"
