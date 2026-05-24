#!/bin/bash
#
# run_tinyqv_rcx_extract.sh ---
#
# Test of running full R-C extraction in magic on an entire (small) chip.
# Good luck!
#
echo "Starting magic."
magic -dnull -noconsole -rcfile /usr/share/pdk/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc << EOF
drc off
crashbackups stop
gds drccheck off
puts stdout "Checkpoint: start"
gds read tinyqv_quarter_label_edited_01.gds
puts stdout "Checkpoint: GDS read"
load chip_top
select top cell
flatten chip_flat
puts stdout "Checkpoint: Flattened chip"
load chip_flat
select top cell
extract path extfiles
extract do resistance
extract do unique
extract all
puts stdout "Checkpoint: Extraction done"
ext2spice lvs
ext2spice cthresh 0.1
ext2spice extresist on
ext2spice -p extfiles
puts stdout "Checkpoint: Netlist generated"
quit -noprompt
EOF
echo "Done!"
