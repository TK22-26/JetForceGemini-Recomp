"""Exercise incremental shader builds without RT64, a compiler, or a ROM."""
import argparse
from pathlib import Path
import subprocess
import tempfile
import time

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cmake", required=True)
    parser.add_argument("--generator", default="Ninja")
    parser.add_argument("--make-program")
    parser.add_argument("--work-root", type=Path, default=Path(__file__).resolve().parents[1] / "build/shader-tests")
    args = parser.parse_args()
    hook = (Path(__file__).resolve().parents[1] / "cmake/rt64_shader_dependencies.cmake").as_posix()
    # Keep MSBuild tracking inputs outside the OS temporary-file directory.
    args.work_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="deps-", dir=args.work_root.resolve()) as directory:
        root = Path(directory)
        source, build = root / "source", root / "build"
        dep = source / "dep"
        (dep / "src/shared").mkdir(parents=True)
        (dep / "src/shaders/nested").mkdir(parents=True)
        header = dep / "src/shared/layout.h"
        nested = dep / "src/shaders/nested/common.hlsli"
        header.write_text("layout-v1\n")
        nested.write_text("nested-v1\n")
        (dep / "src/shaders/test.hlsl").write_text("synthetic shader\n")
        (source / "CMakeLists.txt").write_text(
            'cmake_minimum_required(VERSION 3.20)\nproject(fixture NONE)\n'
            f'set(CMAKE_PROJECT_rt64_INCLUDE "{hook}")\nadd_subdirectory(dep)\n')
        (dep / "CMakeLists.txt").write_text(r"""
cmake_minimum_required(VERSION 3.20)
project(rt64 NONE)
set(products)
foreach(format IN ITEMS spirv dxil rw metal)
    set(stem "${CMAKE_BINARY_DIR}/test")
    if(format STREQUAL "spirv" OR format STREQUAL "metal")
        set(binary "${stem}.spv")
    else()
        set(binary "${stem}.${format}")
    endif()
    if(NOT format STREQUAL "metal")
        add_custom_command(OUTPUT "${binary}"
            COMMAND "${CMAKE_COMMAND}" -E copy
                "${CMAKE_CURRENT_SOURCE_DIR}/src/shaders/test.hlsl" "${binary}"
            DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/src/shaders/test.hlsl")
    endif()
    add_custom_command(OUTPUT "${stem}.${format}.c"
        COMMAND "${CMAKE_COMMAND}" -E copy "${binary}" "${stem}.${format}.c"
        DEPENDS "${binary}")
    list(APPEND products "${stem}.${format}.c")
endforeach()
add_custom_target(rt64 ALL DEPENDS ${products} SOURCES ${products})
""")
        configure = [args.cmake, "-S", str(source), "-B", str(build), "-G", args.generator]
        if args.make_program:
            configure.append("-DCMAKE_MAKE_PROGRAM=" + args.make_program)
        result = subprocess.run(configure, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        def run_build():
            result = subprocess.run([args.cmake, "--build", str(build), "--config", "Release"],
                                    capture_output=True, text=True)
            assert result.returncode == 0, result.stdout + result.stderr
            return {p.name: p.stat().st_mtime_ns for p in build.glob("test.*.c")}
        initial = run_build()
        assert len(initial) == 4, initial
        assert run_build() == initial, "unchanged build regenerated shader blobs"
        for changed, text in [(header, "layout-v2\n"), (nested, "nested-v2\n"),
                              (dep / "src/shared/added.h", "added\n")]:
            time.sleep(1.1)
            changed.write_text(text)
            rebuilt = run_build()
            assert all(rebuilt[k] > initial[k] for k in initial), (changed, initial, rebuilt)
            assert run_build() == rebuilt, "dependency fix caused perpetual rebuilds"
            initial = rebuilt
        print("Shader dependencies: shared, nested, added headers rebuild all formats; unchanged builds stay idle.")

if __name__ == "__main__":
    main()
