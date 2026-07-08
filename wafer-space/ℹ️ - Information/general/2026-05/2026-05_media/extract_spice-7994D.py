#!/usr/bin/env python3
import os
import sys
import subprocess
import tempfile
import shutil

def main():
    if len(sys.argv) < 2:
        print("Usage: extract_spice.py <gds_file>")
        sys.exit(1)

    gds_file = sys.argv[1]
    gds_file_abs = os.path.abspath(gds_file)
    basename = os.path.splitext(os.path.basename(gds_file))[0]
    out_dir = os.path.dirname(gds_file_abs)
    
    # We will work in a temporary directory to not clutter the original path
    # First, use klayout script to get the top cell
    klayout_script = f"""
import klayout.db as kdb
layout = kdb.Layout()
layout.read("{gds_file_abs}")
top_cells = layout.top_cells()
for cell in top_cells:
    if not cell.name.startswith("$$$"):
        print(cell.name)
        break
"""
    app_dir = os.getcwd()
    klayout_py_path = os.path.join(app_dir, "find_top.py")
    with open(klayout_py_path, "w") as f:
        f.write(klayout_script)
    
    try:
        top_cell = subprocess.check_output(["uv", "run", "python", "find_top.py"], cwd=app_dir, text=True).strip().split('\n')[0]
    except Exception as e:
        print("Error finding top cell with klayout:", e)
        sys.exit(1)
        
    print(f"Top cell found: {top_cell}")

    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        
        # Symlink the GDS file into the temp dir so magic writes files next to it locally in temp dir
        temp_gds = os.path.join(temp_dir, f"{top_cell}.gds")
        os.symlink(gds_file_abs, temp_gds)

        # Generate extraction script for magic
        magic_script = f"""
drc off
gds read {temp_gds}
load {top_cell}
select top cell
port makeall
ext2spice lvs
extract do resistance
extract all
ext2sim labels on
ext2sim {top_cell}
extresist simplify off
extresist all {top_cell}
ext2spice extresist on
ext2spice resistor tee on
ext2spice -d {top_cell}
quit -noprompt
"""
        with open("magic_extract.tcl", "w") as f:
            f.write(magic_script)

        pdk_root = os.environ.get("PDK_ROOT")
        if not pdk_root:
            pdk_root = os.path.expanduser("~/.ciel/ciel/sky130/versions/0fe599b2afb6708d281543108caf8310912f54af")
            if not os.path.exists(pdk_root):
                 pdk_root = os.path.expanduser("~/.volare/volare/sky130/versions/0fe599b2afb6708d281543108caf8310912f54af")
                 
        magic_rc = os.path.join(pdk_root, "sky130A/libs.tech/magic/sky130A.magicrc")
        
        env = os.environ.copy()
        env["PDK_ROOT"] = pdk_root

        print("Running Magic...")
        magic_bin = "magic"
        if os.path.exists("/usr/local/bin/magic"):
            magic_bin = "/usr/local/bin/magic"
        elif os.path.exists("/usr/bin/magic"):
            magic_bin = "/usr/bin/magic"
            
        subprocess.run([magic_bin, "-dnull", "-noconsole", "-rcfile", magic_rc, "magic_extract.tcl"], env=env)
        
        spice_path = f"{top_cell}.spice"
        final_spice_path = os.path.join(out_dir, f"{basename}_pex.spice")
        if os.path.exists(spice_path):
            with open(spice_path, "r") as f:
                lines = f.readlines()
                
            out_lines = []
            for line in lines:
                if line.startswith(f".subckt {top_cell}") and "VSUBS" not in line:
                    # Add default known ports from the mcml_nmos_block topology if they aren't there
                    out_lines.append(f"{line.strip()} CS IN_P IN_N OUT_P OUT_N VDD GND VCTRL VSUBS\n")
                else:
                    out_lines.append(line)
                    
            with open(final_spice_path, "w") as f:
                f.writelines(out_lines)
                
            print(f"Done. Extracted SPICE file: {final_spice_path}")
        else:
            print("Error: Magic failed to produce the SPICE file.")
            
        # Clean up the find_top.py created in the original directory
        if os.path.exists(klayout_py_path):
            os.remove(klayout_py_path)

if __name__ == '__main__':
    main()
