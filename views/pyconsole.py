# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 
# pyconsole - a simple console for pygame based applications 
#
# Copyright (C) 2006  John Schanck
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #


import pygame, os, sys 
from pygame.locals import *

import textwrap # Used for proper word wrapping
from string import ascii_letters
from code import InteractiveConsole        # Gives us access to the python interpreter

__version__ = "0.7"

WIDTH=0
HEIGHT=1

OUT = 0
IN = 1
ERR = 2

PYTHON = 2 

path = os.path.abspath(os.path.dirname(__file__))
#font_path = os.path.join(path, "fonts")

class Writable(list):
    line_pointer = -1
    def write(self, line):
        self.append(str(line))
    def reset(self):
        self.__init__()
    """
    def readline(self, size=-1):
        # Python's interactive help likes to try and call this, which causes the program to crash
        # I see no reason to implement interactive help.
        raise NotImplementedError
    """
    def readline(self):
        raise

class Console:
    def __init__(self, screen, rect, functions={}, key_calls={}, vars={}, syntax={}):
        if not pygame.display.get_init():
            raise pygame.error, "Display not initialized. Initialize the display before creating a Console"
        
        if not pygame.font.get_init():
            pygame.font.init()

        self.parent_screen = screen
        self.rect = pygame.Rect(rect)
        self.size = self.rect.size
        
        self.user_vars = vars        
        self.user_syntax = syntax
        self.user_namespace = {}
        
        self.variables = {\
                "bg_alpha":int,\
                "bg_color": list,\
                "txt_color_i": list,\
                "txt_color_o": list,\
                "ps1": str,\
                "ps2": str,\
                "ps3": str,\
                "active": bool,\
                "repeat_rate": list,\
                "preserve_events":bool,\
                "python_mode":bool,\
                "motd":list
                }
        
        self.init_default_cfg()
        
        
        pygame.key.set_repeat(*self.repeat_rate)
            
        self.bg_layer = pygame.Surface(self.size)
        self.bg_layer.set_alpha(self.bg_alpha)
        
        self.txt_layer = pygame.Surface(self.size)
        self.txt_layer.set_colorkey(self.bg_color)
        
        self.font = pygame.font.Font('views/DroidSansMono.ttf', 12)
        
        self.font_height = self.font.get_linesize()
        self.max_lines = (self.size[HEIGHT] / self.font_height) - 1
        
        self.max_chars = (self.size[WIDTH]/(self.font.size(ascii_letters)[WIDTH]/len(ascii_letters))) - 1
        self.txt_wrapper = textwrap.TextWrapper()
        
        self.c_out = self.motd
        self.c_hist = [""]
        self.c_hist_pos = 0
        self.c_in = ""
        self.c_pos = 0
        self.c_draw_pos = 0
        self.c_scroll = 0
        
        self.changed = True
        
        self.func_calls = {}
        self.key_calls = {}
        
        self.add_func_calls({"echo":self.output, "clear": self.clear, "help":self.help})
        self.add_func_calls(functions)
        
        self.add_key_calls({"l":self.clear, "c":self.clear_input, "w":self.set_active})
        self.add_key_calls(key_calls)
        self.set_interpreter()

    ##################
    #-Initialization-#
    def init_default_cfg(self):
        self.bg_alpha = 175
        self.bg_color = [0x0,0x44,0xAA]
        self.txt_color_i = [0xFF,0xFF,0xFF]
        self.txt_color_o = [0xEE,0xEE,0xEE]
        self.ps1 = "] "
        self.ps2 = ">>> "
        self.ps3 = "... "
        self.active = True
        self.repeat_rate = [500,30]
        self.python_mode = False
        self.preserve_events = False
        self.motd = ["Press Ctrl_w to hide the console","One day this will have more to say"]

    def add_func_calls(self, functions):
        '''\
        Add functions to the func_calls dictionary.
        Arguments:
           functions -- dictionary of functions to add.
        '''
        if isinstance(functions,dict):
            self.func_calls.update(functions)
            self.user_namespace.update(self.func_calls)
    
    def add_key_calls(self, functions):
        '''\
        Add functions to the key_calls dictionary.
        Arguments:
           functions -- dictionary of key_calls to add.
        '''
        if isinstance(functions,dict):
            self.key_calls.update(functions)
    
    def output(self, text):
        '''\
        Prepare text to be displayed
        Arguments:
           text -- Text to be displayed
        '''
        if not str(text):
            return;
        
        try:
            self.changed = True
            if not isinstance(text,str):
                text = str(text)
            text = text.expandtabs()
            text = text.splitlines()
            self.txt_wrapper.width = self.max_chars
            for line in text:
                for w in self.txt_wrapper.wrap(line):
                    self.c_out.append(w)
        except:
            raise
    
    def set_active(self,b=None):
        '''\
        Activate or Deactivate the console
        Arguments:
           b -- Optional boolean argument, True=Activate False=Deactivate
        '''
        if not b:
            self.active = not self.active
        else:
            self.active = b
        
    def format_input_line(self):
        '''\
        Format input line to be displayed
        '''
        # The \v here is sort of a hack, it's just a character that isn't recognized by the font engine
        text = self.c_in[:self.c_pos] + "\v" + self.c_in[self.c_pos+1:] 
        n_max = self.max_chars - len(self.c_ps)
        vis_range = self.c_draw_pos, self.c_draw_pos + n_max
        return self.c_ps + text[vis_range[0]:vis_range[1]]
    
    def draw(self):
        '''\
        Draw the console to the parent screen
        '''
        if not self.active:
            return;
        
        if self.changed:
            self.changed = False
            # Draw Output
            self.txt_layer.fill(self.bg_color)
            lines = self.c_out[-(self.max_lines+self.c_scroll):len(self.c_out)-self.c_scroll]
            y_pos = self.size[HEIGHT]-(self.font_height*(len(lines)+1))
            
            for line in lines:
                tmp_surf = self.font.render(line, True, self.txt_color_o)
                self.txt_layer.blit(tmp_surf, (1, y_pos, 0, 0))
                y_pos += self.font_height
            # Draw Input
            tmp_surf = self.font.render(self.format_input_line(), True, self.txt_color_i)
            self.txt_layer.blit(tmp_surf, (1,self.size[HEIGHT]-self.font_height,0,0))
            # Clear background and blit text to it
            self.bg_layer.fill(self.bg_color)
            self.bg_layer.blit(self.txt_layer,(0,0,0,0))
        
        # Draw console to parent screen
        pygame.draw.rect(self.parent_screen, self.txt_color_i, (self.rect.x-1, self.rect.y-1, self.size[WIDTH]+2, self.size[HEIGHT]+2), 1)
        self.parent_screen.blit(self.bg_layer,self.rect)

    #######################################################################
    # Functions to communicate with the console and the python interpreter#
    def set_interpreter(self):
        #self.output("Entering Python mode")
        self.python_interpreter = InteractiveConsole()
        self.tmp_fds = []
        self.py_fds = [Writable() for i in range(3)]
        self.c_ps = self.ps2
    
    def catch_output(self):
        if not self.tmp_fds:
            self.tmp_fds = [sys.stdout, sys.stdin, sys.stderr]
            sys.stdout, sys.stdin, sys.stderr = self.py_fds
    
    def release_output(self):
        if self.tmp_fds:
            sys.stdout, sys.stdin, sys.stderr = self.tmp_fds
            self.tmp_fds = []
            [fd.reset() for fd in self.py_fds]

    def submit_input(self, text):
        '''\
        Submit input
           1) Move input to output
           2) Evaluate input
           3) Clear input line
        '''
    
        self.clear_input()
        self.output(self.c_ps + text)
        self.c_scroll = 0
        self.send_python(text)

    def send_python(self, text):
        '''\
        Sends input the the python interpreter in effect giving the user the ability to do anything python can.
        '''
        self.c_ps = self.ps2
        self.catch_output()
        if text:
            self.add_to_history(text)
            r = self.python_interpreter.push(text)
            if r:
                self.c_ps = self.ps3
        else:
            code = "".join(self.py_fds[OUT])
            self.python_interpreter.push("\n")
            self.python_interpreter.runsource(code)
        for i in self.py_fds[OUT]+self.py_fds[ERR]:
            self.output(i)
        self.release_output()
    
    
    ####################################################
    #-Functions for sharing variables with the console-#
    def setvar(self, name, value):
        '''\
        Sets the value of a variable
        '''
        if self.user_vars.has_key(name) or not self.__dict__.has_key(name):
            self.user_vars.update({name:value})
            self.user_namespace.update(self.user_vars)
        elif self.__dict__.has_key(name):
            self.__dict__.update({name:value})
        
    def getvar(self, name):
        '''\
        Gets the value of a variable, this is useful for people that want to access console variables from within their game
        '''
        if self.user_vars.has_key(name) or not self.__dict__.has_key(name):
            return self.user_vars[name]
        elif self.__dict__.has_key(name):
            return self.__dict__[name]
    
    def setvars(self, vars):
        try:
            self.user_vars.update(vars)
            self.user_namespace.update(self.user_vars)
        except TypeError:
            self.output("setvars requires a dictionary")
    
    def getvars(self, opt_dict=None):
        if opt_dict:
            opt_dict.update(self.user_vars)
        else:
            return self.user_vars
    
    def add_to_history(self, text):
        '''\
        Add specified text to the history
        '''
        self.c_hist.insert(-1,text)
        self.c_hist_pos = len(self.c_hist)-1
            
    def clear_input(self):
        '''\
        Clear input line and reset cursor position
        '''
        self.c_in = ""
        self.c_pos = 0
        self.c_draw_pos = 0
    
    def set_pos(self, newpos):
        '''\
        Moves cursor safely
        '''
        self.c_pos = newpos
        if (self.c_pos - self.c_draw_pos) >= (self.max_chars - len(self.c_ps)):
            self.c_draw_pos = max(0, self.c_pos - (self.max_chars - len(self.c_ps)))
        elif self.c_draw_pos > self.c_pos:
            self.c_draw_pos = self.c_pos - (self.max_chars/2)
            if self.c_draw_pos < 0:
                self.c_draw_pos = 0
                self.c_pos = 0
    
    def str_insert(self, text, strn):
        '''\
        Insert characters at the current cursor position
        '''
        foo = text[:self.c_pos] + strn + text[self.c_pos:]
        self.set_pos(self.c_pos + len(strn))
        return foo
        
    def process_input(self):
        '''\
        Loop through pygame events and evaluate them
        '''
        if not self.active:
            return;
        
        if self.preserve_events:
            eventlist = pygame.event.get(KEYDOWN)
        else:
            eventlist = pygame.event.get()
        
        for event in eventlist:
            if event.type == KEYDOWN:
                self.changed = True
                ## Special Character Manipulation
                if event.key == K_TAB:
                    self.c_in = self.str_insert(self.c_in, "    ")
                elif event.key == K_BACKSPACE:
                    if self.c_pos > 0:
                        self.c_in = self.c_in[:self.c_pos-1] + self.c_in[self.c_pos:]
                        self.set_pos(self.c_pos-1)
                elif event.key == K_DELETE:
                    if self.c_pos < len(self.c_in):
                        self.c_in = self.c_in[:self.c_pos] + self.c_in[self.c_pos+1:]
                elif event.key == K_RETURN or event.key == 271:
                    self.submit_input(self.c_in)
                ## Changing Cursor Position
                elif event.key == K_LEFT:
                    if self.c_pos > 0:
                        self.set_pos(self.c_pos-1)
                elif event.key == K_RIGHT:
                    if self.c_pos < len(self.c_in):
                        self.set_pos(self.c_pos+1)
                elif event.key == K_HOME:
                    self.set_pos(0)
                elif event.key == K_END:
                    self.set_pos(len(self.c_in))
                ## History Navigation
                elif event.key == K_UP:
                    if len(self.c_out):
                        if self.c_hist_pos > 0:
                            self.c_hist_pos -= 1
                        self.c_in = self.c_hist[self.c_hist_pos]
                        self.set_pos(len(self.c_in))
                elif event.key == K_DOWN:
                    if len(self.c_out):
                        if self.c_hist_pos < len(self.c_hist)-1:
                            self.c_hist_pos += 1
                        self.c_in = self.c_hist[self.c_hist_pos]
                        self.set_pos(len(self.c_in))
                ## Scrolling
                elif event.key == K_PAGEUP:
                    if self.c_scroll < len(self.c_out)-1:
                        self.c_scroll += 1
                elif event.key == K_PAGEDOWN:
                    if self.c_scroll > 0:
                        self.c_scroll -= 1
                ## Normal character printing
                elif event.key >= 32:
                    mods = pygame.key.get_mods()
                    if mods & KMOD_CTRL:
                        if event.key in range(256) and chr(event.key) in self.key_calls:
                            self.key_calls[chr(event.key)]()
                    else:
                        char = str(event.unicode)
                        self.c_in = self.str_insert(self.c_in, char)

    ##########################
    #-Some Builtin functions-#
    def clear(self):
        '''\
        Clear the Screen
        '''
        self.c_out = ["[Screen Cleared]"]
        self.c_scroll = 0
    
    def help(self, *args):
        '''\
        Output information about functions
        Arguments:
           args -- arbitrary argument list of function names
             |- No Args - A list of available functions will be displayed
             |- One or more Args - Docstring of each function will be displayed
        '''
        if args:
            items = [(i,self.func_calls[i]) for i in args if i  in self.func_calls]
            for i,v in items:
                out = i + ": Takes %d arguments. " % (v.func_code.co_argcount - (v.func_code.co_varnames[0] is "self"))
                doc = v.func_doc
                if doc:
                    out += textwrap.dedent(doc)
                tmp_indent = self.txt_wrapper.subsequent_indent
                self.txt_wrapper.subsequent_indent = " "*(len(i)+2)
                self.output(out)
                self.txt_wrapper.subsequent_indent = tmp_indent    
        else:
            out = "Available commands: " + str(self.func_calls.keys()).strip("[]")
            self.output(out)
            self.output(r'Type "help command-name" for more information on that command')
