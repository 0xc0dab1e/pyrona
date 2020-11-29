#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This file contains functions called during the simulation time step update.
"""
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


def detect_meetings(agents, iXY, eval_time, config, visualize):
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
        for agent in agents:
            agent.color = (1.0, 1.0, 1.0, 0.0)
    
    
    for i, agent in enumerate(agents):
        
        assert(i==agent.idx)
        
        
        
        iXY[i] = (agent.idx, agent.x, agent.y)
    
    # sort along X-axis
    # resulting shape: [original index, sorted x, y]
    iXsY = iXY[iXY['x'].argsort()] 
    
    rad = config["infection"]["radius"]
    
    meets_curr = dict()
    
    for k in range(len(agents)):
        
        nears = []
        
        caret = k-1 
        while(caret >= 0):
            
            dx = iXsY['x'][k] - iXsY['x'][caret]
            
            if dx < rad:
                
                dy = iXsY['y'][k] - iXsY['y'][caret]
                
                dist = np.sqrt(dx*dx + dy*dy)
            
                if dist < rad:
                    
                    nears.append(iXsY['idx'][caret])
            else: 
                break
            
            caret -= 1
        
        
        
        # leave only the ones within a Euclidean circle        
        color = (1.0, 0.0, 0.051, 1.0)
        reference_agent_id = iXsY['idx'][k]
        
        if visualize:
            if nears: agents[reference_agent_id].color = color
        
        for near in nears:
            
            link  = frozenset({reference_agent_id, near}) # who with who
            place = agents[reference_agent_id].allowed_box.name  # where
            
            meets_curr[link] = place
            
            agents[near].color = color
        
    return meets_curr

