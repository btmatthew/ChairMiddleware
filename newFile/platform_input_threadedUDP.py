"""
  platform_input_threadedUDP.py

  Receives UDP messages on port 10009
  Move messages are: "xyzrpy,x,y,z,r,p,y,\n"
  xyz are translations in mm, rpy are rotations in radians
  set self.angles_as_radians = False for angle in degrees
  set self.is_normalized to True for range of all fields between -1 to +1
  or you can send a config message to change default units:
      "config,units=normalized"  <- sets self.is_normalized to True
      "config,units=mm_radians" <- sets angles as radians, self.is_normalized to False
      "config,units=mm_degrees" <- sets angles as degrees, self.is_normalized to False
  
  Command messages are:
  "command,enable,\n"   : activate the chair for movement
  "command,disable,\n"  : disable movement and park the chair
  "command,exit,\n"     : shut down the application
"""

import sys
import socket
from math import radians, degrees
import threading
import time
from Queue import Queue
import Tkinter as tk
import traceback


class InputInterface(object):
    USE_GUI = True  # set True if using tkInter
    print "USE_GUI", USE_GUI

    def __init__(self):
        #  default input mode, can be changed using config message
        self.is_normalized = True  #  set True if input range is -1 to +1
        self.angles_as_radians = False # angles in degrees if False, only used if not normalized
        if self.is_normalized:
            print 'Platform Input is UDP with normalized parameters as default'
        else:
            if  self.angles_as_radians:
                print 'Platform Input is UDP with realworld values as mm and radians'
            else:
                print 'Platform Input is UDP with realworld values as mm and degrees'

        self.HOST = "localhost"
        self.PORT = 10009
        
        self.levels = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        #self.max_values = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.max_values = [130, 300, 325, 90, 25, 115] 
        self.start_time = 0
 
        self.nbr_messages = 0
              
        self.rootTitle = "UDP Platform Interface"
        self.xyzrpyQ = Queue()
        self.cmdQ = Queue()
        t = threading.Thread(target=self.listener_thread, args= (self.HOST, self.PORT))
        t.daemon = True
        t.start()

    def init_gui(self, master):
        self.master = master
        frame = tk.Frame(master)
        frame.pack()
        self.label0 = tk.Label(frame, text="Accepting UDP messages on port " + str(self.PORT))
        self.label0.pack(fill=tk.X, pady=10)

        self.units_label = tk.Label(frame, text="Units")
        self.units_label.pack(side="top", pady=10)
        self.display_units()

        self.msg_label = tk.Label(frame, text="")
        self.msg_label.pack(side="top", pady=10)

        self.cmd_label = tk.Label(frame, text="")
        self.cmd_label.pack(side="top", pady=10)

        self.deactivation_button = tk.Button(master, command=self._disable_pressed)
        self.deactivation_button.pack(side="bottom")        
        self.activation_button = tk.Button(master, underline=0, command=self._enable_pressed)
        self.activation_button.pack(side="bottom")
        self.set_activation_buttons(False)

    def _enable_pressed(self):
        if self.cmd_func:
            self.cmd_func("enable")
            self.set_activation_buttons(True)

    def _disable_pressed(self):
        if self.cmd_func:
            self.cmd_func("disable")
            self.set_activation_buttons(False)

    def set_activation_buttons(self, isEnabled):  # callback from Client
        if isEnabled:
            self.activation_button.config(text="Activated ", width=12,  relief=tk.SUNKEN)
            self.deactivation_button.config(text="Deactivate", width=12, relief=tk.RAISED)
        else:
            self.activation_button.config(text="Activate ", width=12, relief=tk.RAISED)
            self.deactivation_button.config(text="Deactivated", width=12, relief=tk.SUNKEN)

    def chair_status_changed(self, chair_status):
        print(chair_status[0])
    
    def display_units(self):
        if self.is_normalized:
            txt = "Expecting normalized values between -1 and +1"
        else:
            if self.angles_as_radians:
                txt = "Expecting x,y,z values in mm, angles as radians"
            else:
                txt = "Expecting x,y,z values in mm, angles as degrees"
        self.units_label.config(text=txt)

    def intensity_status_changed(self, intensity):
        print( "intensity " + intensity[0])

    def begin(self, cmd_func, move_func, limits):
        self.cmd_func = cmd_func
        self.move_func = move_func

    def fin(self):
        # client exit code goes here
        pass
        
    def get_current_pos(self):
        return self.levels

    def intensity_status_changed(self, status):
        pass

    def service(self):
        # move request returns translations as mm and angles as radians
        msg = None
        while self.cmdQ.qsize() > 0:
            cmd = self.cmdQ.get()
            self.process_command_msg(cmd)
        # this logic assumes that incoming data rate is much higher then service rate
        if self.xyzrpyQ.qsize() > 1: # need at least two messges
            msg0 = []
            msg1 = []
            # throw away all but most recent two movement messages
            while self.xyzrpyQ.qsize() > 1:
                msg0 = self.xyzrpyQ.get()  
            msg1 = self.xyzrpyQ.get() 
            try:
                data0 = self.extract_data(msg0[1])
                data1 = self.extract_data(msg1[1])
                delta = msg1[0] - msg0[0] 
                if data0 != None and data1 != None:
                    # print "incoming msg:", self.delta,  data1
                    self.process_telemetry_msg(data0, data1, delta)
            except:
                #  print error if input not a string or cannot be converted into valid request
                e = sys.exc_info()[0]
                s = traceback.format_exc()
                print e, s

    def extract_data(self, source):
        # this returns extacted data as list of floats(source also modified)
        if source is not None:
            source = source.rstrip()
            fields = source.split(",")
            if fields[0] == "xyzrpy":
                data = [float(f) for f in list(fields[1:7])]
                # todo if needed - code to handle gimbal lock?
                return data
        return None
        
    def process_xyzrpy_msg(self, field_list):
        try:
            r = [float(f) for f in field_list[1:7]]
            if self.is_normalized == False:
                if self.angles_as_radians == False:
                    # convert to radians if received as degrees 
                    r[3] = radians(r[3])
                    r[4] = radians(r[4])
                    r[5] = radians(r[5])
            #print r
            if self.move_func:
                #print r
                self.move_func(r)
                self.levels = r
        except:  # if not a list of floats, process as command
            e = sys.exc_info()[0]
            print "UDP svc err", e
    
    def process_telemetry(self, data0, data1, delta):
        print "todo process telemetry"
    
    def process_command_msg(self, msg):
        if msg is not None:
            msg = msg.rstrip()
            fields = msg.split(",")
            if fields[0] == "command":
                print "command is {%s}:" % (fields[1])
                self.cmd_label.config(text="Most recent command: " + fields[1])
                if self.cmd_func:
                    self.cmd_func(fields[1])
            elif fields[0] == "config":
                print "config mesage is {%s}:" % (fields[1])
                self.process_config_msg(fields[1])
            
    def process_config_msg(self, field_list):
        parm = field_list[1].split("=")
        if parm[0] == "units":
            #  to change units, send one of: "config,units=normalized", "config,units=mm_radians", or "config,units=mm_degrees"
            if parm[1] ==  "normalized":
                self.is_normalized = True
                print "client config set to normalized data"
            elif parm[1] == "mm_degrees":
                self.is_normalized = False
                self.angles_as_radians = False # angles sent as degrees
                print "client config set to realworld values as mm and degrees"
            elif parm[1] == "mm_radians":
                self.is_normalized = False
                self.angles_as_radians = True # angles sent as radians
                print "client config set to realworld values as mm and radians"
            else:
                print "unrecognized client config message: " + field_list[1]
            self.display_units()

    def listener_thread(self, HOST, PORT):
        try:
            self.MAX_MSG_LEN = 1024
            client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client.bind((HOST, PORT))
            print "opening socket on", PORT           
        except:
            e = sys.exc_info()[0]
            s = traceback.format_exc()
            print "thread init err", e, s
        while True:
            try:
                msg = client.recv(self.MAX_MSG_LEN)
                if msg is not None:
                    if msg.find("xyzrpy") == 0:
                        now = time.time()
                        if self.nbr_messages > 0: # ignore first message
                            self.xyzrpyQ.put([now,msg])
                        self.nbr_messages += 1
                    elif msg.find("command") == 0:
                        self.cmdQ.put(msg)
                    elif msg.find("config") == 0:
                        self.cmdQ.put(msg) # config messages go onto command queue
               
            except:
                e = sys.exc_info()[0]
                s = traceback.format_exc()
                print "listener err", e, s

