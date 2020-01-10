##############################################
# Tooling Inspection Motion Controller GUI   #
# Tool: NOVA and LAPIS Piping Scanners       #
# PLM Code Storage:  DOC-00xx-xxxx           #
# PLM Parameter File Storage: DOC-00xx-xxxx  #
# Code Revision: 0                           #
# Development Version: 5.1                   #
##############################################
# Revision Updates:
#   <> Initial Release


# Author:   Vincent Vigliano
# Email:    vincent.vigliano@ge.com
# Date:     12/03/2019
# Company:  GE Hitachi

from tkinter import *
from tkinter import messagebox
import serial
import threading
import time
import datetime
import platform
import queue

baud = 115200
THREAD_WAIT = 0.0001
SCAN_THREAD_WAIT = .25
STATUS_THREAD_WAIT = 0.5
decpl = 1
parm_num_list = ["32",      # 0 PositionErrorThreshold
                 "39",      # 1 MaxCurrentClamp
                 "123",     # 2 MaxJogSpeed
                 "129",     # 3 UnitsName
                 "2",       # 4 Counts per Unit
                 "41",      # 5 Motor Type (2 - DC Brush, 3 - Stepper)
                 "1"]       # 6 Reverse Motion Direction


# This class sets Frame parameters for Axis 1
class SetupAxis1:
    def __init__(self):
        self.axisName = "TRANSLATOR"
        self.jogFWDText = "IN"
        self.jogREVText = "OUT"
        self.speedMin = 0.2
        self.speedRes = 0.2
        self.queue_name = "CTRL"
        self.motorMultiplier = 1

        # Open Communication and Get the Following Parameters from Ensemble
        self.parm_output_list = getparams(self.axisName)
        self.posErrLimit = float(self.parm_output_list[0])
        self.currentLimit = float(self.parm_output_list[1])
        self.speedMax = float(self.parm_output_list[2])
        self.axisUnits = self.parm_output_list[3]
        self.ctsPerUnit = float(self.parm_output_list[4])
        self.motorType = int(self.parm_output_list[5])
        self.motorDirection = int(self.parm_output_list[6])


# This class sets Frame parameters for Axis 2
class SetupAxis2:
    def __init__(self):
        self.axisName = "CIRC"
        self.jogFWDText = "CCW"
        self.jogREVText = "CW"
        self.speedMin = 0.2
        self.speedRes = 0.2
        self.queue_name = "CTRL"
        self.motorMultiplier = 1

        # Open Communication and Get the Following Parameters from Ensemble
        self.parm_output_list = getparams(self.axisName)
        self.posErrLimit = float(self.parm_output_list[0])
        self.currentLimit = float(self.parm_output_list[1])
        self.speedMax = float(self.parm_output_list[2])
        self.axisUnits = self.parm_output_list[3]
        self.ctsPerUnit = float(self.parm_output_list[4])
        self.motorType = int(self.parm_output_list[5])
        self.motorDirection = int(self.parm_output_list[6])


# This class places a button on the top of the GUI to select between LAPIS and NOVA
class ToolFrame:
    def __init__(self, master, params):
        # Read in first parameter from TIMC setup file list to determine last configuration
        self.toolName = params[0].replace("\n", "")
        topFrame = Frame(master, relief=SUNKEN, border=2)
        topFrame.pack(fill=X, padx=10, pady=10)
        self.toolButton = Button(topFrame, text=self.toolName, font="Helvetica, 14 bold", fg="Black",
                                 command=lambda: self.toggle_tool())
        self.toolButton.pack(fill=X)

        # Set Button Name and Color based on Tool from Setup File
        if self.toolName == "LAPIS":
            self.toolButton.config(text=self.toolName, fg="Black", bg="Goldenrod")
        elif self.toolName == "NOVA":
            self.toolButton.config(text=self.toolName, fg="Black", bg="Deep Sky Blue")
        self.toolButton.pack(fill=X)

    # Toggle tool between LAPIS and NOVA, overwrite setup file list
    def toggle_tool(self):
        # Only used in offline mode
        if not TIMC.online:
            if self.toolName == "NOVA":
                # Switch to LAPIS, Update Setup File
                self.toolName = "LAPIS"
                self.toolButton.config(text=self.toolName, bg="Goldenrod")
                TIMC.master.config(bg="Light Goldenrod")
                TIMC.params[0] = "LAPIS\n"

            elif self.toolName == "LAPIS":
                # Switch to NOVA, Update Setup File
                self.toolName = "NOVA"
                self.toolButton.config(text=self.toolName, bg="Deep Sky Blue")
                TIMC.master.config(bg="Light Blue")
                TIMC.params[0] = "NOVA\n"


