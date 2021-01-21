#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
from datetime import datetime # for timestamp in generated filenames
import numpy as np
import os
import pickle
import shutil
import tarfile
from tqdm import tqdm 
import yaml
from entities import generate_spatial_entities
from updates import detect_meetings
from updates import increment_agent_positions
from updates import initial_sort
from updates import queue_sotilaskoti
from updates import rotate_teams
from updates import x_sort

parser = argparse.ArgumentParser()
parser.add_argument('--no-visual', action='store_true',
                    help='Switch off the simulation rendering window',)
parser.add_argument('-n', '--name', default='',
                    help='Name tag for the generated config, meetings table \
                          and result files')
parser.add_argument('--config', default='',
                    help=('Path to a configuration file to use instead of a',
                          'config.yaml in the repository root folder.'))

args = parser.parse_args()
visualize = not args.no_visual # by default: visualize

"""
Conditional OpenGL import (only on the module level)

"""
if visualize:
    import glfw
    from OpenGL.GL import ctypes
    from OpenGL.GL import glBindBuffer, glBufferData, glClear, glClearColor
    from OpenGL.GL import glDrawArrays, glGenBuffers, glGetAttribLocation
    from OpenGL.GL import glGetUniformLocation, glEnableVertexAttribArray
    from OpenGL.GL import glVertexAttribPointer, glUniform2f, glUniform4f
    from OpenGL.GL import glUseProgram
    from OpenGL.GL import GL_ARRAY_BUFFER, GL_COLOR_BUFFER_BIT, GL_LINE_LOOP
    from OpenGL.GL import GL_STATIC_DRAW, GL_TRIANGLES, GL_FLOAT, GL_FALSE
    from plotting import generate_agents_verticies
    from plotting import generate_map
    from plotting import compile_shader
    import time # for an FPS limit
    """
    Sorry for the following OpenGL code. It appears to rely on global variables
    within the __main__ function and therefore is hard to encapsulate. 
    """


