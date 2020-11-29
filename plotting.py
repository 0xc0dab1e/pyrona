#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This file contains functions relevant only to the visualization.
"""

import numpy as np
import OpenGL.GL.shaders
from OpenGL.GL import GL_VERTEX_SHADER, GL_FRAGMENT_SHADER

def compile_shader():
    
    VERTEX_SHADER = """
        
        attribute in vec2 init_pos;
        uniform vec2 dyn_pos;
        
        void main() {
          gl_Position.xy = init_pos + dyn_pos;
        }
    """

    FRAGMENT_SHADER = """
        
        uniform vec4 dyn_color;
        
        void main() {
          gl_FragColor = dyn_color;
        }

    """

    shader = OpenGL.GL.shaders.compileProgram(
        OpenGL.GL.shaders.compileShader(   VERTEX_SHADER,
                                        GL_VERTEX_SHADER),
        OpenGL.GL.shaders.compileShader(   FRAGMENT_SHADER,
                                        GL_FRAGMENT_SHADER))
    return shader

def generate_map(boxes, config):
    canvas = {"top"    : 0,
              "bottom" : 0,
              "right"  : 0,
              "left"   : 0}
    for box in boxes.values():
        if box.top    > canvas[   "top"]:
            canvas[   "top"] = box.top
        if box.bottom < canvas["bottom"]:
            canvas["bottom"] = box.bottom
        if box.right  > canvas[ "right"]:
            canvas[ "right"] = box.right
        if box.left   < canvas[  "left"]:
            canvas[  "left"] = box.left
    
    canvas[ "width"] = canvas["right"] - canvas["left"]
    canvas["height"] = canvas["top"] - canvas["bottom"]
    
    # 24 verticies for plotting each box (4*2 tringles, 3 vert. per triangle) 
    fences_verts = np.zeros(24*len(boxes), [("poles", np.float32, 2)])
    
    # get relative position for each vertex and load in corresponding
    for i, box in enumerate(boxes.values()):              # memory placeholder
        # relative coords (openGL uses relative coordinates)
        r = box.right  / canvas["width"] # between  0..1
        r = 2*r - 1                      # between -1..1
        l = box.left   / canvas["width"]
        l = 2*l - 1
        t = box.top    / canvas["height"]
        t = 2*t - 1
        b = box.bottom / canvas["height"]
        b = 2*b - 1
        # leave a bit of blank space at the plot border
        r, l, t, b = 0.99*r, 0.99*l, 0.99*t, 0.99*b
    
        tx = 1/(config["window"][ "width"]/2) # box border thickness: 
        ty = 1/(config["window"]["height"]/2) # 1 px
    
        fences_verts["poles"][i*24 : (i+1)*24] = (
            # left border
            (l, t), (l+tx, b), (l+tx, t),
            (l, t), (l+tx, b), (l,    b),
            # top border
            (l, t-ty), (r, t), (l,    t),
            (l, t-ty), (r, t), (r, t-ty),
            # right border
            (r-tx, t), (r, b), (r,    t),
            (r-tx, t), (r, b), (r-tx, b),
            # bottom border
            (l, b), (r, b+ty), (l, b+ty),
            (l, b), (r, b+ty), (r,    b),
        )
        
    return fences_verts, canvas


def generate_agents_verticies(config):
    
    agents_verts = np.zeros(3*3, [("verticies", np.float32, 2)])
    
    # templates for agent marker shapes
    marker_size  = config["markerSize"]
    w = config["window"][ "width"]
    h = config["window"]["height"]
    aspect_ratio = w/h
    
    m_w = marker_size / aspect_ratio
    m_h = marker_size * np.sqrt(3)/2
    
    # triangle verticies
    civ_templ = ((   0, m_h), 
                 (-m_w,-m_h), 
                 ( m_w,-m_h))
    
    # upside-down triangle verticies
    mil_templ = ((-m_w, m_h),
                 (   0,-m_h),
                 ( m_w, m_h))
    
    agents_verts["verticies"][0:3] = civ_templ
    agents_verts["verticies"][3:6] = mil_templ
    # There is some bug in OpenGL library that prevents proper outline drawing
    # unless the following line is included (probably the bug has to do with 
    # offsets matching between numpy buffer and GL values parsing).
    agents_verts["verticies"][6:9] = mil_templ
    
    return agents_verts