# This class pulls parameters from the specific axis and puts them in the GUI
class AxisFrame:
    def __init__(self, master, parameters):
        self.axisName = parameters.axisName
        self.axisUnits = parameters.axisUnits
        self.jogFWDText = parameters.jogFWDText
        self.jogREVText = parameters.jogREVText
        self.speedMin = parameters.speedMin
        self.speedMax = parameters.speedMax
        self.speedRes = parameters.speedRes
        self.parm_output_list = parameters.parm_output_list
        self.motorType = parameters.motorType
        self.currentLimit = parameters.currentLimit
        self.posErrLimit = parameters.posErrLimit
        self.ctsPerUnit = parameters.ctsPerUnit
        self.motorDirection = parameters.motorDirection
        self.queue = parameters.queue_name
        self.motorMultiplier = parameters.motorMultiplier

        self.state = 0  # Flag for Enabled/Disabled Axis

        self.frame = Frame(master, relief=SUNKEN, border=2)
        self.frame.pack(fill=X, padx=10, pady=5)

        self.position = StringVar(master, value=str(round(float(0), decpl)))
        self.pos_err = float(0)
        self.current = float(0)
        self.velocity = StringVar(master, value=str(round(float(0), decpl)))
        self.setToText = StringVar(master, value="0")
        self.GoToText = StringVar(master, value="0")
        self.moveIncText = StringVar(master, value="0")

        # Create Widgets
        # Frames
        self.pos_frame = Frame(self.frame, bg="White", relief=SUNKEN, border=2)
        self.button_frame = Frame(self.frame)
        self.error_frame = Frame(self.frame)
        self.pos_err_graph = Canvas(self.error_frame, bg="white", height=100, width=20)
        self.current_graph = Canvas(self.error_frame, bg="white", height=100, width=20)

        # Labels
        self.label_0 = Label(self.frame, text=self.axisName, font="Helvetica, 14 bold")
        self.label_1 = Label(self.pos_frame, text=self.axisUnits, fg="Gray", bg="White", anchor=W, font="Helvetica, 20 bold")
        self.label_2 = Label(self.pos_frame, text="Velocity", font=("Helvetica", 8), bg="White")
        self.label_3 = Label(self.pos_frame, text=(self.axisUnits + "/s"), font=("Helvetica", 8), bg="White")
        self.label_4 = Label(self.button_frame,  text=("Speed (" + self.axisUnits + "/s)"), font=("Helvetica", 10))
        self.label_5 = Label(self.error_frame, text="Pos Err", font=("Helvetica", 8))
        self.label_6 = Label(self.error_frame, text="Current", font=("Helvetica", 8))

        # Buttons
        self.abortButton = Button(self.frame, text="ABORT", fg="Gray", bg="Light Coral", height=1, width=5, state="disabled", command=lambda: self.abort_axis(), font="Helvetica, 8 bold")
        self.enableButton = Button(self.frame, text="OFF", fg="Red", bg="Light Grey", height=1, width=8,
                                   command=lambda: self.toggle_axis(), font="Helvetica, 12 bold")
        self.setToButton = Button(self.button_frame, text="SET TO:", fg="Black", bg="Light Grey", height=1, width=10,
                                  state="normal", command=lambda: self.setTo(1))
        self.GoToButton = Button(self.button_frame, text="GO TO:", fg="Gray", bg="Light Grey", height=1, width=10,
                                 state="disabled",
                                 command=lambda: self.GoTo(1))
        self.moveIncButton = Button(self.button_frame, text="MOVE INC:", fg="Gray", bg="Light Grey", height=1, width=10,
                                    state="disabled", command=lambda: self.moveInc())
        self.setToZero = Button(self.button_frame, text="Set To 0", fg="Black", bg="Light Grey", height=1, state="normal", command=lambda: self.setTo(0))
        self.GoToZero = Button(self.button_frame, text="Go To 0", fg="Gray", bg="Light Grey", height=1, state="disabled", command=lambda: self.GoTo(0))
        self.jogButtonFWD = Button(self.frame, text="Jog " + self.jogFWDText, fg="Gray", bg="Light Grey", height=1, width=10,
                                   font="Helvetica, 12 bold", state="disabled")
        self.jogButtonREV = Button(self.frame, text="Jog " + self.jogREVText, fg="Gray", bg="Light Grey", height=1, width=10,
                                   font="Helvetica, 12 bold", state="disabled")

        # Feedback Labels and Entry Boxes
        self.position_box = Entry(self.pos_frame, state="readonly", textvariable=self.position, fg="Gray", readonlybackground="White", width=7, relief="flat", font="Helvetica, 26 bold", justify="center")
        self.velocity_box = Entry(self.pos_frame, state="disabled", textvariable=self.velocity, disabledbackground="White", readonlybackground="White", width=8, relief="flat", font="Helvetica, 8", justify="center")
        self.pos_err_box = Label(self.error_frame, text=str(round(self.pos_err, decpl)), fg="Gray", bg="SystemButtonFace", width=6, anchor=N, font="Helvetica, 8")
        self.current_box = Label(self.error_frame, text=str(round(self.current, decpl)), fg="Gray", bg="SystemButtonFace", width=6, anchor=N, font="Helvetica, 8")

        self.setToEntry = Entry(self.button_frame, textvariable=self.setToText, width=10, font=("Helvetica", 10), justify="center")
        self.GoToEntry = Entry(self.button_frame, textvariable=self.GoToText, width=10, font=("Helvetica", 10), justify="center")
        self.moveIncEntry = Entry(self.button_frame, textvariable=self.moveIncText, width=10, font=("Helvetica", 10), justify="center")

        # Velocity Scale
        self.vel = Scale(self.frame, from_=self.speedMin, to=self.speedMax, orient=HORIZONTAL, length=200, resolution=self.speedRes, troughcolor="White")
        self.vel.set((self.speedMax - self.speedMin) * 0.5)

        # Jog Button Actions
        self.jogButtonFWD.bind('<ButtonPress-1>', lambda event: self.jogFWD())
        self.jogButtonFWD.bind('<ButtonRelease-1>', lambda event: self.stopjog())
        self.jogButtonREV.bind('<ButtonPress-1>', lambda event: self.jogREV())
        self.jogButtonREV.bind('<ButtonRelease-1>', lambda event: self.stopjog())

        # Grid Widgets
        self.label_0.grid(column=0, row=0, pady=5, sticky=W)
        self.abortButton.grid(column=1, row=0, padx=5, sticky=E)
        self.pos_frame.grid(column=0, row=1, columnspan=2, rowspan=3, padx=5, sticky=N)
        self.position_box.grid(column=0, row=0, columnspan=2, pady=5)
        self.label_1.grid(column=3, row=0, pady=5)              # Units
        self.label_2.grid(column=0, row=1, padx=5, sticky=E)            # Velocity
        self.velocity_box.grid(column=1, row=1)
        self.label_3.grid(column=3, row=1, pady=2, sticky=W)            # Units/s
        self.enableButton.grid(column=0, row=4, columnspan=2, rowspan=1, padx=5, sticky=N)

        self.button_frame.grid(column=2, row=0, rowspan=3, columnspan=3)
        self.setToButton.grid(column=0, row=0, padx=10, sticky=S)
        self.setToEntry.grid(column=0, row=1, sticky=N)
        self.setToZero.grid(column=0, row=2, pady=5, sticky=N)
        self.moveIncButton.grid(column=1, row=0, padx=10, sticky=S)
        self.moveIncEntry.grid(column=1, row=1, sticky=N)
        self.label_4.grid(column=1, row=2, sticky=S)                    # Units/s
        self.GoToButton.grid(column=2, row=0, padx=10, sticky=S)
        self.GoToEntry.grid(column=2, row=1, sticky=N)
        self.GoToZero.grid(column=2, row=2,  pady=5, sticky=N)

        self.vel.grid(column=2, row=2, rowspan=2, columnspan=3, sticky=S)
        self.vel.lower()
        self.jogButtonFWD.grid(column=2, row=4, rowspan=2, padx=10, pady=5, sticky=SW)
        self.jogButtonREV.grid(column=4, row=4, rowspan=2, padx=10, pady=5, sticky=SE)

        self.error_frame.grid(column=5, row=0, rowspan=5, padx=5)
        self.pos_err_graph.grid(column=0, row=0)
        self.current_graph.grid(column=1, row=0)
        self.label_5.grid(column=0, row=1, sticky=S)                    # Current
        self.label_6.grid(column=1, row=1, sticky=S)                    # Pos Err
        self.pos_err_rect = self.pos_err_graph.create_rectangle(2, 98, 21, 100, fill="red", outline="red")
        self.current_rect = self.current_graph.create_rectangle(2, 98, 21, 100, fill="red", outline="red")
        self.pos_err_box.grid(column=0, row=2)
        self.current_box.grid(column=1, row=2)

    # This function toggles the button between OFF and ON
    def toggle_axis(self):
        if self.state or TIMC.fault.fault_state:
            self.disable_axis()
        else:
            self.enable_axis()

    # This function enables the axis
    def enable_axis(self):
        self.state = 1
        self.activate_axis_btns()
        self.enableButton.config(text="ON")
        if TIMC.online == 1:
            TIMC.acmd(self.queue, "ENABLE " + self.axisName)    # Aerotech command to enable axis

        if TIMC.axis1.state and TIMC.axis2.state and not TIMC.scan.paused and not TIMC.scan.scan_state:
            TIMC.scan.activate_scan_btns()                      # Once both axes are enabled, scan button is active

        if TIMC.axis1.state and TIMC.axis2.state and TIMC.scan.paused:
            TIMC.scan.resume.config(state="normal", fg="Black", bg="Dodger Blue")
            TIMC.scan.stop.config(state="normal", fg="Black", bg="Indian Red")

    # This function disables the axis
    def disable_axis(self):
        self.state = 0
        self.deactivate_axis_btns()
        self.enableButton.config(text="OFF", fg="Red", bg="Light Grey")
        if TIMC.online == 1:
            TIMC.acmd(self.queue, "DISABLE " + self.axisName)   # Aerotech command to disable axis

        if TIMC.scan.scan_state:
            TIMC.scan.pause_scan()
        else:
            TIMC.scan.deactivate_scan_btns()

    def activate_axis_btns(self):
        self.state = 1
        self.abortButton.config(state="normal", fg="Black", bg="Indian Red")
        self.enableButton.config(state="normal", fg="Black", bg="Lawn Green")
        self.setToButton.config(state="normal", fg="Black", bg="Lawn Green")
        self.GoToButton.config(state="normal", fg="Black", bg="Lawn Green")
        self.moveIncButton.config(state="normal", fg="Black", bg="Lawn Green")
        self.setToZero.config(state="normal", fg="Black", bg="Lawn Green")
        self.GoToZero.config(state="normal", fg="Black", bg="Lawn Green")
        if TIMC.tool.toolName == "NOVA":
            self.jogButtonFWD.config(state="normal", fg="Black", bg="Deep Sky Blue")
            self.jogButtonREV.config(state="normal", fg="Black", bg="Deep Sky Blue")
        else:
            self.jogButtonFWD.config(state="normal", fg="Black", bg="Goldenrod")
            self.jogButtonREV.config(state="normal", fg="Black", bg="Goldenrod")
        self.position_box.config(fg="Black")
        self.label_1.config(fg="Black")
        self.velocity_box.config(state="readonly", fg="Black")

    def deactivate_axis_btns(self):
        self.abortButton.config(state="disabled", fg="Gray", bg="Light Coral")
        self.GoToButton.config(state="disabled", fg="Gray", bg="Light Grey")
        self.moveIncButton.config(state="disabled", fg="Gray", bg="Light Grey")
        self.GoToZero.config(state="disabled", fg="Gray", bg="Light Grey")
        self.jogButtonFWD.config(state="disabled", fg="Gray", bg="Light Grey")
        self.jogButtonREV.config(state="disabled", fg="Gray", bg="Light Grey")
        self.position_box.config(fg="Gray")
        self.label_1.config(fg="Gray")
        self.velocity_box.config(state="disabled")
        # Keep Set To and Set To Zero Buttons Active unless scanning
        if TIMC.scan.scan_state:
            self.setToButton.config(state="disabled", fg="Gray", bg="Light Grey")
            self.setToZero.config(state="disabled", fg="Gray", bg="Light Grey")
        else:
            self.setToButton.config(state="normal", fg="Black", bg="Light Grey")
            self.setToZero.config(state="normal", fg="Black", bg="Light Grey")

    # This function starts Jogging in the FORWARD Direction
    def jogFWD(self):
        if TIMC.online == 1 and TIMC.scan.scan_state == 0 and self.state == 1:
            TIMC.acmd(self.queue, "ABORT " + self.axisName)
            if self.motorDirection:
                speed = str(self.motorMultiplier * self.vel.get())
            else:
                speed = str(-self.motorMultiplier * self.vel.get())
            TIMC.acmd(self.queue, "FREERUN " + self.axisName + " " + speed)

    # This function starts Jogging in the REVERSE Direction
    def jogREV(self):
        if TIMC.online == 1 and TIMC.scan.scan_state == 0 and self.state == 1:
            TIMC.acmd(self.queue, "ABORT " + self.axisName)
            if self.motorDirection:
                speed = str(-self.motorMultiplier * self.vel.get())
            else:
                speed = str(self.motorMultiplier * self.vel.get())
            TIMC.acmd(self.queue, "FREERUN " + self.axisName + " " + speed)

    # This function stops Jogging
    def stopjog(self):
        if TIMC.online == 1 and TIMC.scan.scan_state == 0 and self.state == 1:
            TIMC.acmd(self.queue, "FREERUN " + self.axisName + " 0")

    # This function sets the position in the position label based on Set To Entry Box
    def setTo(self, zero):
        if zero == 0:
            position = "0"
        else:
            position = str(self.setToEntry.get())
        if check_is_digit(position):
            if TIMC.online == 1:
                TIMC.acmd(self.queue, "POSOFFSET SET " + self.axisName + ", " + position)
            else:
                self.position.set(str(round(float(position), decpl)))

    def GoTo(self, zero):
        if zero == 0:
            position = "0"
        else:
            position = str(self.GoToEntry.get())
        if check_is_digit(position):
            if TIMC.online == 1:
                speed = str(self.vel.get())
                TIMC.acmd(self.queue, "MOVEABS " + self.axisName + " " + position + " F " + speed)
            else:
                self.position.set(str(round(float(position), decpl)))

    def moveInc(self):
        distance = self.moveIncEntry.get()
        if check_is_digit(distance):
            if TIMC.online == 1:
                speed = str(self.vel.get())
                TIMC.acmd(self.queue, "MOVEINC " + self.axisName + " " + distance + " F " + speed)
            else:
                position = str(float(self.position.get()) + float(distance))
                self.position.set(str(round(float(position), decpl)))

    def abort_axis(self):
        if TIMC.online == 1:
            TIMC.acmd(self.queue, "ABORT " + self.axisName)

    def updateCurrent(self, cur):
        self.current_box.config(text=("%.2f" % cur))
        cur_line = int(98 - round(abs((cur/self.currentLimit)*100)))
        # Delete the old representation of current
        self.current_graph.delete(self.current_rect)
        # Draw the new position error box
        self.current_rect = self.current_graph.create_rectangle(2, cur_line, 21, 100, fill="red", outline="red")

    def updatePosErr(self, pos_err):
        self.pos_err_box.config(text=str(round(pos_err, decpl)))
        pos_err_line = int(98 - round(abs((pos_err/self.posErrLimit)*100)))
        # Delete the old representation of current
        self.pos_err_graph.delete(self.pos_err_rect)
        # Draw the new position error box
        self.pos_err_rect = self.pos_err_graph.create_rectangle(2, pos_err_line, 21, 100, fill="red", outline="red")


