# Pyrona: a pandemic simulator

Developed to compare potential conscripts service/leave arrangements of Finnish Defence Forces in the times of COVID-19. 

## Usage

Clone repository. Install requirements by running
```
pip3 install -r requirements.txt
```
Edit `config.yaml`

Run `generateMeetings.py` with `--no-visual` option if necessary.

Run `outputProbabilities.py --all`

Find plots and stats in `pyrona/output/stat_results` folder.


### Parallel computation
`massrun.sh` is a shell script for running several meeting table generations and probabilities outputs simultaneously. 

Usage: put some configuration files with filenames in the format `config_mytag.yaml` in the `configs_to_run` `spatial` and `infection` folders.
For configs in the spatial folder, both meeting table and infection part would be computed. For configs in the infection folder,
only the infection part. In other words, the output statistics would be based on some existing, previously-generated
meet_table and new infection parameters (from configs in the configs_to_run/infection dir).
The source meet_table for infection propagation upon should be specified directly in the 
massrun.sh script (for instance, in the default version it is *"output/meetings_tables/meet_table_40x40.bin.tar.bz2"*). 
When configs are planted and the source meeting_table is specified, run `./massrun.sh NCORES` where NCORES is the desired 
number of logical cpu cores dedicated for the parallel computation. E.g. `./massrun.sh 30`

## Extended description

`generateMeetings.py` creates a `.bin` table of all meetings between agents in the `pyrona/output/meetings_tables` folder. If generation has finished successful, the file is compressed to `.bin.tar.bz2` format. This table along with the saved config in `pyrona/output/configs` is used to compute the infection spread. The results in the form of statistics `summary.txt` and plots are saved in `pyrona/output/stat_results`.



## Other considerations

- `config.beauty.yaml` is for presentations. `config.yaml` is for actual computations. 

- Run `generateMeetings.py` without `--no-visual` option to check if your arrangement of team boxes is correct.

- `generateMeetings.py` supports `-n` or `--name` option which allows to add a tag to the filename of the generated meetings table - config pair. E.g. `generateMeetings.py --no-visual -n 4+2,nosotku`

Code uses one processor core. In order to run several meeting table generations in parallel from one console, one can run the following command multiple times
```
nohup python3 generateMeetings.py --no-visual -n your_run_identifier_string >/dev/null 2>&1 &
```