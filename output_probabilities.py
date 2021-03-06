#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This script plots graphs, computes and writes down statistics about the 
infection spread based on agents "meeting tables" pre-generated by the
generateMeetings.py script. Please run these scripts in the correct order.
"""
import argparse 
import tarfile
from tqdm import tqdm 
import numpy as np
import os
import pandas as pd
import pickle
import sys
import yaml
from entities import generate_infection_entities
from entities import init_infect
from parsing import find_table_config_pairs
from plotting import distribution_plot, linear_plot

"""
Read command line option specifying which file(s) should be processed

"""
parser = argparse.ArgumentParser()
group = parser.add_argument_group()
group.add_argument('--all', action='store_true', 
                    help='Generate output probabilities for all meeting \
                          table files in the output/meeting_tables folder',)
group.add_argument('-n', '--name', default='',
                    help='Specify part of a meeting table / config filename \
                          you wish output probabilities to be computed for.')
group_rewrite = parser.add_argument_group()
group_rewrite.add_argument('--rewrite', action='store_true',
                         help='Fully rewrite all_stats.csv file instead of \
                               appending to it.')
group_massrun = parser.add_argument_group()
group_massrun.add_argument('--config', default='',
                           help='Specify a full path to a configuration file \
                                 deployed for this computation run.')
group_massrun.add_argument('--meet-table', default='',
                           help='Specify a full path to a meeting table used \
                                 as a basis for this computation run.')
args = parser.parse_args()

if not (args.all or args.name or args.config or args.meet_table):
        print('\nEither --all or --name or (--config together with',
              '--meet-table) must be specified.',
              'The program either tries to process all possible',
              'config-meeting table pairs, or searches ones with some',
              'specific pattern in filenames (--name option) or just processes',
              'a particular config/meeting table pair with full path',
              'specified for both of them (that one is useful for mass-runs)',
              'via an orchestrating bash script.',
              '\n')
        sys.exit(1)
if args.all and args.name:
    print('\nIt should be either all config/meet tables or the ones with some',
          'specific pattern in their name (-n == --name option). Make your',
          'choice.',
          '\n')
    sys.exit(1)
if (bool(args.config) ^ bool(args.meet_table)): # either both or none
    print('\nSpecify both config and meeting table paths. This is the most',
          'manual way of running this program and there both options must',
          'be specified.',
          '\n')
    sys.exit(1)

"""
Safety check if the scripts have been run in the correct order

"""
if not os.path.exists("output"):
    print(("\nAn 'output' folder is not detected"
           " in the root folder of the project."
           " Please run the generateMeetings.py file first.\n"))
    sys.exit(1)

"""
Setup folders to take information for infection spread calculation
             and to store outputs for each set on input conditions
"""
paths = {"configs"     : os.path.join("output", "configs"),
         "meet_tables" : os.path.join("output", "meetings_tables"),
         "out_stats"   : os.path.join("output", "stat_results")}

"""
Search for files with speified pattern in filename to process (or just read
full paths from options). 

"""
if args.all or args.name:

    if args.all:
        tag = ''
    if args.name:
        tag = args.name

    path_pairs = find_table_config_pairs(tag, paths)

#sys.exit(0)

if args.config and args.meet_table:
    # from e.g. 'config_mytag_10:11:12.yaml' filename leave just 'mytag'
    tag = os.path.basename(args.config)[7:-5]
    path_pairs = [{
        'config' : args.config,
        'meet_table' : args.meet_table,
        'tag' : tag,
        }]

if not path_pairs:
    print("Are you sure that output files with specified tag exist?")
    sys.exit(1)
else: 
    print(f"Found {len(path_pairs)} [meet_table, config] pairs")

"""
Specify meta-file for statistics from all runs to be summarized in.