# This class creates a Scan Window in the GUI
class ScanFrame:
    def __init__(self, master, axis1_parameters, axis2_parameters, scan_parameters):
        self.master = master
        self.axis1 = axis1_parameters
        self.axis2 = axis2_parameters
        self.scanTypeVar = StringVar()
        self.scanConfigVar = StringVar()
        self.scan_setup = []
        self.scan_config = []
        # Input scan setup parameters from setup text file
        # Indices 1-5 are scan setup values (Scan Start, Scan Stop, Index Start, Index Stop, Index Size)
        for i in range(1, 6):
            self.scan_setup.append(scan_parameters[i].replace("\n", ""))  # Input Values from Setup File
        self.scan_config = []
        # Indices 6, 7 are configuration (Bi/Uni, Scan Axis Selection)
        for i in range(6, 8):
            self.scan_config.append(scan_parameters[i].replace("\n", ""))  # Input Values from Setup File
        # Indices 8, 9 are speeds
        self.axis1_scan_speed = float(scan_parameters[8].replace("\n", ""))
        self.axis2_scan_speed = float(scan_parameters[9].replace("\n", ""))
        # Scan State Flags
        self.scan_state = 0
        self.paused = 0
        self.var_check = 0
        # Scan Time Variables
        self.scanTimeText = StringVar()
        self.scanTimeText.set("00:00:00")

        scan_frame = Frame(master, relief=SUNKEN, border=2)
        left_frame = Frame(scan_frame)
        right_frame = Frame(scan_frame)
        bottom_frame = Frame(master, relief=RAISED, border=2)
        scan_frame.pack(fill=X, padx=10)

        left_frame.grid(column=0, row=0, sticky=W)
        right_frame.grid(column=1, row=0, padx=20)
        bottom_frame.pack(fill=X, padx=10)

        # Labels and Axis Names
        self.label_0 = Label(left_frame, text="SCAN WINDOW", font=("Helvetica", 14))
        self.axis_label_1 = Label(left_frame, text=self.axis1.axisName, font=("Helvetica", 12))
        self.axis_label_2 = Label(left_frame, text=self.axis2.axisName, font=("Helvetica", 12))

        # Start, Stop, Pause, and Resume Buttons
        self.start = Button(bottom_frame, text="START", font="Helvetica, 12 bold", fg="Gray", bg="Light Green", height=2,
                            width=10, command=lambda: self.start_scan(), state="disabled")
        self.stop = Button(bottom_frame, text="STOP", font="Helvetica, 12 bold", fg="Gray", bg="Light Coral", height=2,
                           width=10, command=lambda: self.stop_scan(), state="disabled")
        self.pause = Button(bottom_frame, text="PAUSE", font="Helvetica, 12 bold", fg="Gray", bg="Light Yellow", height=2, width=10,
                            command=lambda: self.pause_scan(), state="disabled")
        self.resume = Button(bottom_frame, text="RESUME", font="Helvetica, 10 bold", fg="Gray", bg="Light Blue", height=1, width=10,
                             command=lambda: self.resume_scan(), state="disabled")

        # Speed slider bars
        self.vel1 = Scale(left_frame, from_=self.axis1.speedMin, to=self.axis1.speedMax, orient=HORIZONTAL, length=100,
                          label="Speed " + self.axis1.axisUnits + "/sec", font=("Helvetica", 10),
                          resolution=self.axis1.speedRes)
        self.vel1.set(self.axis1_scan_speed)
        self.vel2 = Scale(left_frame, from_=self.axis2.speedMin, to=self.axis2.speedMax, orient=HORIZONTAL, length=100,
                          label="Speed " + self.axis2.axisUnits + "/sec", font=("Helvetica", 10),
                          resolution=self.axis2.speedRes)
        self.vel2.set(self.axis2_scan_speed)

        # Scan configuration
        self.scanTypeVar.set(self.scan_config[0])
        self.scanTypeMenu = OptionMenu(right_frame, self.scanTypeVar, "Bidirectional", "Unidirectional")
        self.scanTypeMenu.config(width=15, font="Helvetica, 10 bold")
        if self.scan_config[1] == "axis1":
            self.scanConfigVar.set(self.axis1.axisName)
        else:
            self.scanConfigVar.set(self.axis2.axisName)
        self.scanConfigMenu = OptionMenu(right_frame, self.scanConfigVar, self.axis1.axisName, self.axis2.axisName)
        self.scanConfigMenu.config(width=15, font="Helvetica, 10 bold")

        # Scan Entry Labels
        self.label_1 = Label(right_frame, text="Scan Start", font=("Helvetica", 10))
        self.label_2 = Label(right_frame, text="Scan Stop", font=("Helvetica", 10))
        self.label_3 = Label(right_frame, text="Index Start", font=("Helvetica", 10))
        self.label_4 = Label(right_frame, text="Index Stop", font=("Helvetica", 10))
        self.label_5 = Label(right_frame, text="Index Size", font=("Helvetica", 10))
        self.label_6 = Label(right_frame, text="Remaining Move Time", font=("Helvetica", 10))
        self.label_7 = Label(right_frame, text="Scan Type:", font=("Helvetica", 10))
        self.label_8 = Label(right_frame, text="Scan Axis:", font=("Helvetica", 10))

        # Scan Entry Boxes
        self.e_scanStart = Entry(right_frame, width=8, font=("Helvetica", 10), justify="center")
        self.e_scanStart.insert(0, self.scan_setup[0])
        self.e_scanStop = Entry(right_frame, width=8, font=("Helvetica", 10), justify="center")
        self.e_scanStop.insert(0, self.scan_setup[1])
        self.e_indexStart = Entry(right_frame, width=8, font=("Helvetica", 10), justify="center")
        self.e_indexStart.insert(0, self.scan_setup[2])
        self.e_indexStop = Entry(right_frame, width=8, font=("Helvetica", 10), justify="center")
        self.e_indexStop.insert(0, self.scan_setup[3])
        self.e_indexSize = Entry(right_frame, width=8, font=("Helvetica", 10), justify="center")
        self.e_indexSize.insert(0, self.scan_setup[4])
        self.time_entry = Entry(right_frame, state="readonly", width=8, font="Courier, 12", textvariable=self.scanTimeText)

        # Place widgets in frames
        self.label_0.grid(column=0, row=0, columnspan=2, sticky=W)
        self.axis_label_1.grid(column=0, row=2, rowspan=2, sticky=E, pady=5)
        self.axis_label_2.grid(column=0, row=4, rowspan=2, sticky=E, pady=5)
        self.vel1.grid(column=1, row=2, rowspan=2, columnspan=2, pady=5)
        self.vel2.grid(column=1, row=4, rowspan=2, columnspan=2, pady=5)
        self.label_7.grid(column=0, row=0, sticky=S)
        self.scanTypeMenu.grid(column=0, row=1, columnspan=2, rowspan=2, padx=30, sticky=NW)
        self.label_8.grid(column=0, row=2, sticky=S)
        self.scanConfigMenu.grid(column=0, row=3, columnspan=2, rowspan=2, padx=30, sticky=NW)
        self.label_1.grid(column=2, row=0, sticky=E)
        self.label_2.grid(column=2, row=1, sticky=E)
        self.label_3.grid(column=2, row=2, sticky=E)
        self.label_4.grid(column=2, row=3, sticky=E)
        self.label_5.grid(column=2, row=4, sticky=E)
        self.label_6.grid(column=1, row=5, columnspan=2, padx=2)
        self.e_scanStart.grid(column=3, row=0, padx=5, pady=4)
        self.e_scanStop.grid(column=3, row=1, padx=5, pady=4)
        self.e_indexStart.grid(column=3, row=2, padx=5, pady=4)
        self.e_indexStop.grid(column=3, row=3, padx=5, pady=4)
        self.e_indexSize.grid(column=3, row=4, padx=5, pady=4)
        self.time_entry.grid(column=3, row=5, columnspan=2, pady=5, padx=5, sticky=E)
        self.start.pack(side=LEFT, padx=22, pady=5)
        self.stop.pack(side=LEFT, padx=22, pady=5)
        self.resume.pack(side=RIGHT, padx=22, pady=5)
        self.pause.pack(side=RIGHT, padx=22, pady=5)

    # Start Scan Button Function
    def start_scan(self):
        TIMC.fault.clear_status()  # Clear Fault Status

        # Get values from Entry Boxes
        self.scan_setup = [self.e_scanStart.get(), self.e_scanStop.get(), self.e_indexStart.get(), self.e_indexStop.get(), self.e_indexSize.get()]
        self.e_scanStart.config(state="readonly")
        self.e_scanStop.config(state="readonly")
        self.e_indexStart.config(state="readonly")
        self.e_indexStop.config(state="readonly")
        self.e_indexSize.config(state="readonly")

        # Deactivate Start Scan Button and Axis Buttons During Scan
        self.start.config(state="disabled", fg="Gray")
        TIMC.axis1.deactivate_axis_btns()
        TIMC.axis2.deactivate_axis_btns()

        # Deactivate Menus
        self.scanTypeMenu.config(state="disabled")
        self.scanConfigMenu.config(state="disabled")

        # Activate Stop and Pause Buttons
        self.stop.config(state="normal", fg="Black", bg="Indian Red")
        self.pause.config(state="normal", fg="Black", bg="Gold")

        # Run through scan_setup array to check inputs for errors
        self.var_check = 0
        for i in range(0, 5):
            # Check if user has entered data
            if self.scan_setup[i] == "":
                messagebox.showinfo("Bad Scan Input", "User must enter all five scan window inputs")
                self.stop_scan()
                return
            # If there is a negative sign
            elif "-" in self.scan_setup[i]:
                # There should only be one and it should be at the beginning
                if self.scan_setup[i].count("-") > 1 and self.scan_setup[i].index('-') != 0:
                    messagebox.showinfo("Bad Scan Input", "Error associated with '-' character")
                    self.stop_scan()
                    return
            # If there is a period sign there should only be one
            elif "." in self.scan_setup[i]:
                # There should only be one period
                if self.scan_setup[i].count(".") > 1:
                    messagebox.showinfo("Bad Scan Input", "Error associated with '.' character")
                    self.stop_scan()
                    return
            # Finally check if input is a number
            elif check_is_digit(self.scan_setup[i]) is False:
                messagebox.showinfo("Bad Scan Input", "Error scan inputs have characters")
                self.stop_scan()
                return

        if self.vel1.get() == 0 or self.vel2.get() == 0:
            messagebox.showinfo("Bad Scan Input", "Scan or Index Speed is 0")
            self.stop_scan()
            return

        # Convert scan setup data to type float for more checks
        scan_start = round(float(self.scan_setup[0]), 2)
        scan_stop = round(float(self.scan_setup[1]), 2)
        index_start = round(float(self.scan_setup[2]), 2)
        index_stop = round(float(self.scan_setup[3]), 2)
        index_size = round(float(self.scan_setup[4]), 2)

        # Is Start Scan =  End Scan or Start Index = End Index
        if scan_start == scan_stop or index_start == index_stop:
            messagebox.showinfo("Bad Scan Inputs", "Start/Stop Values are Same")
            self.stop_scan()
            return
        # Is Index Increment multiple of Index Range
        rem = round(abs(index_start - index_stop) % index_size, 2)
        if rem > 0:
            messagebox.showinfo("Bad Scan Input", "Index Size must be a multiple of Index Start - Index Stop")
            self.stop_scan()
            return
        # Is Index size negative
        if index_size < 0:
            index_size = abs(index_size)

        # If inputs are good, get scan type and index/scan axis and start scan
        self.var_check = 1
        self.scan_state = 1
        if self.scanTypeVar.get() == "Unidirectional":
            self.scan_type = 1
        else:
            self.scan_type = 2

        if self.scanConfigVar.get() == self.axis1.axisName:
            self.scan_axis = self.axis1.axisName
            self.index_axis = self.axis2.axisName
            self.scan_speed = self.vel1.get()
            self.index_speed = self.vel2.get()
        else:
            self.scan_axis = self.axis2.axisName
            self.index_axis = self.axis1.axisName
            self.scan_speed = self.vel2.get()
            self.index_speed = self.vel1.get()

        self.scan_points = self.create_scan_points(scan_start, scan_stop, index_start, index_stop, index_size)
        self.process_scan = ScanThread(self.scan_setup, self.scan_type, self.scan_points, self.scan_axis, self.index_axis, self.scan_speed, self.index_speed)
        if TIMC.online:
            self.process_scan.start()

    # Stop Scan Button Function
    def stop_scan(self):
        if TIMC.online and TIMC.scan.var_check:
            self.process_scan.stop()
        # Activate Start Scan Button and Axis Buttons if Scan was not stopped via Axis Disable
        if TIMC.axis1.state:
            TIMC.axis1.activate_axis_btns()
        if TIMC.axis2.state:
            TIMC.axis2.activate_axis_btns()
        if TIMC.axis1.state and TIMC.axis2.state:
            self.activate_scan_btns()

        # Deactivate Stop, Pause and Resume
        self.stop.config(state="disabled", fg="Gray", bg="Light Coral")
        self.pause.config(state="disabled", fg="Gray", bg="Light Yellow")
        self.resume.config(state="disabled", fg="Gray", bg="Light Blue")
        self.scanTimeText.set("00:00:00")
        # Reactivate Entry Boxes
        self.e_scanStart.config(state="normal")
        self.e_scanStop.config(state="normal")
        self.e_indexStart.config(state="normal")
        self.e_indexStop.config(state="normal")
        self.e_indexSize.config(state="normal")
        # Reactivate Menus
        self.scanTypeMenu.config(state="normal")
        self.scanConfigMenu.config(state="normal")
        self.scan_state = 0
        self.paused = 0

    # Pause Scan Button Function
    def pause_scan(self):
        if TIMC.online:
            self.process_scan.pause()

        # Activate Axis Buttons and Resume Button if not in a fault state and both axes are Enabled
        if not TIMC.fault.fault_state:
            if TIMC.axis1.state:
                TIMC.axis1.activate_axis_btns()
                TIMC.axis1.enableButton.config(state="normal")
            if TIMC.axis2.state:
                TIMC.axis2.activate_axis_btns()
                TIMC.axis2.enableButton.config(state="normal")
            if TIMC.axis1.state and TIMC.axis2.state:
                self.resume.config(state="normal", fg="Black", bg="Dodger Blue")
                self.pause.config(state="disabled", fg="Gray", bg="Light Yellow")
            else:
                self.stop.config(state="normal", fg="Black", bg="Indian Red")
                self.pause.config(state="disabled", fg="Gray", bg="Light Yellow")

        self.scan_state = 0
        self.paused = 1

    # Resume Scan Button Function
    def resume_scan(self):
        # Deactivate Axis Buttons and Resume Button
        TIMC.axis1.deactivate_axis_btns()
        TIMC.axis2.deactivate_axis_btns()
        TIMC.scan.resume.config(state="disabled", fg="Gray", bg="Light Blue")
        TIMC.scan.pause.config(state="normal", fg="Black", bg="Gold")
        self.scan_state = 1
        self.paused = 0
        if TIMC.online:
            self.process_scan.resume()

    # Function to activate Start Scan Button and set time to zero
    def activate_scan_btns(self):
        self.start.config(state="normal", fg="Black", bg="Lawn Green")
        self.scanTimeText.set("00:00:00")

    # Function to deactivate all Scan Buttons
    def deactivate_scan_btns(self):
        self.start.config(state="disabled", fg="Gray", bg="Light Green")
        self.stop.config(state="disabled", fg="Gray", bg="Light Coral")
        self.pause.config(state="disabled", fg="Gray", bg="Light Yellow")
        self.resume.config(state="disabled", fg="Gray", bg="Light Blue")

    # Method calculates the scan points based on the user input
    def create_scan_points(self, scan_start, scan_stop, index_start, index_stop, index_size):
        if (index_stop - index_start) > 0:
            i_var = index_start - index_size            # Initialize index variable
        else:
            i_var = index_start + index_size
        s_var = scan_start                          # Initialize scan variable
        s_toggle = [scan_start, scan_stop]          # Toggle values for the scan axis scan points
        x = 0                                       # Toggle control variable

        # Calculate the number of points in the scan
        # Uni-directional
        if self.scanTypeVar.get() == "Unidirectional":
            size = int(abs(index_stop - index_start) / index_size * 3 + 3)
        # Bi-directional
        else:
            size = int(abs(index_stop - index_start) / index_size * 2 + 2)

        # 2D array for scan points [scan][index]
        w, h = 2, size
        scan_points = [[0 for x in range(w)] for y in range(h)]

        # Calculate scan points and store to 2D array scan_points
        # Uni-directional
        if self.scanTypeVar.get() == "Unidirectional":
            for i in range(0, size):
                # Set s_var
                if i % 3 == 1:
                    s_var = scan_stop
                # Increment i_var
                elif i % 3 == 0 and (index_stop - index_start) > 0:
                    i_var += index_size
                elif i % 3 == 0 and (index_stop - index_start) < 0:
                    i_var -= index_size
                else:
                    s_var = scan_start
                scan_points[i][0] = round(s_var, 2)
                scan_points[i][1] = round(i_var, 2)

        # Bi-directional
        else:
            for i in range(0, size):
                # Toggle s_var
                if i % 2:
                    x = 1 if x == 0 else 0
                    s_var = s_toggle[x]
                # Increment i_var
                elif index_stop > 0:
                    i_var += index_size
                else:
                    i_var -= index_size
                scan_points[i][0] = round(s_var, 2)
                scan_points[i][1] = round(i_var, 2)
        print(scan_points)
        return scan_points