def main(visualize):
    
    if args.config:
        config_path = args.config
    else:
        config_path = "config.yaml"
    
    with open(config_path) as file:
        config = yaml.load(file, Loader=yaml.FullLoader)
    
    teams, boxes, agents = generate_spatial_entities(config)
    
    agents_x_sorted = initial_sort(agents)
    
    if config["sotilaskoti"]["allow"]:
        # create queue to the sotilaskoti
        q = []
    
    # table of meetings between agents, from the previous simulation step
    meets_prev = dict() 
    
    if visualize:
        
        # verticies for area borders and inferred width and height of the map.
        # I.e. canvas contains map width and height in meters for computations
        fences_verts, canvas = generate_map(boxes, config)
        # verticies for traingles that represent agents
        agents_verts = generate_agents_verticies(config)
        
        
        if not glfw.init():
            return
    
        window = glfw.create_window(config["window"][ "width"],
                                    config["window"]["height"],
                                    config["window"][ "title"], 
                                    None, None)
        if not window:
            glfw.terminate()
            return
        
        glfw.make_context_current(window)
        
        # compile shader for on-the-fly configurable trianges
        shader = compile_shader()
        
        # create Buffer object in gpu
        VBO = glGenBuffers(2)
    
        # bind buffers
        glBindBuffer(GL_ARRAY_BUFFER, VBO[0])
        glBufferData(GL_ARRAY_BUFFER, 
                     fences_verts.nbytes, 
                     fences_verts, 
                     GL_STATIC_DRAW)
        
        glBindBuffer(GL_ARRAY_BUFFER, VBO[1])
        glBufferData(GL_ARRAY_BUFFER,
                     agents_verts.nbytes,
                     agents_verts,
                     GL_STATIC_DRAW)
        
        fences_stride = fences_verts.strides[0]
        agents_stride = agents_verts.strides[0]
    
        # get the position from vertex shader
        # stride offset
        offset = ctypes.c_void_p(0)
        init_pos = glGetAttribLocation(shader, 'init_pos')
        glVertexAttribPointer(init_pos, 2, GL_FLOAT,
                              GL_FALSE, agents_stride, offset)
        glEnableVertexAttribArray(init_pos)
    
        glUseProgram(shader)
    
        glClearColor(1.0, 1.0, 1.0, 1.0)
    
    """
    Prepare directories to store:
    - source configuration files,
    - intermediate results in the form of meeting tables
    - output statistical reports
    """
    if not os.path.exists("output"):
        os.makedirs("output")
    
    paths = {
        "configs"     : os.path.join("output", "configs"),
        "meet_tables" : os.path.join("output", "meetings_tables"),
        "agents"      : os.path.join("output", "agents"),
        "out_stats"   : os.path.join("output", "stat_results"),
        }
    
    for path in paths.values():
        if not os.path.exists(path):
             os.makedirs(path)
    
    if args.config:
        # in this usage scenario all identifiers are set manually
        # (unique tags are generated in meta-loop that launches these scripts)
        tag = args.name
    else:
        # in this usage scenario timestamp is autimatically appended to 
        # distinguish between consequtive manual program launches
        timestamp = datetime.now().strftime("%H:%M:%S")
        tag = args.name +'_'+  timestamp
    
    # store the config file for the reference
    dump_config_path = os.path.join(
        paths["configs"], "config_"+ tag +".yaml")
    
    shutil.copy(config_path, dump_config_path)
    
    # store agents for the further move speed / infection spread correlating
    agents_souls_path = os.path.join(
        paths["agents"], "spatial_agents_"+ tag +".bin")
    
    with open(agents_souls_path, 'wb') as file:
        pickle.dump(agents, file)
    
    # create the file with agent meetings
    # originally a .bin file, is later compressed to the .bin.tar.bz2 format
    meets_table_path = os.path.join(
        paths["meet_tables"], "meet_table_"+ tag +".bin")
    
    with open(meets_table_path, 'wb') as file:
        
        # run until the end of the set simulation period
        
        T  = config["simulationDuration"] * 24*60*60
        dt = config[ "minSimulationStep"]
        
        eval_times = np.arange(0, T, dt)
        
        for eval_time in tqdm(eval_times):
            
            """
            Transition agents between service and leave
            """
            entities = (teams, boxes, agents)
            
            # some agents prefer to stay on the base during holidays
            stay_chance = config.get('dontGoOffDuty', 0.0)
            
            rotate_teams(entities, stay_chance, eval_time, dt)
            
            """
            Transition agents to "Sotilaskoti" cafeteria and back
            """
            if config["sotilaskoti"]["allow"]:
                
                queue_sotilaskoti(entities, q, eval_time, dt, config)
            
            """
            Update agent positions (along one time step)
            """
            increment_agent_positions(agents)
            
            """
            Refresh the sorting of agents after the positions update
            """
            x_sort(agents_x_sorted)
            
            """
            Register new meetings between agents and export them to file
            """
            meets_curr = detect_meetings(agents_x_sorted, eval_time,
                                         config, visualize)
            
            # each key is a meeting link between two agents 
            # in the form {agent1_idx, agent2_idx}
            links_curr = set( meets_curr.keys() )
            links_prev = set( meets_prev.keys() )
            
            meets_new = dict()
            
            for link in links_curr:
                
                if link not in links_prev:
                    
                    meets_new[link] = meets_curr[link]
            
            if meets_new:
                
                timeline = {"timestamp" : eval_time,
                             "meetings" : meets_new}
                
                pickle.dump(timeline, file)
            
            meets_prev = meets_curr
            
            """
            Plot canvas if not specified otherwise (--no-visual option)
            """
            if visualize:
                
                if glfw.window_should_close(window):
                    break
                
                time_zero = time.time()
                
                glClear(GL_COLOR_BUFFER_BIT)
                
                """
                Indicate current day in window title
                """
                day_n = eval_time // (24*60*60) + 1
                
                dayly_title = config["window"]["title"] +", day: "+ str(day_n)
                
                glfw.set_window_title(window, dayly_title)

                """
                Draw borders (i.e. boxes, i.e. fences) - 1 px black outlines
                """
                glBindBuffer(GL_ARRAY_BUFFER, VBO[0])
                glVertexAttribPointer(init_pos, 2, GL_FLOAT,
                                      GL_FALSE, fences_stride, offset)
                glEnableVertexAttribArray(init_pos)
                
                transformLoc = glGetUniformLocation(shader, "dyn_pos")
                glUniform2f(transformLoc, 0.0, 0.0)
                
                transformLoc = glGetUniformLocation(shader, "dyn_color")
                glUniform4f(transformLoc, 0.0, 0.0, 0.0, 0.0)
        
                glDrawArrays(GL_TRIANGLES, 0, len(fences_verts))
                
                """
                Draw agents (i.e. conscripts and civilians)
                """
                glBindBuffer(GL_ARRAY_BUFFER, VBO[1])
                glVertexAttribPointer(init_pos, 2, GL_FLOAT,
                                      GL_FALSE, agents_stride, offset)
                glEnableVertexAttribArray(init_pos)
                
                for i, agent in enumerate(agents):
                    
                    poly_prop = np.zeros(1, [( "pos" , np.float32, 2),
                                             ("color", np.float32, 4)])
                    
                    # absolute to relative coordinates, meters -> fractions
                    x = (agent.x/canvas[ "width"]*2 - 1)*0.99
                    y = (agent.y/canvas["height"]*2 - 1)*0.99
                    
                    poly_prop["pos"] = (x, y)
                    
                    transformLoc = glGetUniformLocation(shader, "dyn_pos")
                    glUniform2f(transformLoc, *poly_prop["pos"].T)
                    
                    """
                    Agent triangle marker filling
                    """
                    poly_prop["color"] = agent.color
                    
                    transformLoc = glGetUniformLocation(shader, "dyn_color")
                    glUniform4f(transformLoc, *poly_prop["color"].T)
    
                    if agent.conscripted:
                        glDrawArrays(GL_TRIANGLES, 3, 6)
                    else:
                        glDrawArrays(GL_TRIANGLES, 0, 3)
                    
                    """
                    Marker outline
                    """
                    transformLoc = glGetUniformLocation(shader, "dyn_color")
                    glUniform4f(transformLoc, 0.0, 0.0, 0.0, 1.0) # black
                    
                    if agent.conscripted:
                        glDrawArrays(GL_LINE_LOOP, 3, 6)
                    else:
                        glDrawArrays(GL_LINE_LOOP, 0, 3)
                
                glfw.swap_buffers(window)
                
                # FPS limited to 60
                while(time.time() - time_zero < 1/60):
                    time.sleep(0.001)
                glfw.poll_events()
    
    if visualize:
        glfw.terminate()
    
    """
    Compress output file to save space 
    """
    compressed_path = os.path.join(
        paths["meet_tables"], "meet_table_"+ tag +".bin.tar.bz2")
    
    with tarfile.open(compressed_path, "w:bz2") as tar:
        tar.add(meets_table_path)
    
    # in case compressing went successful, remove the source file
    if os.path.exists(compressed_path):
        os.remove(meets_table_path)
        

if __name__ == "__main__":
    main(visualize)




