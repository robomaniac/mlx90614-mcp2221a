"""Build the Cython extension locally; Windows uses the venv's portable compiler."""
from pathlib import Path
import os
import platform
import shutil
import struct
import subprocess
import sys
import sysconfig


def main():
    root = Path(__file__).resolve().parent
    source = root / "mcp2221_native.pyx"
    build = root / ".native-build"
    output = root / ("mcp2221_native" + sysconfig.get_config_var("EXT_SUFFIX"))
    if output.exists() and output.stat().st_mtime >= max(source.stat().st_mtime, Path(__file__).stat().st_mtime):
        print("Native extension already built. Reuse this environment.")
        return
    build.mkdir(exist_ok=True)
    generated = build / "mcp2221_native.c"
    subprocess.run([sys.executable, "-m", "cython", "-3", str(source), "-o", str(generated)], check=True)
    include = Path(sysconfig.get_path("include"))
    if not (include / "Python.h").is_file():
        raise SystemExit("Python development headers are missing. Use a full CPython installation.")
    env = os.environ.copy()
    if sys.platform == "win32":
        if struct.calcsize("P") != 8 or platform.machine().lower() not in ("amd64", "x86_64"):
            raise SystemExit("This Windows demo requires x64 CPython.")
        library = Path(sys.base_prefix) / "libs" / f"python{sys.version_info.major}{sys.version_info.minor}.lib"
        if not library.is_file():
            raise SystemExit("Python import library is missing. Use a full x64 CPython installation.")
        env["ZIG_GLOBAL_CACHE_DIR"] = str(build / "zig-global")
        env["ZIG_LOCAL_CACHE_DIR"] = str(build / "zig-local")
        # CPython's Windows pointer-size configuration needs this macro with a GNU compiler.
        command = [sys.executable, "-m", "ziglang", "cc", "-target", "x86_64-windows-gnu",
                   "-shared", "-O2", "-DNDEBUG", "-DMS_WIN64", "-I", str(include), str(generated), str(library), "-o", str(output)]
    else:
        compiler = shutil.which("cc")
        if not compiler:
            raise SystemExit("Install a C compiler and Python development headers before building.")
        command = [compiler, "-shared", "-fPIC", "-O2", "-I", str(include), str(generated), "-o", str(output)]
        if sys.platform == "darwin":
            command.extend(["-undefined", "dynamic_lookup"])
    subprocess.run(command, check=True, env=env, cwd=root)
    subprocess.run([sys.executable, "-c", "import mcp2221_native; print('Native extension import: PASS')"],
                   check=True, cwd=root)
    print("Build complete. Run demo.py --simulate or demo.py --list.")


if __name__ == "__main__":
    main()
