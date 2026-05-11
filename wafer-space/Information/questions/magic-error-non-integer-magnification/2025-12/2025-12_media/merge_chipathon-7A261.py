# Copyright (c) 2025 Leo Moser <leo.moser@pm.me>
# SPDX-License-Identifier: Apache-2.0

import sys
import pya
import argparse

def merge_layouts(
    padring_path: str,
    chipathon_path: str,
    output: str,
):
    # Create the main layout and read the padring
    main_layout = pya.Layout()
    main_layout.read(padring_path)
    
    top_cell = main_layout.top_cell()
    
    # Create a separate layout to prevent cell conflicts
    chipathon_layout = pya.Layout()

    # Read the chipathon layout
    chipathon_layout.read(chipathon_path)

    # Get the top cell
    chipathon_layout_topcell = chipathon_layout.top_cell()
    assert chipathon_layout_topcell.name == "chiptop_A_track"

    dbbox = chipathon_layout.top_cell().dbbox()
    print(dbbox)

    # Create new cell in main layout
    chipathon_cell = main_layout.create_cell("chipathon")

    # Copy the contents into the cell
    chipathon_cell.copy_tree(chipathon_layout_topcell)

    # Insert the user cell
    top_cell.insert(
        pya.DCellInstArray(
            chipathon_cell,
            # Coordinates for the chipathon project
            pya.DPoint(
                500,
                500,
            ),
        )
    )
    
    # Replace the chipathon bondpad with the template bondpad
    donor_cell = main_layout.cell("Bondpad_5LM")
    recipient_cells = main_layout.cells("Bondpad_5LM*")
    
    for recipient_cell in recipient_cells:
        # ignore the donor
        if recipient_cell == donor_cell:
            continue
        
        recipient_cell.clear_insts()
        recipient_cell.clear_shapes()
        recipient_cell.copy_tree(donor_cell)
    
    # We need to clean up the new top cells
    for top_cell in main_layout.top_cells():
        if top_cell.name != "padring_ws":
            top_cell.delete()
    
    main_layout.write(output)

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    
    parser.add_argument(
        "padring",
        help="The padring GDS."
    )

    parser.add_argument(
        "chipathon",
        help="The chipathon GDS."
    )

    parser.add_argument(
        "output",
        help="The output GDS.",
        nargs="?",
        default="output.gds",
    )

    # Parse the arguments
    args = vars(parser.parse_args())

    merge_layouts(args["padring"], args["chipathon"], args["output"])
