#!/usr/bin/env python3
import argparse
import glob
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def die(message: str, exit_code: int = 1) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(exit_code)


def tcl_brace(value: str) -> str:
    """
    Quote a value for Tcl using braces.
    This is sufficient for normal filesystem paths and cell names.
    """
    return "{" + value.replace("\\", "\\\\").replace("}", "\\}") + "}"


def slug(value: str) -> str:
    """
    Make a filesystem-friendly tag.
    """
    value = str(value)
    value = value.replace(".", "p")
    value = value.replace("-", "m")
    value = value.replace("+", "")
    value = value.replace("/", "_")
    value = re.sub(r"[^A-Za-z0-9_]+", "_", value)
    return value.strip("_")


def resolve_magic_rc(pdk_root: str, pdk: str) -> Path:
    """
    Resolve the Magic rcfile from PDK_ROOT and PDK.

    Expected Open PDKs layout:
      $PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc
    """
    pdk_root_path = Path(pdk_root).expanduser().resolve()

    candidates = [
        pdk_root_path / pdk / "libs.tech" / "magic" / f"{pdk}.magicrc",
        # Fallback for cases where PDK_ROOT already points directly at the PDK dir.
        pdk_root_path / "libs.tech" / "magic" / f"{pdk}.magicrc",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    searched = "\n  ".join(str(c) for c in candidates)
    die(f"Could not find Magic rcfile. Searched:\n  {searched}")


def find_magic_binary() -> str:
    if os.path.exists("/usr/local/bin/magic"):
        return "/usr/local/bin/magic"
    return "magic"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract parasitic SPICE from a GDS using Magic."
    )

    parser.add_argument(
        "gds_file",
        help="Input GDS file.",
    )

    parser.add_argument(
        "--pdk-root",
        default=os.environ.get("PDK_ROOT"),
        help="PDK root directory. Defaults to $PDK_ROOT.",
    )

    parser.add_argument(
        "--pdk",
        default=os.environ.get("PDK"),
        help="PDK name, for example sky130A or gf180mcuC. Defaults to $PDK.",
    )

    parser.add_argument(
        "--cthresh",
        type=float,
        default=None,
        help=(
            "Optional ext2spice capacitance threshold. "
            "If omitted, Magic's default is used."
        ),
    )

    parser.add_argument(
        "--subcircuit-top",
        action="store_true",
        help=(
            "Emit 'ext2spice subcircuit top on'. "
            "Default behavior is Magic's default, equivalent to off."
        ),
    )

    parser.add_argument(
        "--hierarchy-off",
        action="store_true",
        help=(
            "Emit 'ext2spice hierarchy off'. "
            "Default behavior is Magic's default, equivalent to hierarchy on."
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.pdk_root:
        die("PDK_ROOT is not set. Set $PDK_ROOT or pass --pdk-root.")

    if not args.pdk:
        die("PDK is not set. Set $PDK or pass --pdk.")

    gds_file_abs = os.path.abspath(args.gds_file)
    if not os.path.exists(gds_file_abs):
        die(f"GDS file does not exist: {gds_file_abs}")

    basename = os.path.splitext(os.path.basename(args.gds_file))[0]
    out_dir = os.path.dirname(gds_file_abs)
    app_dir = os.getcwd()

    magic_rc = resolve_magic_rc(args.pdk_root, args.pdk)

    cthresh_tag = "cthresh_default" if args.cthresh is None else f"cthresh_{slug(f'{args.cthresh:g}')}"
    subckt_tag = "subckt_top_on" if args.subcircuit_top else "subckt_top_off"
    hier_tag = "hier_off" if args.hierarchy_off else "hier_on"
    pdk_tag = f"pdk_{slug(args.pdk)}"

    output_tag = "__".join([pdk_tag, cthresh_tag, subckt_tag, hier_tag])
    final_spice_path = os.path.join(out_dir, f"{basename}_pex__{output_tag}.spice")

    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)

        temp_gds = os.path.join(temp_dir, f"{basename}.gds")
        os.symlink(gds_file_abs, temp_gds)

        klayout_script = f"""
import sys
import os

try:
    import klayout.db as kdb
except ImportError:
    sys.path.insert(0, os.path.join({app_dir!r}, ".venv", "lib", "python3.12", "site-packages"))
    import klayout.db as kdb

layout = kdb.Layout()
layout.read({temp_gds!r})

top_cell = None
for cell in layout.top_cells():
    if not cell.name.startswith("$$$"):
        top_cell = cell
        break

if top_cell is None:
    sys.exit(1)

print(top_cell.name)
"""

        klayout_py_path = os.path.join(temp_dir, "find_top.py")
        with open(klayout_py_path, "w") as f:
            f.write(klayout_script)

        try:
            top_cell = subprocess.check_output(
                ["uv", "run", "python", klayout_py_path],
                cwd=app_dir,
                text=True,
            ).strip().split("\n")[0]
        except Exception as e:
            die(f"Error finding top cell with KLayout: {e}")

        magic_commands = [
            "drc off",
            f"gds read {tcl_brace(temp_gds)}",
            f"load {tcl_brace(top_cell)}",
            "select top cell",
            "port makeall",
            "ext2spice lvs",
            "extract do resistance",
            "extract all",
            "ext2sim labels on",
            "ext2sim",
            "extresist simplify off",
            "extresist all",
            "ext2spice extresist on",
            "ext2spice resistor tee on",
        ]

        if args.cthresh is not None:
            magic_commands.append(f"ext2spice cthresh {args.cthresh:g}")

        if args.subcircuit_top:
            magic_commands.append("ext2spice subcircuit top on")

        if args.hierarchy_off:
            magic_commands.append("ext2spice hierarchy off")

        magic_commands.extend(
            [
                "ext2spice",
                "quit -noprompt",
            ]
        )

        with open("magic_extract.tcl", "w") as f:
            f.write("\n".join(magic_commands) + "\n")

        env = os.environ.copy()
        env["PDK_ROOT"] = str(Path(args.pdk_root).expanduser().resolve())
        env["PDK"] = args.pdk

        print(f"Using PDK_ROOT: {env['PDK_ROOT']}")
        print(f"Using PDK:      {env['PDK']}")
        print(f"Using magicrc:  {magic_rc}")
        print(f"Top cell:       {top_cell}")
        print("Running Magic extraction...")

        magic_bin = find_magic_binary()

        result = subprocess.run(
            [
                magic_bin,
                "-dnull",
                "-noconsole",
                "-rcfile",
                str(magic_rc),
                "magic_extract.tcl",
            ],
            env=env,
        )

        if result.returncode != 0:
            die(f"Magic failed with exit code {result.returncode}")

        spice_files = glob.glob("*.spice")
        spice_path = f"{top_cell}.spice"

        if not os.path.exists(spice_path) and spice_files:
            spice_path = spice_files[0]

        if not os.path.exists(spice_path):
            die("Magic did not produce a SPICE file.")

        with open(spice_path, "r") as f:
            lines = f.readlines()

        with open(final_spice_path, "w") as f:
            f.writelines(lines)

        print(f"Done. Extracted SPICE file: {final_spice_path}")


if __name__ == "__main__":
    main()