# This class creates a Fault Frame in the GUI
class FaultFrame:
    def __init__(self, master):
        self.frame = Frame(master, borderwidth=2, relief=SUNKEN)
        self.canvas = Canvas(self.frame, highlightthickness=0)
        self.canvas.pack(fill=X)
        self.frame.pack(fill=X, padx=10, pady=5)
        self.frame.pack()
        self.status_text = StringVar()
        self.fault_state = 0

        self.label_0 = Label(self.canvas, text="FAULT STATUS", height=1, font=("Helvetica", 14))
        self.button = Button(self.canvas, text="FAULT\nRESET", font="Helvetica, 12", fg="black", bg="#d3d3d3", height=2,
                             width=6, command=lambda: self.fault_ack())
        self.entry = Entry(self.canvas, width=50, textvariable=self.status_text, font="Helvetica, 12", justify="center")
        self.label_0.grid(row=0, column=0, columnspan=2, sticky=W)
        self.entry.grid(row=1, column=0, columnspan=2, padx=30)
        self.button.grid(row=0, column=2, rowspan=2, pady=10, padx=5)

    # Method to display the fault text and change the background color to red
    def fault_status(self, text):
        self.canvas.config(bg="red")
        self.label_0.config(bg="red")
        self.fault_state = 1
        self.status_text.set(text)

    # Method to display information text and keep the background color default
    def update_status(self, text):
        self.canvas.config(bg="SystemButtonFace")
        self.label_0.config(bg="SystemButtonFace")
        self.entry.config(bg="Yellow")
        self.status_text.set(text)

    # Method to reset the fault and change background color back to default
    def fault_ack(self):
        if TIMC.online:
            TIMC.acmd("CTRL", "ACKNOWLEDGEALL")
            self.canvas.config(bg="SystemButtonFace")
            self.label_0.config(bg="SystemButtonFace")
            self.entry.config(bg="White")
            self.fault_state = 0
            self.status_text.set("")

    def clear_status(self):
        if not TIMC.fault.fault_state:
            self.canvas.config(bg="SystemButtonFace")
            self.label_0.config(bg="SystemButtonFace")
            self.entry.config(bg="White")
            self.fault_state = 0
            self.status_text.set("")


# This class starts a thread that opens communication and puts queued commands to the Ensemble
class SerialThread(threading.Thread):
    def __init__(self, qControl_read, qControl_write, qScan_read, qScan_write, qStatus_read, qStatus_write, qFBK_read, qFBK_write, qLog_write1, qLog_write2):
        threading.Thread.__init__(self)
        self.qControl_read = qControl_read
        self.qControl_write = qControl_write
        self.qScan_read = qScan_read
        self.qScan_write = qScan_write
        self.qStatus_read = qStatus_read
        self.qStatus_write = qStatus_write
        self.qFBK_read = qFBK_read
        self.qFBK_write = qFBK_write
        self.qLog_write1 = qLog_write1
        self.qLog_write2 = qLog_write2
        self.s = serial.Serial()
        self._is_running = 1
        self.port_open = 0

    def run(self):
        # Open the serial port
        result = find_port()
        if result:
            self.s = serial.Serial(result[0], baud, timeout=0.05)
            # Send a command to check if communication has been established
            self.s.write("ACKNOWLEDGEALL".encode('ascii') + b' \n')
            data = self.s.readline().decode('ascii')
            if '%' in data:
                self.port_open = 1
                self.s.write("WAIT MODE NOWAIT".encode('ascii') + b' \n')
                # Throw away second response
                self.s.readline().decode('ascii')
        else:
            self.port_open = 0
            self._is_running = 0

        # Serial Thread Main Loop - Check Queue for Commands to Send to Aerotech Drive
        while self._is_running:
            time.sleep(THREAD_WAIT)
            # Check if control queue has commands in the queue to send to the Aerotech drive
            if self.qControl_write.qsize():
                command = self.qControl_write.get().encode('ascii') + b' \n'
                self.s.write(command)
                data = self.s.readline().decode('ascii')
                self.qControl_read.put(data)
                # Copy data Log queue for processing
                self.qLog_write1.put("CTRL: " + str(command) + str(data))
            # Check if scan queue has commands in the queue to send to the Aerotech drive
            elif self.qScan_write.qsize():
                command = self.qScan_write.get().encode('ascii') + b' \n'
                self.s.write(command)
                data = self.s.readline().decode('ascii')
                self.qScan_read.put(data)
                # Copy data Log queue for processing
                self.qLog_write1.put("SCAN: " + str(command) + str(data))
            # Check if status queue has commands in the queue to send to the Aerotech drive
            elif self.qStatus_write.qsize():
                command = self.qStatus_write.get().encode('ascii') + b' \n'
                self.s.write(command)
                data = self.s.readline().decode('ascii')
                self.qStatus_read.put(data)
                # Copy data Log queue for processing
                self.qLog_write1.put("STAT: " + str(command) + str(data))
            # Check if log queue has actions that need to be copied to the main Log queue, e.g. start/stop/pause/resume buttons were pressed
            elif self.qLog_write2.qsize():
                log_entry = self.qLog_write2.get()
                self.qLog_write1.put(log_entry)
            # Check if feedback queue has commands in the queue. This is the least priority
            elif self.qFBK_write.qsize():
                command = self.qFBK_write.get().encode('ascii') + b' \n'
                self.s.write(command)
                data = self.s.readline().decode('ascii')
                self.qFBK_read.put(data)

        # Stop the thread from running
    def stop(self):
        self._is_running = 0
        try:
            self.s.close()
        except:
            print("No Serial Port to Close")


