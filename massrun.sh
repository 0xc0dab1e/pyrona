#!/bin/bash
function spatinf() {
    python3 generate_meetings.py -n $1 --config $2 --no-visual 
    python3 output_probabilities.py --config $2 --meet-table $3
}
function inf() {
    python3 output_probabilities.py --config $1 --meet-table $2
}
export -f spatinf
export -f inf
# vary the spatial config part, keep infection params the same
for conf in configs_to_run/spatial/*; do
    tag="$(basename "$conf")"
    tag="${tag:7:-5}"
    mt="output/meetings_tables/meet_table_$tag.bin.tar.bz2"
    
    echo $tag $conf $mt
done \
| xargs -n 3 --max-procs=$1 bash -c 'spatinf "$@"' _
# vary infection params, keep the spatial config (meetings table) the same
for conf in configs_to_run/infection/*; do
    mt="output/meetings_tables/meet_table_40x40.bin.tar.bz2"
    echo $conf $mt
done \
| xargs -n 2 --max-procs=$1 bash -c 'inf "$@"' _