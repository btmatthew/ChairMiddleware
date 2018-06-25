"""
  platform_input_threadedUDP.py

  Receives UDP messages on port 10009
  Move messages are: "xyzrpy,x,y,z,r,p,y,\n"
  xyz are translations in mm, rpy are rotations in radians
  however if self.is_normalized is set True, range for all fields is -1 to +1
  
  Command messages are:
  "command,enable,\n"   : activate the chair for movement
  "command,disable,\n"  : disable movement and park the chair
  "command,exit,\n"     : shut down the application
"""

import sys
import socket
from math import radians, degrees
import threading
from Queue import Queue
import Tkinter as tk
import traceback

import ctypes
from ctypes import wintypes
import time

import pyautogui as pyautogui

from serial_remote import SerialRemote
import keys


import carseour
import time
import cmath
game = carseour.live()


class InputInterface(object):
    USE_GUI = True  # set True if using tkInter
    print "USE_GUI", USE_GUI

    def __init__(self):
        #  set True if input range is -1 to +1
        self.is_normalized = True
        self.expect_degrees = False  # convert to radians if True
        if self.is_normalized:
            print 'Platform Input is UDP with normalized parameters'
        else:
            print 'Platform Input is UDP with realworld parameters'
        self.levels = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.maximum = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.floatArray = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.rootTitle = "UDP Platform Interface"
        self.inQ = Queue()
        t = threading.Thread(target=self.listener_thread, args=(self.inQ,))
        t.daemon = True
        t.start()
        actions = {'detected remote': self.detected_remote, 'activate': self.activate,
                   'deactivate': self.deactivate, 'pause': self.pause, 'dispatch': self.dispatch,
                   'reset': self.reset, 'emergency_stop': self.emergency_stop, 'intensity': self.set_intensity}
        self.RemoteControl = SerialRemote(actions)

    def init_gui(self, master):
        self.master = master
        frame = tk.Frame(master)
        frame.pack()
        # self.label0 = tk.Label(frame, text="Accepting UDP messages on port " + str(self.PORT))
        # self.label0.pack(fill=tk.X, pady=10)

        """ 
        self.units_label = tk.Label(frame, text=t)
        self.units_label.pack(side="top", pady=10)
        """

        self.msg_label = tk.Label(frame, text="")
        self.msg_label.pack(side="top", pady=10)

        self.cmd_label = tk.Label(frame, text="")
        self.cmd_label.pack(side="top", pady=10)

    def chair_status_changed(self, chair_status):
        print(chair_status[0])

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
        self.RemoteControl.service()
        # move request returns translations as mm and angles as radians
        msg = None
        # throw away all but most recent message
        while not self.inQ.empty():
            msg = self.inQ.get()
        try:
            if msg is not None:
                msg = msg.rstrip()
                # print msg
                fields = msg.split(",")
                field_list = list(fields)
                if field_list[0] == "xyzrpy":
                    # self.msg_label.config(text="got: " + msg)
                    try:
                        r = [float(f) for f in field_list[1:7]]
                        # remove next 3 lines if angles passed as radians 
                        if self.move_func:
                            # print r
                            self.move_func(r)
                            self.levels = r
                    except:  # if not a list of floats, process as command
                        e = sys.exc_info()[0]
                        print "UDP svc err", e
                elif field_list[0] == "command":
                    print "command is {%s}:" % (field_list[1])
                    self.cmd_label.config(text="Most recent command: " + field_list[1])
                    if self.cmd_func:
                        self.cmd_func(field_list[1])
        except:
            #  print error if input not a string or cannot be converted into valid request
            e = sys.exc_info()[0]
            s = traceback.format_exc()
            print e, s

    def detected_remote(self, info):
        print info

    def activate(self):
        self.cmd_func("enable")
        print "activate"

    def deactivate(self):
        self.pause()
        self.cmd_func("disable")
        # directx scan codes http://www.gamespp.com/directx/directInputKeyboardScanCodes.html
        keys.PressKey(0x01)
        time.sleep(0.05)  # Keep the sleep at 50ms to prevent double click of esc button
        keys.ReleaseKey(0x01)
        print "deactivate"

    def pause(self):
        # directx scan codes http://www.gamespp.com/directx/directInputKeyboardScanCodes.html
        keys.PressKey(0x01)
        time.sleep(0.05)  # Keep the sleep at 50ms to prevent double click of esc button
        keys.ReleaseKey(0x01)
        print "pause"

    def dispatch(self):
        # directx scan codes http://www.gamespp.com/directx/directInputKeyboardScanCodes.html
        keys.PressKey(0x1C)
        time.sleep(0.05)  # Keep the sleep at 50ms to prevent double click of esc button
        keys.ReleaseKey(0x1C)
        print "dispatch"

    def reset(self):
        # directx scan codes http://www.gamespp.com/directx/directInputKeyboardScanCodes.html
        keys.PressKey(0xC7)
        time.sleep(0.05)  # Keep the sleep at 50ms to prevent double click of esc button
        keys.ReleaseKey(0xC7)
        print "reset"

    def emergency_stop(self):
        self.deactivate()
        self.pause()
        print "stop"

    def set_intensity(self, intensity):
        self.cmd_func(intensity)
        print "intensity ", intensity

    def normalization(self, val, max_val):
        if max_val <= 1 or val == 0.0:
            return val
        sign = 1.0
        if val < 0:
            val = -val
            sign = -1
        if val > max_val:
            val = max_val
        return cmath.log10(val + 1) / cmath.log10(max_val) * sign

    def listener_thread(self, inQ):
        try:
            self.inQ = inQ
        except:
            e = sys.exc_info()[0]
            s = traceback.format_exc()
            print "thread init err", e, s
        while True:
            try:
                for x in range(6):
                    if x == 0:
                        self.floatArray[x] = game.mLocalVelocity[1]
                    elif x == 1:
                        self.floatArray[x] = game.mLocalVelocity[0]
                    elif x == 2:
                        self.floatArray[x] = game.mLocalVelocity[2]
                    elif x == 3:
                        self.floatArray[x] = game.mAngularVelocity[1]
                    elif x == 4:
                        self.floatArray[x] = game.mAngularVelocity[0]
                    elif x == 5:
                        self.floatArray[x] = game.mAngularVelocity[2]

                    if self.floatArray[x] > self.maximum[x]:
                        self.maximum[x] = self.floatArray[x]

                    self.floatArray[x] = self.normalization(self.floatArray[x], self.maximum[x])


 #               print(str(self.floatArray[1]) + " " + str(self.floatArray[0]) + " " + str(self.floatArray[2]))
#                print(str(self.floatArray[4]) + " " + str(self.floatArray[3]) + " " + str(self.floatArray[5]))
                msg = "xyzrpy," + str(self.floatArray[1]) + "," + str(self.floatArray[0]) + "," + str(self.floatArray[2]) + "," + str(self.floatArray[4]) + "," + str(self.floatArray[3]) + "," + str(self.floatArray[5])
                print(msg)
            # msg = client.recv(self.MAX_MSG_LEN)
                self.inQ.put(msg)
            except:
                e = sys.exc_info()[0]
                s = traceback.format_exc()
                print "listener err", e, s