# This class starts a thread for automated scanning
class ScanThread(threading.Thread):
    def __init__(self, scan_setup, scan_type, scan_points, scan_axis, index_axis, scan_speed, index_speed):
        threading.Thread.__init__(self)
        self._is_running = 1        # used to determine if scan is running
        self._is_paused = 0         # used to determine if scan is in a pause state
        self._just_paused = 0       # used to get position after pausing
        self.scan_setup = scan_setup    # Array with scan setup values
        # Break out scan setup values
        self.scan_start = float(self.scan_setup[0])
        self.scan_stop = float(self.scan_setup[1])
        self.index_start = float(self.scan_setup[2])
        self.index_stop = float(self.scan_setup[3])
        self.index_size = float(self.scan_setup[4])
        self.scan_type = scan_type      # Uni (1) or Bi (2)
        self.scan_points = scan_points  # Array with GOTO position values
        self.scanName = scan_axis       # Axis name of Scan Axis
        self.indexName = index_axis     # Axis name of Index Axis
        self.scanSpeed = scan_speed     # Speed for Scan Axis
        self.indexSpeed = index_speed   # Speed for Index Axis
        self.axis1_position = float()
        self.axis2_position = float()
        self.scan_time = float()
        self.i = 0
        self.j = 0
        self.setDaemon(True)

    def run(self):
        # Create entry in logbook for start of scan
        TIMC.acmd("LOG", "LOG SCAN STARTED: " + TIMC.scan.scanTypeVar.get() +
                  ", SCAN START: " + self.scan_setup[0] +
                  ", SCAN STOP: " + self.scan_setup[1] +
                  ", INDEX START: " + self.scan_setup[2] +
                  ", INDEX STOP: " + self.scan_setup[3] +
                  ", INDEX SIZE: " + self.scan_setup[4] + "\n")
        TIMC.acmd("LOG", "SCAN POINTS: " + str(self.scan_points))
        print("Starting Scan")

        # Variable used while either scan or index axis is in motion to prevent double moves
        axis_is_moving = 0

        # Calculate Scan Time and start timer
        self.calc_scan_time(self.i, self.j)

        # While loop to run while scan thread is running
        while self._is_running:
            time.sleep(SCAN_THREAD_WAIT)

            # Obtain the position following a pause
            if self._just_paused == 1:
                self.axis1_position = round(float(TIMC.axis1.position.get()), 2)
                self.axis2_position = round(float(TIMC.axis2.position.get()), 2)
                self._just_paused = 0

            # Check the status of each axis to determine if it is time to move to the next scan point
            scan_status = int(TIMC.acmd("SCAN", "AXISSTATUS(" + self.scanName + ")"))
            scan_enabled = 0b1 & scan_status
            scan_in_pos = 0b100 & scan_status

            index_status = int(TIMC.acmd("SCAN", "AXISSTATUS(" + self.indexName + ")"))
            index_enabled = 0b1 & index_status
            index_in_pos = 0b100 & index_status

            # Main Scan Logic Loop, determines if conditions are met to move to next location and issues move command
            # Starts looking at conditions to move Scan Axis
            if self.i == self.j and self.i < len(self.scan_points):
                if scan_enabled and index_enabled and TIMC.fault.fault_state == 0:
                    if scan_in_pos and index_in_pos and not axis_is_moving and not self._is_paused:
                        print("MOVING SCAN AXIS " + str(self.i))
                        self.calc_scan_time(self.i, self.j)
                        axis_is_moving = 1
                        TIMC.acmd("SCAN", "MOVEABS " + self.scanName + " " + str(self.scan_points[self.i][0]) + " F " + str(self.scanSpeed))
                        while axis_is_moving:
                            if TIMC.fault.fault_state == 1:
                                axis_is_moving = 0
                                TIMC.scan.pause_scan()
                            elif self._is_paused:
                                axis_is_moving = 0
                            else:
                                scan_status = int(TIMC.acmd("SCAN", "AXISSTATUS(" + self.scanName + ")"))
                                scan_in_pos = 0b100 & scan_status
                                if scan_in_pos and not self._is_paused:
                                    print("DONE.")
                                    axis_is_moving = 0
                                    self.i += 1
                                else:
                                    time.sleep(SCAN_THREAD_WAIT)
            # Looks at conditions to move Index Axis
            elif self.j < len(self.scan_points):
                if scan_enabled and index_enabled and TIMC.fault.fault_state == 0:
                    if scan_in_pos and index_in_pos and not axis_is_moving and not self._is_paused:
                        print("MOVING INDEX AXIS " + str(self.j))
                        self.calc_scan_time(self.i, self.j)
                        axis_is_moving = 1
                        TIMC.acmd("SCAN", "MOVEABS " + self.indexName + " " + str(self.scan_points[self.j][1]) + " F " + str(self.indexSpeed))
                        while axis_is_moving:
                            if TIMC.fault.fault_state == 1:
                                axis_is_moving = 0
                                TIMC.scan.pause_scan()
                            elif self._is_paused:
                                axis_is_moving = 0
                            else:
                                index_status = int(TIMC.acmd("SCAN", "AXISSTATUS(" + self.indexName + ")"))
                                index_in_pos = 0b100 & index_status
                                if index_in_pos and not self._is_paused:
                                    print("DONE.")
                                    axis_is_moving = 0
                                    self.j += 1
                                else:
                                    time.sleep(SCAN_THREAD_WAIT)

            else:
                messagebox.showinfo("", "Scan is Complete")
                TIMC.scan.stop_scan()

    # Scan Thread Stop Function
    def stop(self):
        self._is_running = 0
        self._is_paused = 1
        TIMC.acmd("SCAN", "ABORT " + self.scanName)
        TIMC.acmd("SCAN", "ABORT " + self.indexName)
        # Create a log entry
        TIMC.acmd("LOG", "LOG SCAN STOPPED \n")
        TIMC.fault.update_status("SCAN STOPPED")

    # Scan Thread Pause Function
    def pause(self):
        self._is_paused = 1
        self._just_paused = 1
        TIMC.acmd("SCAN", "ABORT " + self.scanName)
        TIMC.acmd("SCAN", "ABORT " + self.indexName)
        # Create a log entry
        TIMC.acmd("LOG", "LOG SCAN PAUSED \n")
        TIMC.fault.update_status("SCAN PAUSED")

    # Scan Thread Resume Function
    def resume(self):
        # Find current positions
        new_axis1_pos = round(float(TIMC.axis1.position.get()), 2)
        new_axis2_pos = round(float(TIMC.axis2.position.get()), 2)

        # Get new scan speeds and positions depending on which axis is scan axis
        if self.scanName == TIMC.axis1.axisName:
            self.scanSpeed = TIMC.scan.vel1.get()
            self.indexSpeed = TIMC.scan.vel2.get()
            scan_pos0 = self.axis1_position
            index_pos0 = self.axis2_position
            scan_pos1 = new_axis1_pos
            index_pos1 = new_axis2_pos
        else:
            self.scanSpeed = TIMC.scan.vel2.get()
            self.indexSpeed = TIMC.scan.vel1.get()
            scan_pos0 = self.axis2_position
            index_pos0 = self.axis1_position
            scan_pos1 = new_axis2_pos
            index_pos1 = new_axis1_pos

        # If both axes moved, go back to previous scan point
        if scan_pos0 != scan_pos1 and index_pos0 != index_pos1:
            if self.j > 0:
                self.i -= 1
                self.j -= 1
            else:
                self.i -= 1

        # If only scan axis moved
        elif scan_pos0 != scan_pos1:
            if self.i == self.j:    # Scan axis was moving or about to move
                if self.scan_start <= scan_pos1 <= self.scan_stop or self.i == 0:
                    pass            # Scan axis is still within scan profile or it was making its initial move
                else:
                    self.i -= 1     # Go back to previous scan point
                    self.j -= 1     # Index is in position but j cannot be > i
            else:                   # Index axis was moving or about to move and operator drove scan axis
                self.i -= 1         # Go back to previous scan point
                self.j -= 1

        # If only index axis moved (Not concerned if in the profile since indexes are small and logic would be hard to code using scan_points array)
        elif index_pos0 != index_pos1:
            # Uni-directional
            if self.scan_type == 1:
                self.i = self.i - self.i % 3            # Go back to an earlier scan point that is a product of 3
                self.j = self.i
            # Bi-directional
            else:
                self.i -= 1  # Go back to previous scan point
                self.j -= 1

        self.calc_scan_time(self.i, self.j)
        self._is_paused = 0
        # Create a log entry
        TIMC.acmd("LOG", "LOG SCAN RESUMED \n")
        TIMC.fault.clear_status()

    # This function calculates the total scan time based on scan points and wait time
    def calc_scan_time(self, start_i, start_j):
        self.scan_time = 0
        # Get current position
        scan_position = round(float(TIMC.acmd("SCAN", "PFBKPROG(" + self.scanName + ")")), 2)
        index_position = round(float(TIMC.acmd("SCAN", "PFBKPROG(" + self.indexName + ")")), 2)

        if start_i < len(self.scan_points):
            # Time to move from current scan position
            scan_distance = self.scan_points[start_i][0] - scan_position
            self.scan_time += (abs(scan_distance / self.scanSpeed))
            # Time for remaining scan moves
            for i in range(start_i + 1, len(self.scan_points)):
                scan_distance = self.scan_points[i][0] - self.scan_points[i - 1][0]
                self.scan_time += (abs(scan_distance / self.scanSpeed))

        if start_j < len(self.scan_points):
            # Time to move from current index position
            index_distance = self.scan_points[start_j][1] - index_position
            self.scan_time += (abs(index_distance / self.indexSpeed))
            # Time for remaining index moves
            for j in range(start_j + 1, len(self.scan_points)):
                index_distance = self.scan_points[j][1] - self.scan_points[j - 1][1]
                self.scan_time += abs(index_distance / self.indexSpeed)

        hours = int(self.scan_time / 3600)
        mins = int((self.scan_time - (hours * 3600)) / 60)
        seconds = int(self.scan_time - hours * 3600 - mins * 60)
        TIMC.scan.scanTimeText.set(str(hours).zfill(2) + ":" + str(mins).zfill(2) + ":" + str(seconds).zfill(2))


