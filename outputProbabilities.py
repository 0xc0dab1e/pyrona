#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This file is described in readme.md
"""
import argparse 
import tarfile
from tqdm import tqdm 
import matplotlib as mpl; mpl.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import pickle
import seaborn as sns
import sys
import yaml
from entities import generate_infection_entities
from entities import init_infect

from parsing import find_table_config_pairs

# task 1: import correct file
"""
Read command line option specifying which file(s) should be processed
"""
parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument('--all', action='store_true', 
                    help='Generate output probabilities for all meeting \
                          table files in the output/meeting_tables folder',)
group.add_argument('-n', '--name', default='',
                    help='Specify part of a meeting table / config filename \
                          you wish output probabilities to be computed for.')

args = parser.parse_args()

if args.all:
    tag = ''
if args.name:
    tag = args.name

print(tag)

"""
Safety check if the scripts have been run in the correct order
"""
if not os.path.exists("output"):
    print("\nAn 'output' folder is not detected \
in the root folder of the project. \
Please run the generateMeetings.py file first.\n")
    sys.exit(1)

paths = {"configs"     : os.path.join("output", "configs"),
         "meet_tables" : os.path.join("output", "meetings_tables"),
         "out_stats"   : os.path.join("output", "stat_results")}

path_pairs = find_table_config_pairs(tag, paths)

if not path_pairs:
    print("Are you sure that output files with specified tag exist?")
    sys.exit(1)
else: 
    print(f"Found {len(path_pairs)} [meet_table, config] pairs")

fig_n = 0

for i, path_pair in enumerate(path_pairs):
    
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
    
    agents = generate_infection_entities(config)
    
    init_infect(agents, config)
    
    """
    Calculate probabilities for each day for each agent to be sympt. infected
    
    """
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
        
        day_n = ts//(24*60*60)
        
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
    
    df = pd.DataFrame(data=data)
    
    del(data)
    
    meets_N = {"mil" : [],
               "civ" : []}
    
    for agent in agents:
        if agent.conscripted:
            meets_N["mil"].append(agent.meetings_n)
        else: 
            meets_N["civ"].append(agent.meetings_n)
    
    results_foldername = tag if tag else path_pair['tag']
    
    out_path = os.path.join("output/stat_results", results_foldername)
    if not os.path.exists(out_path):
        os.makedirs(out_path)
    
    df_n = df.rename(columns={'status': 'Type', 
                                  'inf_p' : 'Infected population fraction', 
                                  'imm_p' : 'Immune population fraction', 
                                  'day'   : 'Day'})
    
    title_ending = config["figTitleEnd"]
    
    """
    Plot and save the infection spread.
    """
    fig_n += 1
    fig = plt.figure(fig_n)
    print("plotting Figure "+ str(fig_n) + " . . .")
    
    sns.set_theme()
    sns.set_context("paper")
    ax = sns.lineplot(data=df_n, x="Day", y='Infected population fraction',
                      hue="Type")
    ax.set_title('Infection spread'+ title_ending)
    fig_name = "infection"
    fig_path = os.path.join(out_path, fig_name)
    
    ax.set_xlim(  left=0, right= 200) 
    #ax.set_ylim(bottom=0, top=0.05) 
    ax.set_ylim(bottom=0, top=0.3) 
    
    ax.get_xaxis().set_major_locator(mpl.ticker.MultipleLocator(20.0))
    ax.get_xaxis().set_minor_locator(mpl.ticker.MultipleLocator( 5.0))
    ax.get_yaxis().set_major_locator(mpl.ticker.MultipleLocator(0.0500))
    ax.get_yaxis().set_minor_locator(mpl.ticker.MultipleLocator(0.0125))
    ax.grid(b=True, which='major', color='w', linewidth=1.0)
    ax.grid(b=True, which='minor', color='w', linewidth=0.5)
    
    plt.tight_layout()
    
    fig.set_rasterized(True)
    ax.set_rasterized(True)
    fig.savefig(fig_path +'.tiff', dpi=300)
    
    fig.set_rasterized(False)
    ax.set_rasterized(False)
    fig.savefig(fig_path +'.pdf')
    
    
    """
    Plot and save the immunity gain.
    """
    fig_n += 1
    fig = plt.figure(fig_n)
    print("plotting Figure "+ str(fig_n) + " . . .")
    
    sns.set_theme()
    sns.set_context("paper")
    ax = sns.lineplot(data=df_n, x="Day", y='Immune population fraction',
                      hue="Type")
    ax.set_title('Immunity gain'+ title_ending)
    fig_name = "immunity"
    fig_path = os.path.join(out_path, fig_name)
    
    ax.set_xlim(  left=0, right=200) 
    ax.set_ylim(bottom=0,   top=1.0) 
    
    ax.get_xaxis().set_major_locator(mpl.ticker.MultipleLocator(20.0))
    ax.get_xaxis().set_minor_locator(mpl.ticker.MultipleLocator( 5.0))
    ax.get_yaxis().set_major_locator(mpl.ticker.MultipleLocator(0.10))
    ax.get_yaxis().set_minor_locator(mpl.ticker.MultipleLocator(0.02))
    ax.grid(b=True, which='major', color='w', linewidth=1.0)
    ax.grid(b=True, which='minor', color='w', linewidth=0.5)
    
    plt.tight_layout()
    
    fig.set_rasterized(True)
    ax.set_rasterized(True)
    fig.savefig(fig_path +'.tiff', dpi=300)
    
    fig.set_rasterized(False)
    ax.set_rasterized(False)
    fig.savefig(fig_path +'.pdf')
    
    
    stats_path = os.path.join(out_path, "summary.txt")
    
    with open(stats_path, 'w') as file:
    
        max_inf = 0.0
        sum_inf = 0.0
        n_days = config["outputStatsFor"]
        
        
        for n_day in range(1, n_days):
            
            infs_df = df[(df.status == "mil") & (df.day == n_day)].inf_p
            
            avg_inf = np.average(infs_df)
            
            if avg_inf > max_inf:
                max_inf = avg_inf
                
                max_infs_df = infs_df
            
            sum_inf += avg_inf
        
        
        """
        Stats save to the .txt file
        """
        lower_bound = config["infection"]["acute"]["daysMin"]
        upper_bound = config["infection"]["acute"]["daysMax"]
        
        average_duration = (lower_bound + upper_bound) / 2
        
        undergone_inf = sum_inf / average_duration
        
        file.write((f"Fraction of conscripts that have had the infection"
                    f"( within the first {n_days} days): "
                    f"\n{undergone_inf*100:.1f}%"))
        
        file.write((f"\nMaximum fraction of simultaneously infected conscripts"
                    f"( within the first {n_days} days): "
                    f"\n{      max_inf*100:.1f}%"))
        
        max_sympt = max_inf*(1 - config["infection"]["asymptomatic"]["chance"])
        
        file.write((f"\nOut of which symptomatic: \n{max_sympt*100:.1f}%"))


    # histogram of infected people distribution
    plt.close('all')
    
    fig_n += 1
    print("plotting Figure "+ str(fig_n) + " . . .")
    
    sns.set_theme()
    sns.set_context("paper")
    g = sns.displot(max_infs_df)
    
    g.set_axis_labels(x_var="Probability of being infected", 
                      y_var="Number of conscripts")
    
    fig = g.ax.get_figure()
    
    plt.title(('Infection distribution among conscripts'
               ' at the peak of pandemic'))
    fig_name = "infection_distribution_at_peak"
    
    plt.tight_layout()
    
    fig_path = os.path.join(out_path, fig_name)
    
    fig.set_rasterized(True)
    g.ax.set_rasterized(True)
    fig.savefig(fig_path +'.tiff', dpi=300)
    
    fig.set_rasterized(False)
    g.ax.set_rasterized(False)
    fig.savefig(fig_path +'.pdf')

    # conscripts
    # histogram of the meetings number
    data = {"meets_n"    : [],
            "spread_inf" : [],}
    
    for agent in agents:
        
        if agent.conscripted:
            data[   "meets_n"].append(agent.meetings_n )
            data["spread_inf"].append(agent.infection_transmitted)
        
    spread_df = pd.DataFrame(data=data)
    
    plt.close('all')
    
    fig_n += 1
    print("plotting Figure "+ str(fig_n) + " . . .")
    
    avg_daily_meets = spread_df["meets_n"] / n_days
    
    sns.set_theme()
    sns.set_context("paper")
    g = sns.displot(avg_daily_meets)
    
    fig = g.ax.get_figure()
    
    g.set_axis_labels(x_var="Average meetings per day", 
                      y_var="Number of conscripts")
    
    plt.title('Conscript meetings count distribution')
    fig_name = "conscript_meetings_distribution"
    
    plt.tight_layout()
    
    fig_path = os.path.join(out_path, fig_name)
    
    fig.set_rasterized(True)
    g.ax.set_rasterized(True)
    fig.savefig(fig_path +'.tiff', dpi=300)
    
    fig.set_rasterized(False)
    g.ax.set_rasterized(False)
    fig.savefig(fig_path +'.pdf')
    
    
    # histogram of infection amount transmitted (spread)
    plt.close('all')
    
    fig_n += 1
    print("plotting Figure "+ str(fig_n) + " . . .")
    
    sns.set_theme()
    sns.set_context("paper")
    g = sns.displot(spread_df["spread_inf"])
    
    fig = g.ax.get_figure()
    
    g.set_axis_labels(x_var="Number of people infected (1.0 = one human)", 
                      y_var="Number of conscripts with such spreading rating")
    
    plt.title('\"Amount of infection\" spread by conscripts')
    fig_name = "conscript_infection_transmitted"
    
    plt.tight_layout()
    
    fig_path = os.path.join(out_path, fig_name)
    
    fig.set_rasterized(True)
    g.ax.set_rasterized(True)
    fig.savefig(fig_path +'.tiff', dpi=300)
    
    fig.set_rasterized(False)
    g.ax.set_rasterized(False)
    fig.savefig(fig_path +'.pdf')
    
    # civilians
    # histogram of the meetings number
    data = {"meets_n"    : [],
            "spread_inf" : [],}
    
    for agent in agents:
        
        if not agent.conscripted:
            data[   "meets_n"].append(agent.meetings_n )
            data["spread_inf"].append(agent.infection_transmitted)
        
    spread_df = pd.DataFrame(data=data)
    
    plt.close('all')
    
    fig_n += 1
    print("plotting Figure "+ str(fig_n) + " . . .")
    
    avg_daily_meets = spread_df["meets_n"] / n_days
    
    sns.set_theme()
    sns.set_context("paper")
    g = sns.displot(avg_daily_meets)
    
    fig = g.ax.get_figure()
    
    g.set_axis_labels(x_var="Average meetings per day", 
                      y_var="Number of civilians")
    
    plt.title('Civilian meetings count distribution')
    fig_name = "civilian_meetings_distribution"
    
    plt.tight_layout()
    
    fig_path = os.path.join(out_path, fig_name)
    
    fig.set_rasterized(True)
    g.ax.set_rasterized(True)
    fig.savefig(fig_path +'.tiff', dpi=300)
    
    fig.set_rasterized(False)
    g.ax.set_rasterized(False)
    fig.savefig(fig_path +'.pdf')
    
    
    # histogram of infection amount transmitted (spread)
    plt.close('all')
    
    fig_n += 1
    print("plotting Figure "+ str(fig_n) + " . . .")
    
    sns.set_theme()
    sns.set_context("paper")
    g = sns.displot(spread_df["spread_inf"])
    
    fig = g.ax.get_figure()
    
    g.set_axis_labels(x_var="Number of people infected (1.0 = one human)", 
                      y_var="Number of civilians with such spreading rating")
    
    plt.title('\"Amount of infection\" spread by civilians')
    fig_name = "civilian_infection_transmitted"
    
    plt.tight_layout()
    
    fig_path = os.path.join(out_path, fig_name)
    
    fig.set_rasterized(True)
    g.ax.set_rasterized(True)
    fig.savefig(fig_path +'.tiff', dpi=300)
    
    fig.set_rasterized(False)
    g.ax.set_rasterized(False)
    fig.savefig(fig_path +'.pdf')




















