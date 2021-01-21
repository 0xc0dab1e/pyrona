#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This file contains functions 
"""
from llist import dllist
import numpy as np

def rotate_teams(entities, stay_chance, eval_time, dt):
    """
    Args:
        entities: tuple with pointers to teams, boxes and agents objects.
        eval_time: current time step of simulation, measured in seconds
        dt: size of simulation time step
    """
    teams, boxes, agents = entities
    
    for team in teams:
        
        if team.duty:
            
            offset = team.duty["offset"] * 24*60*60 # serving period shortcurs,
            on     = team.duty[    "on"] * 24*60*60 # converted to seconds
            off    = team.duty[   "off"] * 24*60*60
                    
            # subjective time within the service-leave cycle for each team
            st = (eval_time + offset) % (on+off)
            
            # initial teams positioning
            if eval_time == 0:
                
                if st < on:
                    # transfer to barracks
                    team.currBox = team.homeBox
                    
                    for idx in team.agent_idxs:
                        agents[idx].transfer(team.currBox)
                else:
                    # transfer to freeland
                    team.currBox = boxes["civilian"]
                    
                    for idx in team.agent_idxs:
                        agents[idx].transfer(team.currBox)
            
            # time to serve
            if 0 <= st < dt:
                
                team.currBox = team.homeBox
                
                for idx in team.agent_idxs:
                    agents[idx].transfer(team.currBox)
            
            # time to leave
            if on <= st < on+dt:
                
                team.currBox = boxes["civilian"]
                
                for idx in team.agent_idxs:
                    if np.random.rand() > stay_chance:
                        agents[idx].transfer(team.currBox)


def queue_sotilaskoti(entities, q, eval_time, dt, config):
    
    teams, boxes, agents = entities
    
    start = config['sotilaskoti']['openingHours']['start'] * 3600
    stop  = config['sotilaskoti']['openingHours']['stop']  * 3600
    
    day_time = eval_time % (24*60*60)
    
    if start <= day_time < start+dt :
        
        teams_mil, teams_civ = [], []
        
        for team in teams:
            if team.duty and team.currBox != "civilian":
                teams_mil.append(team)
            else:
                teams_civ.append(team)
        
        cons_n = config['sotilaskoti']['participants']['conscripts']
        civ_n  = config['sotilaskoti']['participants'][ 'civilians']
        
        # Randomly choose agents from conscripted and civilian teams
        
        if teams_mil:
        
            for _ in range(cons_n):
                
                team = np.random.choice(teams_mil)
                idx  = np.random.choice(team.agent_idxs)
                
                q.append({"idx"       : idx,
                          "originBox" : agents[idx].allowed_box})
        if teams_civ:
        
            for _ in range(civ_n):
                
                team = np.random.choice(teams_civ)
                idx  = np.random.choice(team.agent_idxs)
                
                q.append({"idx"       : idx,
                          "originBox" : agents[idx].allowed_box})
        
        # Populate sotilaskoti cafeteria queue with the chosen agents
            
        for p in q: # person in queue
            
            agents[p["idx"]].transfer(boxes["sotilaskoti"])
    
    
    if stop <= day_time < stop+dt:
        
        # Empty the queue and return people to their respective boxes
        
        while q:
            
            p = q.pop(0)
            
            agents[p["idx"]].transfer(p["originBox"])
            

def increment_agent_positions(agents):
    """
    Update positions and dx,dy to keep agents within boxes
    """
    for agent in agents:
        
        cage = agent.allowed_box
        
        x,  y  = agent.x,  agent.y
        dx, dy = agent.dx, agent.dy
        
        if not( cage.left   < (x + dx) <  cage.right):
            agent.dx = -dx
        if not (cage.bottom < (y + dy) <  cage.top):
            agent.dy = -dy
        
        agent.x = x + agent.dx;
        agent.y = y + agent.dy;


def x_sort(dl):
    """
    Sorts the doubly linked list of agents (dl) along the x-ordinate
    """
    n = dl.nodeat(0) # node
    nn = n.next      # next node
    
    while nn:
        
        n = nn
        nn = n.next
        nb = n.prev # previous node
        
        dis = False # disordered: if neighbour pair of agents is in the wrong
                    #      order. By default innocent until found guilty.
        
        while True:
            
            if not nb: # if the list start is reached, just insert there
                e = dl.remove(n) # e: element stored within the node
                dl.appendleft(e)
                break
            
            if not dis: # if things are already ok 
                if nb.value.x < n.value.x:
                    break
            
            dis = True
            
            if nb.value.x < n.value.x: # proper position is found, insert here
                e = dl.remove(n)
                dl.insert(e, nb.next)
                break
            
            nb = nb.prev

    return dl


def initial_sort(agents):
    """
    Perform an initial sort of agents along the x-ordinate (later such sorted
    list is needed for a bit faster neighbours finding computation). Since
    agents x-positions are initially randomly distributed, an off-the-shelf
    numpy quicksort appears to be an optimal choice. 
    Args:
        agents: list with references to (spatial) agents instances
    Out:
        dl: sorted doubly linked list with references to agents instances
    """
    
    IX = [] # list of indexes and positions along the x-ordinate
    
    for agent in agents: IX.append([agent.idx, agent.x])
        
    IXs = np.argsort(IX, axis=0) # sorted according to x-ordinate positions
    
    Is = IXs[:,1] # leave just indices
    
    agents_x_sorted = np.array(agents)[Is]
    
    dl = dllist(agents_x_sorted) # to doubly linked list
    
    return dl


def detect_meetings(agents_x_sorted, eval_time, config, visualize):
    """
    Args:
        agents: list with agents objects
        eval_time: time in seconds elapsed from the simulation start
        config: config read from the yaml
    Out:
        meets_curr: set of frozensets
        Contains info about close agents at this step of the simulation. Each
        frozenset contains two numbers - indexes of agents that form one 
        connection. 
    """
    if visualize:
        for agent in agents_x_sorted:
            agent.color = (1.0, 1.0, 1.0, 0.0)
    
    
    rad = config["infection"]["radius"]
    
    meets_curr = dict()
    
    n = agents_x_sorted.nodeat(0) # node (contains the reference agent)
    nn = n.next                   # next node (contains the following agent)
    
    while nn:
        
        nears = []
        
        n = nn
        nn = n.next
        nb = n.prev
        
        while nb:
            
            dx = n.value.x - nb.value.x
            
            if dx < rad:
                
                dy = n.value.y - nb.value.y
                
                dist = (dx*dx + dy*dy)**0.5
                
                if dist < rad:
                    
                    nears.append(nb.value)
            else:
                break
            
            nb = nb.prev
        
        for near in nears:
            
            link  = frozenset({n.value.idx, near.idx}) # who with who
            place = n.value.allowed_box.name # where
            
            meets_curr[link] = place
            
        # paint agents within a Euclidean circle red
        if visualize:
            color = (1.0, 0.0, 0.051, 1.0)
            if nears: n.value.color = color
            
            for near in nears:
                near.color = color
            
            
    return meets_curr





