# Thread will assess if a fault has occurred and call the appropriate methods to change the state of the GUI
class UpdateStatus(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self._is_running = 1

        # Aerotech defines a bit mapped variable for the type of fault, BIT
        self.fault_array = ["PositionError Fault",                      # 0
                            "OverCurrent Fault",                        # 1
                            "CW/Positive End-of-Travel Limit Fault",    # 2
                            "CCW/Negative End-of-Travel Limit Fault",   # 3
                            "CW/High Software Limit Fault",             # 4
                            "CCW/Low Software Limit Fault",             # 5
                            "Amplifier Fault",                          # 6
                            "Position Feedback Fault",                  # 7
                            "Velocity Feedback Fault",                  # 8
                            "Hall Sensor Fault",                        # 9
                            "Maximum Velocity Command Fault",           # 10
                            "Emergency Stop Fault",                     # 11
                            "Velocity Error Fault",                     # 12
                            "N/A",                                      # 13
                            "N/A",                                      # 14
                            "External Fault",                           # 15
                            "N/A",                                      # 16
                            "Motor Temperature Fault",                  # 17
                            "Amplifier Temperature Fault",              # 18
                            "Encoder Fault",                            # 19
                            "Communication Lost Fault",                 # 20
                            "N/A",                                      # 21
                            "N/A",                                      # 22
                            "Feedback Scaling Fault",                   # 23
                            "Marker Search Fault",                      # 24
                            "N/A",                                      # 25
                            "N/A",                                      # 26
                            "Voltage Clamp Fault",                      # 27
                            "Power Supply Fault"                        # 28
                            ]

    def run(self):
        while self._is_running:
            time.sleep(STATUS_THREAD_WAIT)
            if TIMC.online:
                s_fault = int(TIMC.acmd("STATUS", "AXISFAULT (" + TIMC.axis1.axisName + ")"))
                p_fault = int(TIMC.acmd("STATUS", "AXISFAULT (" + TIMC.axis2.axisName + ")"))

                # Bitwise AND the fault data with a mask to check specifically for ESTOP
                if 0b100000000000 & s_fault or 0b100000000000 & p_fault:
                    TIMC.fault.fault_status("ESTOP was pressed")
                    TIMC.axis1.disable_axis()
                    TIMC.axis2.disable_axis()

                else:
                    faultMask = 1
                    # If there is a fault and axis 1 is not yet disabled
                    if s_fault != 0:
                        if TIMC.axis1.state:
                            TIMC.axis1.disable_axis()
                        # Create fault masks to bitwise AND the data to determine which type of fault has occurred.
                        for i in range(0, len(self.fault_array)):
                            if (s_fault & (faultMask << i)) != 0:
                                TIMC.fault.fault_status("FAULT: " + TIMC.axis1.axisName + " " + str(self.fault_array[i]))

                    # If there is a fault and axis 2 is not yet disabled
                    if p_fault != 0:
                        if TIMC.axis2.state:
                            TIMC.axis2.disable_axis()
                        # Create fault masks to bitwise AND the data to determine which type of fault has occurred.
                        for i in range(0, len(self.fault_array)):
                            if (p_fault & (faultMask << i)) != 0:
                                TIMC.fault.fault_status("FAULT: " + TIMC.axis2.axisName + " " + str(self.fault_array[i]))

    def stop(self):
        self._is_running = 0


# Thread to update the feedback on the GUI. The thread always loads commands into the feedback write queue
# and the feedback read queue is synced to the write queue to update the appropriate feedback variable on the GUI
class UpdateFeedback(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self._is_running = 1
        self.write_index = 0    # Variable to sync read and write queue
        self.read_index = 0     # Variable to sync read and write queue

        # Array of text which are ASCII commands compatible with the Aerotech drive
        self.write_cmd = ["PFBKPROG(" + TIMC.axis1.axisName + ")", "IFBK(" + TIMC.axis1.axisName + ")",
                          "VFBK(" + TIMC.axis1.axisName + ")", "PERR(" + TIMC.axis1.axisName + ")",
                          "PFBKPROG(" + TIMC.axis2.axisName + ")", "IFBK(" + TIMC.axis2.axisName + ")",
                          "VFBK(" + TIMC.axis2.axisName + ")", "PERR(" + TIMC.axis2.axisName + ")"]

    def run(self):
        while self._is_running:
            time.sleep(THREAD_WAIT)
            # Auto-populate the feedback write queue with commands so the queue is never empty
            # As write_index is indexed through the write_cmd array, the read_index is used to put the data returned

            if TIMC.qFBK_read.qsize() and TIMC.online:
                data = TIMC.qFBK_read.get()
                data = data.replace("%", "")
                if self.read_index == 0:
                    pos = round(float(data), 5)
                    TIMC.axis1.position.set(str(round(pos, decpl)))
                    self.read_index += 1
                elif self.read_index == 1:
                    cur = float(data)
                    TIMC.axis1.updateCurrent(cur)
                    self.read_index += 1
                elif self.read_index == 2:
                    vel = round(float(data), 5)
                    TIMC.axis1.velocity.set(str(round(vel, decpl)))
                    self.read_index += 1
                elif self.read_index == 3:
                    pos_err = float(data)
                    TIMC.axis1.updatePosErr(pos_err)
                    self.read_index += 1
                elif self.read_index == 4:
                    pos = round(float(data), 5)
                    TIMC.axis2.position.set(str(round(pos, decpl)))
                    self.read_index += 1
                elif self.read_index == 5:
                    cur = float(data)
                    TIMC.axis2.updateCurrent(cur)
                    self.read_index += 1
                elif self.read_index == 6:
                    vel = round(float(data), 5)
                    TIMC.axis2.velocity.set(str(round(vel, decpl)))
                    self.read_index += 1
                elif self.read_index == 7:
                    pos_err = float(data)
                    TIMC.axis2.updatePosErr(pos_err)
                    self.read_index = 0

            if TIMC.qFBK_write.qsize() == 0 and TIMC.online:
                TIMC.qFBK_write.put(self.write_cmd[self.write_index])
                if self.write_index < len(self.write_cmd) - 1:
                    self.write_index += 1
                else:
                    self.write_index = 0

    def stop(self):
        self._is_running = 0


# Thread to updated the log file. All commands send to the Aerotech drive are sent to this thread
# which decides what information to keep
class UpdateLog(threading.Thread):
    def __init__(self, log_queue, fault_array):
        threading.Thread.__init__(self)
        self._is_running = 1
        self.fault_flag = 0
        self.queue = log_queue
        self.fault_array = fault_array

        # Create log file with date and time as apart of the file name
        text = "PIPING_LOG_" + str(time.strftime("%Y-%m-%d__%H-%M-%S", time.localtime())) + ".txt"
        self.file = open(text, "w+")
        self.print_header()

        # Set variable to monitor if day has changed
        now = datetime.datetime.now()
        self.day = now.day

    def run(self):
        while self._is_running:
            time.sleep(THREAD_WAIT)
            if self.queue.qsize():
                # Remove unnecessary text from the command
                data = self.queue.get()
                data = data.replace("b'", "")
                data = data.replace("\n", "")
                data = data.replace("\\n", "")
                data = data.replace("%", "")
                data = data.replace("#", "")
                data = data.replace("!", "")
                data = data.replace("'", "")

                # "STAT:" has information about ESTOP or Faults, save this data if there is a fault
                if "STAT:" in data:
                    data = data.replace("STAT:", "")
                    if TIMC.axis1.axisName in data:
                        data = int(data.replace("AXISFAULT (" + TIMC.axis1.axisName + ")", ""))

                        # If there is a fault data will be a number other than 0
                        if data and self.fault_flag == 0:
                            # Check which type of fault occurred with Bitwise AND and a fault mask
                            for i in range(0, len(self.fault_array)):
                                faultMask = 1
                                if data & (faultMask << i) != 0:
                                    self.fault_flag = 1
                                    if i == 11:
                                        self.file.write(self.pt() + "ESTOP Pressed\n")
                                    else:
                                        self.file.write(self.pt() + "FAULT: " + TIMC.axis1.axisName + " " + str(self.fault_array[i]) + '\n')

                    elif TIMC.axis2.axisName in data:
                        data = int(data.replace("AXISFAULT (" + TIMC.axis2.axisName + ")", ""))
                        # If there is a fault data will be a number other than 0
                        if data and self.fault_flag == 0:
                            # Check which type of fault occurred with Bitwise AND and a fault mask
                            for i in range(0, len(self.fault_array)):
                                faultMask = 1
                                if data & (faultMask << i) != 0:
                                    self.fault_flag = 1
                                    if i == 11:
                                        self.file.write(self.pt() + "ESTOP Pressed\n")
                                    else:
                                        self.file.write(self.pt() + "FAULT: " + TIMC.axis2.axisName + " " + str(self.fault_array[i]) + '\n')
                # CTRL: has information about buttons pressed in the axisframe, but filter out data about AXISSTATUS
                elif "CTRL:" in data and not "STATUS" in data and not "ABORT" in data:
                    if "ACKNOWLEDGEALL" in data:
                        self.file.write(self.pt() + "ACKNOWLEDGEALL\n")
                        self.fault_flag = 0
                    else:
                        self.file.write(self.pt() + data + '\n')
                elif "SCAN:" in data and not "STATUS" in data and not "ABORT" in data:
                    if "ACKNOWLEDGEALL" in data:
                        self.file.write(self.pt() + "ACKNOWLEDGEALL\n")
                        self.fault_flag = 0
                    else:
                        self.file.write(self.pt() + data + '\n')
                elif "LOG" in data:
                    self.file.write(self.pt() + data + '\n')

    def stop(self):
        self._is_running = 0
        time.sleep(0.5)
        self.file.close()

    # Method to print the time
    def pt(self):
        # Check if the day has changed
        now = datetime.datetime.now()
        if self.day != now.day:
            self.new_day()      # Insert a new day into the log file
            self.day = now.day  # Update current day
        # Return the time for the log entry
        result = time.strftime("%H:%M:%S ", time.localtime())
        return result

    # Header at the beginning of the log file
    def print_header(self):
        self.file.write("===============================================================\n")
        self.file.write("          Tooling Inspection Motion Controller - PIPING          \n")
        self.file.write("                       Code Revision: 0                        \n")
        self.file.write("                         - LOG FILE -                          \n")
        self.file.write("===============================================================\n")
        self.file.write("Controller Initialized:\n")
        self.file.write("    Date: " + time.strftime("%Y-%m-%d", time.localtime()) + '\n')
        self.file.write("    Time: " + time.strftime("%H:%M:%S", time.localtime()) + '\n')
        self.file.write("    COM Port: \n")
        self.file.write("    File: " + sys.argv[0] + "\n\n")
        self.file.write("Tool Info:\n")
        self.file.write("   " + TIMC.tool.toolName + '\n')
        self.file.write("   Axis Parameters: (Position Error Limit, Current Limit, Max Speed, Counts/Unit, Motor Type)\n")
        self.file.write("   Axis 1: " + TIMC.axis1.parm_output_list[0] + ", " + TIMC.axis1.parm_output_list[1] + ", " +
                        TIMC.axis1.parm_output_list[2] + ", " + TIMC.axis1.parm_output_list[4] + ", " + TIMC.axis1.parm_output_list[5] + '\n')
        self.file.write("   Axis 2: " + TIMC.axis2.parm_output_list[0] + ", " + TIMC.axis2.parm_output_list[1] + ", " +
                        TIMC.axis2.parm_output_list[2] + ", " + TIMC.axis2.parm_output_list[4] + ", " + TIMC.axis2.parm_output_list[5] + '\n')
        self.file.write("Computer Information:\n")
        self.file.write("    Computer Name: " + platform.node() + "\n")
        self.file.write("    Platform: " + platform.platform() + "\n")
        self.file.write("    Processor: " + platform.processor() + "\n")
        self.file.write("    Version: " + platform.version() + "\n")
        self.file.write("\n\nRECORDED EVENTS\n")
        self.file.write("===============================================================\n")

    # Print in the log file a new day
    def new_day(self):
        self.file.write("\n")
        self.file.write("===============================================================\n")
        self.file.write("\t\t\t" + time.strftime("%Y-%m-%d", time.localtime()) + "\n")
        self.file.write("===============================================================\n\n")


# Thread to Reset the controller
class ResetThread(threading.Thread):
    def __init__(self, option):
        threading.Thread.__init__(self)
        self._is_running = 1
        self.option = option

    def run(self):
        axis1_position = "0.0"
        axis2_position = "0.0"
        if TIMC.online:
            # abort any motion
            TIMC.axis1.abort_axis()
            TIMC.axis2.abort_axis()

            # disable both axes
            TIMC.axis1.disable_axis()
            TIMC.axis2.disable_axis()

            # Stop all processes
            TIMC.online = 0
            time.sleep(0.5)
            TIMC.process_serial.stop()
            TIMC.process_status.stop()
            TIMC.process_feedback.stop()

            # Disable Program Menu Buttons
            TIMC.menu.deactivate_param_btns()
            TIMC.axis1.enableButton.config(state="disabled")
            TIMC.axis2.enableButton.config(state="disabled")

        while self._is_running:
            # Option 1 = COMMIT PARAMETERS
            if self.option == 1:
                TIMC.fault.update_status("SAVING AND COMMITTING PARAMETERS...")
                result = find_port()
                s = serial.Serial(result[0], baud, timeout=0.05)
                s.write("COMMITPARAMETERS".encode('ascii') + b' \n')
                time.sleep(.5)
                s.close()

            # Option 0 = RESET CONTROLLER
            else:
                TIMC.fault.update_status("RESETTING CONTROLLER...")
                result = find_port()
                s = serial.Serial(result[0], baud, timeout=0.05)

                # Get current position before reset
                command = "PFBKPROG(" + TIMC.axis1.axisName + ")"
                s.write(command.encode('ascii') + b' \n')
                data = s.readline().decode('ascii')
                axis1_position = data.replace("%", "")
                command = "PFBKPROG(" + TIMC.axis2.axisName + ")"
                s.write(command.encode('ascii') + b' \n')
                data = s.readline().decode('ascii')
                axis2_position = data.replace("%", "")

                time.sleep(.5)
                s.write("RESET".encode('ascii') + b' \n')
                time.sleep(.5)

                s.close()

            while TIMC.online == 0:
                s = serial.Serial(result[0], baud, timeout=0.05)
                # Send a command to check if communication has been established
                s.write("ACKNOWLEDGEALL".encode('ascii') + b' \n')
                data = s.readline().decode('ascii')
                if '%' in data:
                    TIMC.online = 1
                s.close()

            if self.option == 1:
                TIMC.online = 0
                self.option = 0     # Go back through and reset

            else:
                TIMC.start_serial()
                if TIMC.online:
                    if TIMC.menu.axis1_dir_change:
                        axis1_position = str(-(float(axis1_position)))
                        TIMC.menu.axis1_dir_change = 0
                    if TIMC.menu.axis2_dir_change:
                        axis2_position = str(-(float(axis2_position)))
                        TIMC.menu.axis2_dir_change = 0
                    TIMC.acmd("CTRL", "POSOFFSET SET " + TIMC.axis1.axisName + ", " + axis1_position)
                    TIMC.acmd("CTRL", "POSOFFSET SET " + TIMC.axis2.axisName + ", " + axis2_position)
                if TIMC.menu.open:
                    for i in range(0, 5):
                        TIMC.menu.axis1entry[i].delete(0, END)
                        TIMC.menu.axis1entry[i].insert(0, TIMC.axis1.parm_output_list[i])
                        TIMC.menu.axis2entry[i].delete(0, END)
                        TIMC.menu.axis2entry[i].insert(0, TIMC.axis2.parm_output_list[i])
                    TIMC.menu.axis1_dir.set(int(TIMC.axis1.parm_output_list[6]))
                    TIMC.menu.axis2_dir.set(int(TIMC.axis2.parm_output_list[6]))
                    TIMC.menu.activate_param_btns()
                TIMC.fault.update_status("COMPLETE")
                print("COMPLETE")
                time.sleep(.5)
                TIMC.fault.clear_status()
                TIMC.start_status_and_feedback()
                TIMC.axis1.enableButton.config(state="normal")
                TIMC.axis2.enableButton.config(state="normal")
                self._is_running = 0

    def stop(self):
        self._is_running = 0


# This class displays the menu bar and handles commands associated with menu items
class ProgramMenu:
    def __init__(self, master):
        menu_bar = Menu(master)
        master.config(menu=menu_bar)
        menu_bar.add_command(label="Parameters", command=lambda: self.openParameters())
        self.axis1_dir = IntVar()
        self.axis2_dir = IntVar()
        self.axis1_dir_change = IntVar(0)
        self.axis2_dir_change = IntVar(0)
        self.axis1entry = []
        self.axis2entry = []
        self.open = IntVar(0)

    # Open a new window and display parameters that are used in the TIMC Program
    def openParameters(self):
        self.queue = "CTRL"
        self.open = 1
        self.parameter_window = Toplevel(root)
        self.parameter_window.focus()
        self.parameter_window.grab_set()
        self.parameter_window.protocol("WM_DELETE_WINDOW", self.param_on_closing)

        w = 500
        h = 350
        x = TIMC.x + (TIMC.w - w)/2
        y = TIMC.y + (TIMC.h - h)/2

        self.parameter_window.geometry("%dx%d+%d+%d" % (w, h, x, y))
        self.parameter_window.resizable(width=False, height=False)
        self.parameter_window.state("normal")

        self.parameter_frame = Frame(self.parameter_window)
        self.parameter_frame.pack()
        self.bottom_frame = Frame(self.parameter_window)
        self.bottom_frame.pack()
        tool_label = Label(self.parameter_frame, text=TIMC.tool.toolName, width=30, font="Helvetica, 18")
        axis1label = Label(self.parameter_frame, text=TIMC.axis1.axisName, width=12, font="Helvetica, 12 bold")
        axis2label = Label(self.parameter_frame, text=TIMC.axis2.axisName, width=12, font="Helvetica, 12 bold")
        tool_label.grid(column=0, row=0, columnspan=3, pady=2)
        axis1label.grid(column=1, row=1, padx=5, pady=2)
        axis2label.grid(column=2, row=1, padx=5, pady=2)

        param_labels = ["Position Error Threshold (" + TIMC.axis1.axisUnits + ")", "Max Current Clamp (A)", "Max Jog Speed (" + TIMC.axis1.axisUnits + "/s", "Units", "Counts per Unit"]
        axis_labels = []
        self.axis1entry.clear()
        self.axis2entry.clear()
        axis_labels.clear()

        # Entry Boxes - create and populate with parameters
        for i in range(0, 5):
            axis_labels.append(Label(self.parameter_frame, text=param_labels[i], font="Helvetica, 10"))
            self.axis1entry.append(Entry(self.parameter_frame, width=10, font='Helvetica, 10', justify='center'))
            self.axis1entry[i].insert(0, TIMC.axis1.parm_output_list[i])
            self.axis2entry.append(Entry(self.parameter_frame, width=10, font='Helvetica, 10', justify='center'))
            self.axis2entry[i].insert(0, TIMC.axis2.parm_output_list[i])
            axis_labels[i].grid(column=0, row=i + 2, pady=2, sticky=E)
            self.axis1entry[i].grid(column=1, row=i + 2, pady=2)
            self.axis2entry[i].grid(column=2, row=i + 2, pady=2)
            if i < 4:
                self.axis1entry[i].config(state="readonly")
                self.axis2entry[i].config(state="readonly")

        # Motor Direction Check Boxes
        direction_label = Label(self.parameter_frame, text="Reverse Positive Direction", font="Helvetica, 10")
        direction_label.grid(column=0, row=12, pady=4, sticky=E)
        self.axis1_dir_box = Checkbutton(self.parameter_frame, variable=self.axis1_dir)
        self.axis1_dir_box.grid(column=1, row=12)
        self.axis1_dir.set(int(TIMC.axis1.parm_output_list[6]))
        self.axis2_dir_box = Checkbutton(self.parameter_frame, variable=self.axis2_dir)
        self.axis2_dir_box.grid(column=2, row=12)
        self.axis2_dir.set(int(TIMC.axis2.parm_output_list[6]))

        # Save/Commit and Reset Buttons
        self.save_btn = Button(self.bottom_frame, text="COMMIT AND RESET", width=20, bg="Light Blue", font="Helvetica, 10 bold",
                               command=lambda: self.save_parameters())
        self.reset_btn = Button(self.bottom_frame, text="RESET", width=15, bg="Light Green", font="Helvetica, 10 bold",
                                command=lambda: self.reset_controller())

        self.save_btn.grid(column=0, row=0, padx=30, pady=10)
        self.reset_btn.grid(column=0, row=1, padx=30, pady=10)

        # This will save and commit new parameters

    def save_parameters(self):
        new_param = 0
        # Get Entry Values and Compare to Initial Entry Values
        # If values have changed and TIMC is online, use SETPARM to set the new value
        # then start the Reset thread to first Commit the new parameters the Reset the controller

        axis1_new_parm_output_list = []
        axis1_new_parm_output_list.clear()
        axis2_new_parm_output_list = []
        axis2_new_parm_output_list.clear()

        for i in range(0, 5):
            axis1_new_parm_output_list.append(self.axis1entry[i].get())
            if TIMC.axis1.parm_output_list[i] != axis1_new_parm_output_list[i]:
                new_param = 1
                if TIMC.online:
                    TIMC.acmd(self.queue, "SETPARM " + TIMC.axis1.axisName + ", " + parm_num_list[i] + ", " +
                              axis1_new_parm_output_list[i])
                TIMC.axis1.parm_output_list[i] = axis1_new_parm_output_list[i]
            axis2_new_parm_output_list.append(self.axis2entry[i].get())
            if TIMC.axis2.parm_output_list[i] != axis2_new_parm_output_list[i]:
                new_param = 1
                if TIMC.online:
                    TIMC.acmd(self.queue, "SETPARM " + TIMC.axis2.axisName + ", " + parm_num_list[i] + ", " +
                              axis2_new_parm_output_list[i])
                TIMC.axis2.parm_output_list[i] = axis2_new_parm_output_list[i]

        # Check for change in Reverse Positive Motion parameter
        if self.axis1_dir.get() != int(TIMC.axis1.parm_output_list[6]):
            new_param = 1
            self.axis1_dir_change = 1
            if TIMC.online:
                TIMC.acmd(self.queue, "SETPARM " + TIMC.axis1.axisName + ", " + parm_num_list[6] + ", " + str(
                    self.axis1_dir.get()))
                TIMC.axis1.motorDirection = self.axis1_dir.get()
                TIMC.axis1.parm_output_list[6] = str(self.axis1_dir.get())

        if self.axis2_dir.get() != int(TIMC.axis2.parm_output_list[6]):
            new_param = 1
            self.axis2_dir_change = 1
            if TIMC.online:
                TIMC.acmd(self.queue, "SETPARM " + TIMC.axis2.axisName + ", " + parm_num_list[6] + ", " + str(
                    self.axis2_dir.get()))
                TIMC.axis2.motorDirection = self.axis2_dir.get()
                TIMC.axis2.parm_output_list[6] = str(self.axis2_dir.get())

        # If any parameters changed, start the Reset Thread with Option 1: Commit then Reset
        if new_param == 1 and TIMC.online:
            self.process_reset = ResetThread(1)
            self.process_reset.start()
        # If there are no new parameters do nothing
        else:
            messagebox.showinfo("Commit Error", "No New Parameters", parent=self.parameter_window)

    def reset_controller(self):
        # This button will start the Reset Thread with Option 0: Reset only
        if TIMC.online:
            self.process_reset = ResetThread(0)
            self.process_reset.start()

    def activate_param_btns(self):
        self.save_btn.config(state="normal", fg="Black", bg="Light Blue")
        self.reset_btn.config(state="normal", fg="Black", bg="Light Green")

    def deactivate_param_btns(self):
        self.save_btn.config(state="disabled", fg="Gray", bg="Light Blue")
        self.reset_btn.config(state="disabled", fg="Gray", bg="Light Green")

    def param_on_closing(self):
        self.open = 0
        self.parameter_window.destroy()


# This class is starts Main GUI Window and starts communication with controller
class Main:
    def __init__(self, master):
        self.master = master
        self.online = 0

        # Create Main GUI Window
        self.ws = self.master.winfo_screenwidth()
        self.hs = self.master.winfo_screenheight()
        self.w = 650
        self.h = 750
        self.x = self.ws*.8 - (self.w/2)
        self.y = (self.hs/2) - (self.h/2)
        master.geometry("%dx%d+%d+%d" % (self.w, self.h, self.x, self.y))
        master.title("R0: TIMC - Piping")
        master.resizable(width=False, height=False)
        print("Starting TIMC-PIPING Control")

        # Create Menu Heading
        self.menu = ProgramMenu(self.master)

        # Open Setup File
        self.params = str()
        self.filename = "TIMC-P-SETUP.txt"
        try:
            f = open(self.filename, "r+")
            self.params = f.readlines()
            f.close()
        except FileNotFoundError:
            print("Cannot Find Setup Text File: " + self.filename)
            print("Creating Default " + self.filename)
            f = open(self.filename, "w+")
            self.params = ["NOVA\n", "0\n", "50\n", "0\n", "100\n", "25\n", "Bidirectional\n", "axis1\n", "12.4", "12.4"]     # Default TIMC Parameters
            f.writelines(self.params)
            f.close()

        if self.params[0] == "NOVA\n":
            master.configure(background="Light Blue")
        else:
            master.configure(background="Light Goldenrod")

        # Determine if GUI should be started offline
        self.is_offline()

        # Setup GUI Frames
        self.tool = ToolFrame(self.master, self.params)
        self.axis1 = AxisFrame(self.master, SetupAxis1())
        self.axis2 = AxisFrame(self.master, SetupAxis2())
        self.scan = ScanFrame(self.master, self.axis1, self.axis2, self.params)
        self.fault = FaultFrame(self.master)

        # If online, check that Tool selected matches Motor Type in parameter file
        # NOVA Motor Type = 3 Stepper
        # LAPIS Motor Type = 2 DC Brush
        if self.online:
            if self.axis1.motorType == 2:
                self.params[0] = "LAPIS\n"
                self.tool.toolName = "LAPIS"
                self.axis1.motorMultiplier = -1     # LAPIS Translator direction is reversed
                self.tool.toolButton.config(text="LAPIS", bg="Goldenrod")
                master.configure(background="Light Goldenrod")
            if self.axis1.motorType == 3:
                self.params[0] = "NOVA\n"
                self.tool.toolName = "NOVA"
                self.tool.toolButton.config(text="NOVA", bg="Deep Sky Blue")
                master.configure(background="Light Blue")
        else:
            self.fault.update_status("OFFLINE MODE")

        self.start_serial()
        time.sleep(1.0)

    # Main method for sending commands to TIMC, command syntax specified by Aerotech: ASCII Commands
    def acmd(self, queue_name, text):
        if queue_name != "LOG":
            if queue_name == "CTRL":
                self.write_queue = self.qControl_write
                self.read_queue = self.qControl_read
            elif queue_name == "SCAN":
                self.write_queue = self.qScan_write
                self.read_queue = self.qScan_read
            elif queue_name == "STATUS":
                self.write_queue = self.qStatus_write
                self.read_queue = self.qStatus_read
            elif queue_name == "FBK":
                self.write_queue = self.qFBK_write
                self.read_queue = self.qFBK_read

            # Put command on the queue, process_serial sends the command and returns the result in the read queue
            self.write_queue.put(text)
            data = self.read_queue.get()

            # Aerotech drive sends back special characters in response to the command given
            if "!" in data:
                print("(!) Bad Execution, Queue:", queue_name, "CMD:", text)
                return 0
            elif "#" in data:
                print("(#) ACK but cannot execute, Queue:", queue_name, "CMD:", text)
                return 0
            elif "$" in data:
                print("($) CMD timeout, Queue:", queue_name, "CMD:", text)
                return 0
            elif data == "":
                print("No data returned, check serial connection, Queue:", queue_name, "CMD:", text)
                TIMC.process_serial.stop()
                TIMC.process_status.stop()
                TIMC.process_feedback.stop()
                return 0
            # If the command was successful, and the command sent requested data to the controller,
            # the "%" precedes the returned data
            elif "%" in data:
                data = data.replace("%", "")
                return data
            else:
                print("Unknown Error, Reboot System Suggested")
        # process_serial will transfer data from this queue to the main queue processed by process_log
        else:
            self.qLog_write2.put(text)

    # if communication is not successful then use Offline Mode
    def is_offline(self):
        self.online = 0
        result = find_port()
        if result:
            s = serial.Serial(result[0], baud, timeout=0.05)
            # Send a command to check if communication has been established
            s.write("ACKNOWLEDGEALL".encode('ascii') + b' \n')
            data = s.readline().decode('ascii')
            if '%' in data:
                self.online = 1
            s.close()

    def start_serial(self):
        # Setup Queue and Establish Serial Thread to Communicate with Ensemble
        self.qControl_read = queue.Queue()      # Results of the qControl_write commands recorded here
        self.qControl_write = queue.Queue()     # Jog, GoTo, Index, Set button press commands are sent to this queue
        self.qScan_read = queue.Queue()         # Results of the qScan_write commands recorded here
        self.qScan_write = queue.Queue()        # Commands from the scan thread are written to this queue
        self.qStatus_write = queue.Queue()      # Results of the qStatus_write commands recorded here
        self.qStatus_read = queue.Queue()       # Fault checking commands are sent to this queue
        self.qFBK_read = queue.Queue()          # Results of the qFBK_write commands recorded here
        self.qFBK_write = queue.Queue()         # Commands to update the feedback are sent to this queue
        self.write_queue = queue.Queue()
        self.read_queue = queue.Queue()
        self.qLog_write1 = queue.Queue()        # All commands are copied to this queue to be processed for the log file
        self.qLog_write2 = queue.Queue()        # Start, Stop, Pause, Resume button clicks recorded to this queue for the log file

        self.process_serial = SerialThread(self.qControl_read, self.qControl_write,
                                           self.qScan_read, self.qScan_write,
                                           self.qStatus_read, self.qStatus_write,
                                           self.qFBK_read, self.qFBK_write,
                                           self.qLog_write1, self.qLog_write2)
        self.process_serial.start()

    def start_status_and_feedback(self):
        # Start thread to updated position, current and error feedback for each axis
        self.process_feedback = UpdateFeedback()
        self.process_feedback.start()

        # Start thread to monitor for ESTOP and faults etc.
        self.process_status = UpdateStatus()
        self.process_status.start()


# This function checks to make sure user entered a usable number
def check_is_digit(text):
    if "-" in text:
        text = text.replace("-", "0")
    if "." in text:
        text = text.replace(".", "0")
    if text.isdigit():
        if float(text) > 9999:
            messagebox.showinfo("Bad Input", "Value exceeds display limits")
            return False
        else:
            return True
    else:
        messagebox.showinfo("Bad Input", "Value is not a number")
        return False


# This function opens a serial communication and gets parameters off of the Ensemble and returns them in an array
# Parameter Numbers are found in C:\Program Files (x86)\Aerotech\Ensemble\Samples\Cpp\ASCII\OperatorInterface\Win\Parameters.h
# List is created at beginning of code
def getparams(axisName):
    # Open Communication and Get Parameters from Ensemble
    parm_output_list = []
    port_open = 0
    result = find_port()
    if result:
        s = serial.Serial(result[0], baud, timeout=0.05)
        for i in parm_num_list:
            command = ("GETPARM(" + axisName + ", " + i + ")")
            s.write(command.encode('ascii') + b' \n')
            data = s.readline().decode('ascii')
            if "%" in data:
                port_open = 1
                data = data.replace("%", " ")
                parm_output_list.append(str(data.strip()))
        s.close()

    if port_open == 0:
        # Use this list if TIMC is offline
        parm_output_list = [2, 5, 25, "mm", 250, 2, 1]

    return parm_output_list


# This function tests 100 ports to find out which one to use and returns that port in "result"
def find_port():
    ports = ['COM%s' % (i + 1) for i in range(100)]
    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    if len(result) == 1:
        return result


# This function executes when window is closed and attempts to close all threads and overwrite settings file
def on_closing():
    print("Closing")
    exception_flag = 0

    if TIMC.online:
        print("Disconnecting...")
        TIMC.axis1.disable_axis()   # Disable Axis 1
        TIMC.axis2.disable_axis()   # Disable Axis 2

        TIMC.online = 0
        time.sleep(0.25)
        try:
            process_log.stop()
        except:
            exception_flag = 2
        try:
            TIMC.process_status.stop()
            print("Status Process Stop")
        except:
            exception_flag = 3
        try:
            TIMC.process_feedback.stop()
            print("Feedback Process Stop")
        except:
            exception_flag = 4
        try:
            time.sleep(0.5)
            TIMC.process_serial.stop()
            print("Serial Comm Process Stop")
        except:
            exception_flag = 5

    if exception_flag > 0:
        print("ERROR CLOSING A THREAD " + str(exception_flag))
    else:
        print("All Threads Closed")

    # Overwrite setup file with parameters to include any changes during program execution
    # To add addtional items to this setup file, they must be strings, and you must add the indices and default values
    # to the default setup array in "Main"
    try:
        new_f = open(TIMC.filename, "r+")
        new_f.close()
        new_f = open(TIMC.filename, "w+")
        TIMC.params[1] = TIMC.scan.e_scanStart.get() + "\n"
        TIMC.params[2] = TIMC.scan.e_scanStop.get() + "\n"
        TIMC.params[3] = TIMC.scan.e_indexStart.get() + "\n"
        TIMC.params[4] = TIMC.scan.e_indexStop.get() + "\n"
        TIMC.params[5] = TIMC.scan.e_indexSize.get() + "\n"
        TIMC.params[6] = TIMC.scan.scanTypeVar.get() + "\n"
        if TIMC.scan.scanConfigVar.get() == TIMC.axis1.axisName:
            TIMC.params[7] = "axis1\n"
        else:
            TIMC.params[7] = "axis2\n"
        TIMC.params[8] = str(TIMC.scan.vel1.get()) + "\n"
        TIMC.params[9] = str(TIMC.scan.vel2.get()) + "\n"

        new_f.writelines(TIMC.params)
        new_f.close()
    except:
        print("Error writing to setup file")

    root.destroy()


root = Tk()
TIMC = Main(root)
if TIMC.online:
    # If axis are enabled at startup, disabled them
    TIMC.axis1.disable_axis()
    TIMC.axis2.disable_axis()

    TIMC.start_status_and_feedback()

    # Start thread for generating log file
    process_log = UpdateLog(TIMC.qLog_write1, TIMC.process_status.fault_array)
    process_log.start()

root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()