"""    
common_damp_path = os.path.join(paths['out_stats'], 'all_stats.csv')

if args.rewrite:
    with open(common_damp_path, "w") as file:
        line = ("tag"       "\t"
                "peak_sympt""\t"
                "had_disease")
        file.write(line) # headline for a tab-separated csv with results

# for each set of initial conditions originally defined in the config file
for i, path_pair in enumerate(path_pairs): 
    
    results_foldername = tag if tag else path_pair['tag']
    
    out_path = os.path.join("output/stat_results", results_foldername)
    if not os.path.exists(out_path):
        os.makedirs(out_path)
    
    print(f"Pair {i+1} name: \"{path_pair['tag']}\"")
    
    with open(path_pair['config']) as file:
        config = yaml.load(file, Loader=yaml.FullLoader)
    
    timelines = []
    with tarfile.open(path_pair['meet_table'], "r:bz2") as tar:
        print('Loading meetings file . .')
        for member in tar:
            file = tar.extractfile(member)
            while True:
                try:
                    timelines.append(pickle.load(file))
                except EOFError:
                    break
    
    """
    Compute infection spread (probabilities of infection states for each agent
                                                                 for each day)
    """
    agents = generate_infection_entities(config)
    
    init_infect(agents, config)
    
    data = {"day"    : [],
            "status" : [],
            "inf_p"  : [],
            "imm_p"  : [],}
    
    for timeline in tqdm(timelines):
        
        ts, meets = timeline['timestamp'], timeline['meetings']
        
        for link, place in meets.items():
            
            link = tuple(link)
            
            ag_0 = agents[link[0]]
            ag_1 = agents[link[1]]
            
            if np.random.rand() > ag_0.meets_dropout:
            
                ag_0.infection.update(ts, ag_0, place, config)
                ag_1.infection.update(ts, ag_1, place, config)
                
                ag_0.infection.transfer(ts, ag_1)
                ag_1.infection.transfer(ts, ag_0)
                
                ag_0.meetings_n += 1
                ag_1.meetings_n += 1
        
        day_n = ts//(24*60*60) + 1
        
        if len(data['day']) < day_n*len(agents):
        
            for agent in agents:
                
                inf = agent.infection.parts_inf.values()
                inf = sum( list(inf) )
                
                imm = agent.infection.parts_imm.values()
                imm = sum( list(imm) )
                
                data["inf_p"].append(inf)
                data["imm_p"].append(imm)
                    
                if agent.conscripted:
                    
                    data['status'].append('mil')
                else:
                    data['status'].append('civ')
            
                data["day"].append(day_n)
    
    """
    Save computed infection spread in the dataframe
    
    """
    df = pd.DataFrame(data=data)
    
    #del(data)
    
    """
    Segregate conscripts and civilians for separate stats clculation
    
    """
    meets_N = {"mil" : [],
               "civ" : []}
    
    for agent in agents:
        if agent.conscripted:
            meets_N["mil"].append(agent.meetings_n)
        else: 
            meets_N["civ"].append(agent.meetings_n)
    
    n_days = config["outputStatsFor"]
    
    meets_per_day_mil = np.average(meets_N['mil']) / n_days
    meets_per_day_civ = np.average(meets_N['civ']) / n_days
    
    
    """
    Compute the vital statistics: infected conscripts fraction at peak,
                      total number of conscripts who had the infection
    """
    if config['outputStatsFor'] > config['simulationDuration']:
        print(("Warning: the desired time period for statistics computation"
               "exceeds the total simulation length. This can and will"
               "lead to fun. Make sure that in the config the 'outputStatsFor'"
               "value is less or equal to the 'simulationDuration'"
               "number of days"))
    
    top_inf, max_inf, sum_inf = 0, 0, 0
    
    for n_day in range(0, n_days):
        
        n_day += 1 # maintain the possibility to run single-day simulations
        
        infs_df = df[(df.day == n_day)].inf_p
        
        top_inf = max(top_inf, np.average(infs_df))
        
        infs_df = df[(df.status == "mil") & (df.day == n_day)].inf_p
        
        avg_inf = np.average(infs_df)
        
        if avg_inf >= max_inf:
            
            max_inf = avg_inf
            
            at_peak_day_df = infs_df
        
        sum_inf += avg_inf
        
    lower_bound = config["infection"]["acute"]["daysMin"]
    upper_bound = config["infection"]["acute"]["daysMax"]
    
    average_duration = (lower_bound + upper_bound) / 2
    
    undergone_inf = sum_inf / average_duration
    
    """
    Save statistics from one set of conditions to the summary.txt file
    
    """
    stats_path = os.path.join(out_path, "summary.txt")
    
    with open(stats_path, 'w') as file:
        
        file.write((f"Fraction of conscripts that have had the infection"
                    f" (within the first {n_days} days): "
                    f"\n{undergone_inf*100:.1f}%"))
        
        file.write((f"\nMaximum fraction of simultaneously infected conscripts"
                    f" (within the first {n_days} days): "
                    f"\n{max_inf*100:.1f}%"))
        
        max_sympt = max_inf*(1 - config["infection"]["asymptomatic"]["chance"])
        
        file.write((f"\nOut of which symptomatic: \n{max_sympt*100:.1f}%"))
    
    
    """
    Dataframe with better name fields for out-of-the-box seaborn plotting
    """
    df_n = df.rename(columns={'status': 'Type', 
                                  'inf_p' : 'Infected population fraction', 
                                  'imm_p' : 'Immune population fraction', 
                                  'day'   : 'Day'})
    
    mu    = config["movementSpeed"][   "mu"]
    sigma = config["movementSpeed"]["sigma"]
    
    """
    Figures title appendix generator.
    
    """
    title_tag = ""
    
    fft = config["figTitle"]["freeFormTag"]
    if fft:
        title_tag += "\n"
        title_tag += f"{fft}"
    if config["figTitle"]["velocityInfo"]:
        title_tag += "\n"
        title_tag += (f"[agents velocity: μ={mu}, "
                      f"σ={mu*sigma} meters/day]")
    if config["figTitle"]["meetingsNumber"]:
        title_tag += "\n"
        title_tag += (f"[average meetings per day: " 
                      f"civ≈{meets_per_day_civ:.2f} " 
                      f"mil≈{meets_per_day_mil:.2f}]")
    fig_n = 0
    
    """
    Plot and save the infection spread.
    
    """
    # make around the same length of y-axes in similar grpahs for easier 
    # visual comparison. E.g. border right at 10, 20, 30% etc.
    ylim = (top_inf+0.05)//0.05*0.05 # 0.05 for 5% step.
    
    linear_plot(fig_n:=fig_n+1, df_n, 
                x_column="Day", y_column='Infected population fraction',
                xlim=config['outputStatsFor'], 
                ylim=ylim, y_ticks_major_minor=(0.05, 0.01),
                title=(f"Infection spread" f"{title_tag}"),
                fig_name="infection", save_path=out_path)

    """
    Plot and save the population immunity gain.
    
    """
    linear_plot(fig_n:=fig_n+1, df_n, 
                x_column="Day", y_column='Immune population fraction',
                xlim=config['outputStatsFor'],
                ylim=1.0, y_ticks_major_minor=(0.10, 0.02),
                title=(f"Immunity gain" f"{title_tag}"),
                fig_name="immunity", save_path=out_path)
    
    
    """
    Plot the infected people distribution at the peak of pandemic
    """
    distribution_plot(
        fig_n:=fig_n+1, at_peak_day_df, 
        x_label="Probability of being infected",
        y_label="Number of conscripts",
        title=('Infection probability distribution among'
               '\nconscripts at the peak of the pandemic.'  
               f"{title_tag}"),
        fig_name="infection_distribution_at_peak", 
        save_path=out_path)
    
    """
    Histograms for average meetings per day and transmitted infection Prob.
    First for conscripts, then for civilians
    """
    # conscripts
    data = {"meets_n"    : [],
            "spread_inf" : [],}
    
    for agent in agents:
        
        if agent.conscripted:
            data[   "meets_n"].append(agent.meetings_n )
            data["spread_inf"].append(agent.infection_transmitted)
        
    spread_df = pd.DataFrame(data=data)
    
    print(out_path)
    
    avg_daily_meets = spread_df["meets_n"] / n_days
    
    distribution_plot(
        fig_n:=fig_n+1, avg_daily_meets,
        x_label="Average meetings per day",
        y_label="Number of conscripts",
        title=("Conscript meetings count distribution" f"{title_tag}"),
        fig_name="conscript_meetings_distribution", 
        save_path=out_path)
    
    distribution_plot(
        fig_n:=fig_n+1, spread_df["spread_inf"], 
        x_label="Cummulative infection probability transmitted",
        y_label="Number of conscripts with such spreading rating",
        title=('\"Amount of infection\" spread by conscripts' f"{title_tag}"),
        fig_name="conscript_infection_transmitted", 
        save_path=out_path)

    # civilians
    data = {"meets_n"    : [],
            "spread_inf" : [],}
    
    for agent in agents:
        
        if not agent.conscripted:
            data[   "meets_n"].append(agent.meetings_n )
            data["spread_inf"].append(agent.infection_transmitted)
        
    spread_df = pd.DataFrame(data=data)
    
    
    avg_daily_meets = spread_df["meets_n"] / n_days
    
    distribution_plot(
        fig_n:=fig_n+1, avg_daily_meets,
        x_label="Average meetings per day",
        y_label="Number of civilians",
        title=('Civilian meetings count distribution' f"{title_tag}"),
        fig_name="civilian_meetings_distribution", 
        save_path=out_path)
    
    distribution_plot(
        fig_n:=fig_n+1, spread_df["spread_inf"], 
        x_label="Cummulative infection probability transmitted",
        y_label="Number of civilians with such spreading rating",
        title=('\"Amount of infection\" spread by civilians' f"{title_tag}"),
        fig_name="civilian_infection_transmitted", 
        save_path=out_path)
    
    """
    Write the primary simulation results for a given set of initial conditions 
    to an all-collecting results file. 
    """
    
    line = f"\n{path_pair['tag']}\t{max_sympt}\t{undergone_inf}"
    
    with open(common_damp_path, "a") as file:
        
        file.write(line) # one line with primary stats 
                         # for each set of conditions
        












