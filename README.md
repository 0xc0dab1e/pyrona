# Pyrona: a pandemic simulator

Developed to compare potential conscripts service/leave arrangements of Finnish Defence Forces in the times of COVID-19. 

## Usage

Clone repository. Install requirements by running

	pip3 install -r requirements.txt

Edit `config.yaml`

Run `generateMeetings.py` with `--no-visual` option if necessary.

Run `outputProbabilities.py --all`

Find plots and stats in `pyrona/output/stat_results` folder.



## Extended description

`generateMeetings.py` creates a `.bin` table of all meetings between agents in the `pyrona/output/meetings_tables` folder. If generation has finished successful, the file is compressed to `.bin.tar.bz2` format. This table along with the saved config in `pyrona/output/configs` is used to compute the infection spread. The results in the form of statistics `summary.txt` and plots are saved in `pyrona/output/stat_results`.



## Other considerations

- `config.beauty.yaml` is for presentations. `config.yaml` is for actual computations. 

- Run `generateMeetings.py` without `--no-visual` option to check if your arrangement of team boxes is correct.

- `generateMeetings.py` supports `-n` or `--name` option which allows to add a tag to the filename of the generated meetings table - config pair. E.g. `generateMeetings.py --no-visual -n 4+2,nosotku`

Code uses one processor core. In order to run several meeting table generations in parallel from one console, one can run command  

	nohup python3 generateMeetings.py --no-visual -n 4+2,std05,all_meetings,nosotku >/dev/null 2>&1 &