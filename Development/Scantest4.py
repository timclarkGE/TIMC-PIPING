"""
This program is beginning of the piping GUI, it creates 2 Axis frames, a Scan Frame, and a Fault Frame

It communicates with the Aerotech Controller and sets up a queue thread for Control Commands Enable and Jog only

Ability to read in text file to set to last used tool configuration

Scan button logic complete - No scan commands

Updated to allow for Jog, GOTO, Move Inc, Set To Moves/Commands

Changed feedback queue to use acmd rather than directly to Serial Thread

Implemented fault status thread and fault handling
"""

from tkinter import *
from tkinter import messagebox
import serial
import threading
import time
import queue


# This class sets Frame parameters for the Circ Axis
class SetupAxis1:
    def __init__(self):
        self.axisName = "CIRC"
        self.axisUnits = "mm"
        self.jogText1 = "CCW"
        self.jogText2 = "CW"
        self.speedMin = 0.1
        self.speedMax = 25.0
        self.speedRes = .5
        self.currentLimit = 5
        self.posErrLimit = 2
        self.queue_name = "CTRL"


# This class sets Frame parameters for the Trans Axis
class SetupAxis2:
    def __init__(self):
        self.axisName = "TRANSLATOR"
        self.axisUnits = "mm"
        self.jogText1 = "IN"
        self.jogText2 = "OUT"
        self.speedMin = 0.1
        self.speedMax = 50.0
        self.speedRes = .5
        self.currentLimit = 5
        self.posErrLimit = 2
        self.queue_name = "CTRL"


# This class places a button on the top of the GUI to select between LAPIS and NOVA
class ToolFrame:
    def __init__(self, master, params):
        self.tool = params
        topFrame = Frame(master, relief=SUNKEN, border=2)
        topFrame.pack(fill=X, padx=10, pady=10)
        self.toolButton = Button(topFrame, text="NOVA", fg="Black", bg="Sky Blue", font=("Helvetica", 14),
                                 command=lambda: self.toggle_tool())

        # Read in first parameter from TIMC setup file list to determine last configuration
        if self.tool[0] == "LPS-1000\n":
            self.toolButton.config(text="LPS-1000", fg="Black", bg="Goldenrod")
        elif self.tool[0] == "NOVA\n":
            self.toolButton.config(text="NOVA", fg="Black", bg="Sky Blue")
        self.toolButton.pack(fill=X)

    # Toggle tool between LAPIS and NOVA, overwrite setup file list
    def toggle_tool(self):
        if self.toolButton["text"] == "NOVA":
            self.toolButton.config(text="LPS-1000", fg="Black", bg="Goldenrod")
            self.tool[0] = "LPS-1000\n"
            TIMC.params = self.tool
        else:
            self.toolButton.config(text="NOVA", fg="Black", bg="Sky Blue")
            self.tool[0] = "NOVA\n"
            TIMC.params = self.tool


# This class pulls parameters from the specific axis and puts them in the GUI
class AxisFrame:
    def __init__(self, master, parameters):
        self.axisName = parameters.axisName
        self.axisUnits = parameters.axisUnits
        self.jogText1 = parameters.jogText1
        self.jogText2 = parameters.jogText2
        self.speedMin = parameters.speedMin
        self.speedMax = parameters.speedMax
        self.speedRes = parameters.speedRes
        self.currentLimit = parameters.currentLimit
        self.posErrLimit = parameters.posErrLimit
        self.queue = parameters.queue_name

        self.state = 0  # Flag for Enabled/Disabled Axis

        self.frame = Frame(master, relief=SUNKEN, border=2)
        self.frame.pack(fill=X, padx=10, pady=5)

        self.position = float(0)
        self.current = float(0)
        self.velocity = float(0)
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
        self.label_1 = Label(self.pos_frame, text=self.axisUnits, fg="Gray", bg="White", font="Helvetica, 20 bold")
        self.label_2 = Label(self.pos_frame, text="Velocity", font=("Helvetica", 8), bg="White")
        self.label_3 = Label(self.pos_frame, text=(self.axisUnits + "/s"), font=("Helvetica", 8), bg="White")
        self.label_4 = Label(self.button_frame,  text=("Speed (" + self.axisUnits + "/s)"), font=("Helvetica", 10))
        self.label_5 = Label(self.error_frame, text="Pos Err", font=("Helvetica", 8))
        self.label_6 = Label(self.error_frame, text="Current", font=("Helvetica", 8))

        # Buttons
        self.enableButton = Button(self.frame, text="OFF", fg="Red", bg="Light Grey", height=1, width=8,
                                   command=lambda: self.toggle_axis(), font="Helvetica, 12 bold")
        self.setToButton = Button(self.button_frame, text="SET TO:", fg="Gray", bg="Light Grey", height=1, width=10,
                                  state="disabled", command=lambda: self.setTo(1))
        self.GoToButton = Button(self.button_frame, text="GO TO:", fg="Gray", bg="Light Grey", height=1, width=10,
                                 state="disabled",
                                 command=lambda: self.GoTo(1))
        self.moveIncButton = Button(self.button_frame, text="MOVE INC:", fg="Gray", bg="Light Grey", height=1, width=10,
                                    state="disabled", command=lambda: self.moveInc())
        self.setToZero = Button(self.button_frame, text="Set To 0", fg="Gray", bg="Light Grey", height=1,
                                      state="disabled", command=lambda: self.setTo(0))
        self.GoToZero = Button(self.button_frame, text="Go To 0", fg="Gray", bg="Light Grey", height=1,
                                state="disabled", command=lambda: self.GoTo(0))
        self.jogButtonFWD = Button(self.frame, text="Jog " + self.jogText1, fg="Gray", bg="Light Grey", height=1, width=10,
                                   font="Helvetica, 12 bold", state="disabled")
        self.jogButtonREV = Button(self.frame, text="Jog " + self.jogText2, fg="Gray", bg="Light Grey", height=1, width=10,
                                   font="Helvetica, 12 bold", state="disabled")

        # Feedback Labels and Entry Boxes
        self.position_box = Label(self.pos_frame, text=("%.2f" % self.position), fg="Gray", bg="White", width=6, anchor=E, font="Helvetica, 26 bold")
        self.velocity_box = Label(self.pos_frame, text=("%.1f" % self.velocity), bg="White", width=8, state="disabled", font=("Helvetica", 8))
        self.setToEntry = Entry(self.button_frame, textvariable=self.setToText, width=10, font=("Helvetica", 10), justify="center")
        self.GoToEntry = Entry(self.button_frame, textvariable=self.GoToText, width=10, font=("Helvetica", 10), justify="center")
        self.moveIncEntry = Entry(self.button_frame, textvariable=self.moveIncText, width=10, font=("Helvetica", 10),
                                  justify="center")

        # Velocity Scale
        self.vel = Scale(self.frame, from_=self.speedMin, to=self.speedMax, orient=HORIZONTAL, length=200, resolution=self.speedRes, troughcolor="White")
        self.vel.set((self.speedMax - self.speedMin) * 0.5)

        # Jog Button Actions
        self.jogButtonFWD.bind('<ButtonPress-1>', lambda event: self.jogFWD())
        self.jogButtonFWD.bind('<ButtonRelease-1>', lambda event: self.stopjog())
        self.jogButtonREV.bind('<ButtonPress-1>', lambda event: self.jogREV())
        self.jogButtonREV.bind('<ButtonRelease-1>', lambda event: self.stopjog())

        # Grid Widgets
        self.label_0.grid(column=0, row=0, columnspan=2, pady=5, sticky=W)
        self.pos_frame.grid(column=0, row=1, rowspan=3, padx=5, sticky=N)
        self.position_box.grid(column=0, row=0, columnspan=2, pady=5)
        self.label_1.grid(column=2, row=0, padx=2, pady=5, sticky=W)    # Units
        self.label_2.grid(column=0, row=1, pady=2, sticky=E)            # Velocity
        self.velocity_box.grid(column=1, row=1)
        self.label_3.grid(column=2, row=1, pady=2, sticky=W)            # Units/s
        self.enableButton.grid(column=0, row=4, rowspan=1, padx=5, sticky=N)

        self.button_frame.grid(column=1, row=0, rowspan=3, columnspan=3)
        self.setToButton.grid(column=0, row=0, padx=10, sticky=S)
        self.setToEntry.grid(column=0, row=1, sticky=N)
        self.setToZero.grid(column=0, row=2, pady=5, sticky=N)
        self.moveIncButton.grid(column=1, row=0, padx=10, sticky=S)
        self.moveIncEntry.grid(column=1, row=1, sticky=N)
        self.label_4.grid(column=1, row=2, sticky=S)  # Units/s
        self.GoToButton.grid(column=2, row=0, padx=10, sticky=S)
        self.GoToEntry.grid(column=2, row=1, sticky=N)
        self.GoToZero.grid(column=2, row=2,  pady=5, sticky=N)

        self.vel.grid(column=1, row=2, rowspan=2, columnspan=3, sticky=S)
        self.vel.lower()
        self.jogButtonFWD.grid(column=1, row=4, rowspan=2, padx=10, pady=5, sticky=SW)
        self.jogButtonREV.grid(column=3, row=4, rowspan=2, padx=10, pady=5, sticky=SE)

        self.error_frame.grid(column=4, row=0, rowspan=5, padx=10)
        self.pos_err_graph.grid(column=0, row=0)
        self.current_graph.grid(column=1, row=0)
        self.label_5.grid(column=0, row=1, sticky=S)                    # Current
        self.label_6.grid(column=1, row=1, sticky=S)                    # Pos Err
        self.pos_err_rect = self.pos_err_graph.create_rectangle(2, 98, 21, 100, fill="red", outline="red")
        self.current_rect = self.current_graph.create_rectangle(2, 98, 21, 100, fill="red", outline="red")

    # This function toggles the button between OFF and ON
    def toggle_axis(self):
        if self.state == 0:
            self.enable_axis()
        else:
            self.disable_axis()

    # This function enables the axis
    def enable_axis(self):
        self.activate_axis_btns()
        self.enableButton.config(text="ON")
        if TIMC.online == 1:
            TIMC.acmd(self.queue, "ENABLE " + self.axisName)    # Aerotech command to enable axis

        if TIMC.axis1.state & TIMC.axis2.state == 1:
            TIMC.scan.activate_scan_btns()                      # Once both axes are enabled, scan button is active

        if TIMC.scan.scan_state == 1:
            TIMC.axis1.enableButton.config(state="disabled")    # If scan is active, disable axis 1 enable button
            TIMC.axis2.enableButton.config(state="disabled")    # If scan is active, disable axis 2 enable button
            TIMC.scan.start.config(state="disabled")            # If scan is active, disable start scan button
            TIMC.scan.stop.config(state="normal", fg="Black", bg="Indian Red")
            TIMC.scan.resume.config(state="normal", fg="Black", bg="Dodger Blue")

    # This function disables the axis
    def disable_axis(self):
        self.deactivate_axis_btns()
        self.enableButton.config(text="OFF", fg="Red", bg="Light Grey")
        TIMC.scan.deactivate_scan_btns()
        if TIMC.online == 1:
            TIMC.acmd(self.queue, "DISABLE " + self.axisName)   # Aerotech command to disable axis

    def activate_axis_btns(self):
        self.state = 1
        self.enableButton.config(state="normal", fg="Black", bg="Lawn Green")
        self.setToButton.config(state="normal", fg="Black", bg="Lawn Green")
        self.GoToButton.config(state="normal", fg="Black", bg="Lawn Green")
        self.moveIncButton.config(state="normal", fg="Black", bg="Lawn Green")
        self.setToZero.config(state="normal", fg="Black", bg="Lawn Green")
        self.GoToZero.config(state="normal", fg="Black", bg="Lawn Green")
        self.jogButtonFWD.config(state="normal", fg="Black", bg="SteelBlue2")
        self.jogButtonREV.config(state="normal", fg="Black", bg="SteelBlue2")
        self.position_box.config(fg="Black")
        self.label_1.config(fg="Black")
        self.velocity_box.config(state="normal")

    def deactivate_axis_btns(self):
        self.state = 0
        self.setToButton.config(state="disabled", fg="Gray", bg="Light Grey")
        self.GoToButton.config(state="disabled", fg="Gray", bg="Light Grey")
        self.moveIncButton.config(state="disabled", fg="Gray", bg="Light Grey")
        self.setToZero.config(state="disabled", fg="Gray", bg="Light Grey")
        self.GoToZero.config(state="disabled", fg="Gray", bg="Light Grey")
        self.jogButtonFWD.config(state="disabled", fg="Gray", bg="Light Grey")
        self.jogButtonREV.config(state="disabled", fg="Gray", bg="Light Grey")
        self.position_box.config(fg="Gray")
        self.label_1.config(fg="Gray")
        self.velocity_box.config(state="disabled")

    # This function starts Jogging in the FORWARD Direction
    def jogFWD(self):
        if TIMC.online == 1:
            TIMC.acmd(self.queue, "ABORT " + self.axisName)
            speed = str(self.vel.get())
            TIMC.acmd(self.queue, "FREERUN " + self.axisName + " " + speed)

    # This function starts Jogging in the REVERSE Direction
    def jogREV(self):
        if TIMC.online == 1:
            TIMC.acmd(self.queue, "ABORT " + self.axisName)
            speed = str(-1 * self.vel.get())
            TIMC.acmd(self.queue, "FREERUN " + self.axisName + " " + speed)

    # This function stops Jogging
    def stopjog(self):
        if TIMC.online == 1:
            TIMC.acmd(self.queue, "FREERUN " + self.axisName + " 0")

    # This function sets the position in the position label based on Set To Entry Box
    def setTo(self, zero):
        if zero == 0:
            position = "0"
        else:
            position = str(self.setToEntry.get())
        if checkIsDigit(position):
            if TIMC.online == 1:
                TIMC.acmd(self.queue, "POSOFFSET SET " + self.axisName + ", " + position)
            else:
                self.position = float(position)
                self.position_box.config(text=("%.2f" % self.position))

    def GoTo(self, zero):
        if zero == 0:
            position = "0"
        else:
            position = str(self.GoToEntry.get())
        if checkIsDigit(position):
            if TIMC.online == 1:
                speed = str(self.vel.get())
                TIMC.acmd(self.queue, "MOVEABS " + self.axisName + " " + position + " F " + speed)
            else:
                self.position = float(position)
                self.position_box.config(text=("%.2f" % self.position))

    def moveInc(self):
        distance = self.moveIncEntry.get()
        if checkIsDigit(distance):
            if TIMC.online == 1:
                speed = str(self.vel.get())
                TIMC.acmd(self.queue, "MOVEINC " + self.axisName + " " + distance + " F " + speed)
            else:
                self.position = self.position + float(distance)
                self.position_box.config(text=("%.2f" % self.position))

    def updateCurrent(self, cur):
        # Max Error for x1 = 401+61 = 462
        cur = abs((cur/self.currentLimit)*100)
        # Delete the old representation of current
        self.current_graph.delete(self.current_rect)
        # Draw the new position error box
        self.current_rect = self.current_graph.create_rectangle(2, 98-cur, 21, 100, fill="red", outline="red")

    def updatePosErr(self, pos_err):
        # Max Error for x1 = 401+61 = 462
        pos_err = abs((pos_err/self.posErrLimit)*100)
        # Delete the old representation of current
        self.pos_err_graph.delete(self.pos_err_rect)
        # Draw the new position error box
        self.pos_err_rect = self.pos_err_graph.create_rectangle(2, 98-pos_err, 21, 100, fill="red", outline="red")


# This class creates a Scan Window in the GUI
class ScanFrame:
    def __init__(self, master, parameters1, parameters2):
        self.master = master
        self.axis1 = parameters1
        self.axis2 = parameters2
        self.scanConfig = IntVar()
        self.scanType = IntVar()
        self.scan_setup = ["0.0", "20.0", "0.0", "10.0", "1.0"]
        self.scan_state = 0

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
        self.pause = Button(bottom_frame, text="PAUSE", font="Helvetica, 10 bold", fg="Gray", bg="Light Yellow", height=1, width=10,
                            command=lambda: self.pause_scan(), state="disabled")
        self.resume = Button(bottom_frame, text="RESUME", font="Helvetica, 10 bold", fg="Gray", bg="Light Blue", height=1, width=10,
                             command=lambda: self.resume_scan(), state="disabled")

        # Speed slider bars
        self.vel1 = Scale(left_frame, from_=self.axis1.speedMin, to=self.axis1.speedMax, orient=HORIZONTAL, length=100,
                          label="Speed " + self.axis1.axisUnits + "/sec", font=("Helvetica", 10),
                          resolution=self.axis1.speedRes)
        self.vel1.set((self.axis1.speedMax - self.axis1.speedMin) * 0.5)
        self.vel2 = Scale(left_frame, from_=self.axis2.speedMin, to=self.axis2.speedMax, orient=HORIZONTAL, length=100,
                          label="Speed " + self.axis2.axisUnits + "/sec", font=("Helvetica", 10),
                          resolution=self.axis2.speedRes)
        self.vel2.set((self.axis2.speedMax - self.axis2.speedMin) * 0.5)

        # Radio buttons to select scan configuration
        self.axis1_radio_0 = Radiobutton(left_frame, text="Scan", font=("Helvetica", 10), variable=self.scanConfig, value=0)
        self.axis1_radio_1 = Radiobutton(left_frame, text="Index", font=("Helvetica", 10), variable=self.scanConfig, value=1)
        self.axis2_radio_0 = Radiobutton(left_frame, text="Scan", font=("Helvetica", 10), variable=self.scanConfig, value=1)
        self.axis2_radio_1 = Radiobutton(left_frame, text="Index", font=("Helvetica", 10), variable=self.scanConfig, value=0)
        self.bidirectional_radio = Radiobutton(right_frame, text="Bidirectional", font=("Helvetica", 10),
                                               variable=self.scanType, value=1)
        self.unidirectional_radio = Radiobutton(right_frame, text="Unidirectional", font=("Helvetica", 10),
                                                variable=self.scanType, value=0)

        # Scan Entry Boxes
        self.label_1 = Label(right_frame, text="Scan Start", font=("Helvetica", 10))
        self.label_2 = Label(right_frame, text="Scan Stop", font=("Helvetica", 10))
        self.label_3 = Label(right_frame, text="Index Start", font=("Helvetica", 10))
        self.label_4 = Label(right_frame, text="Index Stop", font=("Helvetica", 10))
        self.label_5 = Label(right_frame, text="Index Size", font=("Helvetica", 10))
        self.label_6 = Label(right_frame, text="Remaining Time", font=("Helvetica", 10))
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
        self.label_rem_time = Label(right_frame, text="00:00:00", font=("Helvetica", 12))

        # Place widgets in frames
        self.label_0.grid(column=0, row=0, columnspan=2, sticky=W)
        self.axis_label_1.grid(column=0, row=2, rowspan=2, sticky=E, pady=5)
        self.axis_label_2.grid(column=0, row=4, rowspan=2, sticky=E, pady=5)
        self.vel1.grid(column=1, row=2, rowspan=2, columnspan=2, pady=5)
        self.vel2.grid(column=1, row=4, rowspan=2, columnspan=2, pady=5)

        self.axis1_radio_0.grid(column=3, row=2, padx=5, sticky=S)
        self.axis1_radio_1.grid(column=3, row=3, padx=5, sticky=N)
        self.axis2_radio_0.grid(column=3, row=4, padx=5, sticky=S)
        self.axis2_radio_1.grid(column=3, row=5, padx=5, sticky=N)

        self.bidirectional_radio.grid(column=0, row=0, columnspan=2, padx=20, sticky=W)
        self.unidirectional_radio.grid(column=0, row=1, columnspan=2, padx=20, sticky=W)
        self.label_1.grid(column=2, row=0, sticky=E)
        self.label_2.grid(column=2, row=1, sticky=E)
        self.label_3.grid(column=2, row=2, sticky=E)
        self.label_4.grid(column=2, row=3, sticky=E)
        self.label_5.grid(column=2, row=4, sticky=E)
        self.label_6.grid(column=0, row=5, sticky=E)
        self.e_scanStart.grid(column=3, row=0, padx=5, pady=2)
        self.e_scanStop.grid(column=3, row=1, padx=5, pady=2)
        self.e_indexStart.grid(column=3, row=2, padx=5, pady=2)
        self.e_indexStop.grid(column=3, row=3, padx=5, pady=2)
        self.e_indexSize.grid(column=3, row=4, padx=5, pady=2)
        self.label_rem_time.grid(column=1, row=5, columnspan=2, pady=5, padx=5, sticky=W)
        self.start.pack(side=LEFT, padx=22, pady=5)
        self.stop.pack(side=LEFT, padx=22, pady=5)
        self.resume.pack(side=RIGHT, padx=22, pady=5)
        self.pause.pack(side=RIGHT, padx=22, pady=5)

        # Create a scan thread which will command movements to each scan point in self.scan_points
        self.process_scan = ScanThread(self.scan_setup)

    def start_scan(self):
        print("Start Scan")
        # Get values from Entry Boxes
        self.scan_setup[0] = self.e_scanStart.get()
        self.scan_setup[1] = self.e_scanStop.get()
        self.scan_setup[2] = self.e_indexStart.get()
        self.scan_setup[3] = self.e_indexStop.get()
        self.scan_setup[4] = self.e_indexSize.get()

        # Deactivate Start Scan Button and Axis Buttons During Scan
        self.start.config(state="disabled", fg="Gray")
        TIMC.axis1.deactivate_axis_btns()
        TIMC.axis2.deactivate_axis_btns()
        TIMC.axis1.enableButton.config(state="disabled")
        TIMC.axis2.enableButton.config(state="disabled")

        # Activate Stop and Pause Buttons
        self.stop.config(state="normal", fg="Black", bg="Indian Red")
        self.pause.config(state="normal", fg="Black", bg="Gold")

        """
        Check values here to make sure scan is okay to proceed
        """
        # Is Start Scan Less Than End Scan
        if self.scan_setup[0] >= self.scan_setup[1] or self.scan_setup[2] >= self.scan_setup[3]:
            messagebox.showinfo("Bad Scan Inputs", "Start/Stop Values are Same or In Wrong Direction")
            self.stop_scan()
        else:
            self.scan_state = 1
            self.process_scan = ScanThread(self.scan_setup)
            self.process_scan.start()

    def stop_scan(self):
        self.process_scan.stop()
        self.scan_state = 0

        # Activate Start Scan Button and Axis Buttons
        self.start.config(state="normal", fg="Black")
        TIMC.axis1.activate_axis_btns()
        TIMC.axis2.activate_axis_btns()
        TIMC.axis1.enableButton.config(state="normal")
        TIMC.axis2.enableButton.config(state="normal")

        # Deactivate Stop, Pause and Resume
        self.stop.config(state="disabled", fg="Gray", bg="Light Coral")
        self.pause.config(state="disabled", fg="Gray", bg="Light Yellow")
        self.resume.config(state="disabled", fg="Gray", bg="Light Blue")

    def pause_scan(self):
        self.process_scan.pause()

        # Activate Axis Buttons and Resume Button
        TIMC.axis1.activate_axis_btns()
        TIMC.axis2.activate_axis_btns()
        TIMC.axis1.enableButton.config(state="normal")
        TIMC.axis2.enableButton.config(state="normal")
        self.resume.config(state="normal", fg="Black", bg="Dodger Blue")
        self.pause.config(state="disabled", fg="Gray", bg="Light Yellow")

    def resume_scan(self):
        self.process_scan.resume()

        # Deactivate Axis Buttons and Resume Button
        TIMC.axis1.deactivate_axis_btns()
        TIMC.axis2.deactivate_axis_btns()
        TIMC.axis1.enableButton.config(state="disabled")
        TIMC.axis2.enableButton.config(state="disabled")
        self.resume.config(state="disabled", fg="Gray", bg="Light Blue")
        self.pause.config(state="normal", fg="Black", bg="Gold")

    def activate_scan_btns(self):
        self.start.config(state="normal", fg="Black", bg="Lawn Green")

    def deactivate_scan_btns(self):
        self.start.config(state="disabled", fg="Gray", bg="Light Green")
        self.stop.config(state="disabled", fg="Gray", bg="Light Coral")
        self.pause.config(state="disabled", fg="Gray", bg="Light Yellow")
        self.resume.config(state="disabled", fg="Gray", bg="Light Blue")


# This class creates a Fault Frame in the GUI
class FaultFrame:
    def __init__(self, master):
        self.frame = Frame(master, borderwidth=2, relief=SUNKEN)
        self.canvas = Canvas(self.frame, highlightthickness=0)
        self.canvas.pack(fill=X)
        self.frame.pack(fill=X, padx=10, pady=5)
        self.frame.pack()
        self.status_text = StringVar()

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
            self.status_text.set("")


# This class starts a thread that opens communication and puts queued commands to the Ensemble
class SerialThread(threading.Thread):
    def __init__(self, baud, qControl_read, qControl_write, qScan_read, qScan_write, qStatus_read, qStatus_write, qFBK_read, qFBK_write):
        threading.Thread.__init__(self)
        self.qControl_read = qControl_read
        self.qControl_write = qControl_write
        self.qScan_read = qScan_read
        self.qScan_write = qScan_write
        self.qStatus_read = qStatus_read
        self.qStatus_write = qStatus_write
        self.qFBK_read = qFBK_read
        self.qFBK_write = qFBK_write
        self.s = serial.Serial()

        self._is_running = 1
        self.port_open = 0
        self.baud = baud

    def run(self):
        # Open the serial port
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
            self.s = serial.Serial(result[0], self.baud, timeout=0.05)

            # Send a command to check if communication has been established
            self.s.write("ACKNOWLEDGEALL".encode('ascii') + b' \n')
            data = self.s.readline().decode('ascii')
            if '%' in data:
                self.port_open = 1
                self.s.write("WAIT MODE NOWAIT".encode('ascii') + b' \n')
                # Throw away second response
                data = self.s.readline().decode('ascii')
        elif len(result) > 1:
            self.port_open = 0
            self._is_running = 0
        else:
            self._is_running = 0

        # Serial Thread Main Loop - Check Queue for Commands to Send to Aerotech Drive
        while self._is_running:
            time.sleep(.0001)
            # Check if control queue has commands in the queue to send to the Aerotech drive
            if self.qControl_write.qsize():
                command = self.qControl_write.get().encode('ascii') + b' \n'
                self.s.write(command)
                data = self.s.readline().decode('ascii')
                self.qControl_read.put(data)
            # Check if scan queue has commands in the queue to send to the Aerotech drive
            elif self.qScan_write.qsize():
                command = self.qScan_write.get().encode('ascii') + b' \n'
                self.s.write(command)
                data = self.s.readline().decode('ascii')
                self.qScan_read.put(data)
            # Check if status queue has commands in the queue to send to the Aerotech drive
            elif self.qStatus_write.qsize():
                command = self.qStatus_write.get().encode('ascii') + b' \n'
                self.s.write(command)
                data = self.s.readline().decode('ascii')
                self.qStatus_read.put(data)
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
            print("Serial Port Closed")
        except:
            print("No Serial Port to Close")


# This class starts a thread for automated scanning
class ScanThread(threading.Thread):
    def __init__(self, scan_setup):
        threading.Thread.__init__(self)
        self._is_running = 1
        self._is_paused = 0
        self.scan_setup = scan_setup
        self.setDaemon(True)

    """
    Calculate scan points
    """

    def run(self):
        print("Running Scan")
        while self._is_running:
            time.sleep(.25)
            if self._is_paused != 1:
                print("Scanning...")

                """
                Scan profile
                """

    def stop(self):
        self._is_running = 0
        self._is_paused = 1
        print("Stopping Scan")

    def pause(self):
        self._is_paused = 1
        print("Pause Scan")

    def resume(self):
        self._is_paused = 0
        print("Resume Scan")


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
            time.sleep(1)
            s_fault = int(TIMC.acmd("STATUS", "AXISFAULT (" + TIMC.axis1.axisName + ")"))
            p_fault = int(TIMC.acmd("STATUS", "AXISFAULT (" + TIMC.axis2.axisName + ")"))

            # Bitwise AND the fault data with a mask to check specifically for ESTOP
            if 0b100000000000 & s_fault or 0b100000000000 & p_fault:
                TIMC.fault.update_status("ESTOP was pressed")
                TIMC.axis1.disable_axis()
                TIMC.axis2.disable_axis()
            else:
                faultMask = 1
                # If there is a fault and CIRC is not yet disabled
                if s_fault != 0:
                    TIMC.axis1.disable_axis()
                    # Create fault masks to bitwise AND the data to determine which type of fault has occured.
                    for i in range(0, len(self.fault_array)):
                        if (s_fault & (faultMask << i)) != 0:
                            TIMC.fault.fault_status("FAULT: " + TIMC.axis1.axisName + " " + str(self.fault_array[i]))

                # If there is a fault and TRANSLATOR is not yet disabled
                if p_fault != 0:
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
            time.sleep(.0001)
            # Auto-populate the feedback write queue with commands so the queue is never empty
            # When acmd is called, the command is pulled off of the queue so the write queue becomes empty again
            # As write_index is indexed through the write_cmd array, the read_index is used to put the data returned
            # from the acmd command in the correct location
            if TIMC.qFBK_write.qsize() == 0:
                data = TIMC.acmd("FBK", self.write_cmd[self.write_index])
                if self.write_index < len(self.write_cmd) - 1:
                    self.write_index += 1
                else:
                    self.write_index = 0

                if self.read_index == 0:
                    pos = round(float(data), 2)
                    TIMC.axis1.position_box.config(text=("%.2f" % pos))
                    self.read_index += 1
                elif self.read_index == 1:
                    cur = float(data)
                    TIMC.axis1.updateCurrent(cur)
                    self.read_index += 1
                elif self.read_index == 2:
                    vel = round(float(data), 1)
                    TIMC.axis1.velocity_box.config(text=("%.2f" % vel))
                    self.read_index += 1
                elif self.read_index == 3:
                    pos_err = float(data)
                    TIMC.axis1.updatePosErr(pos_err)
                    self.read_index += 1
                elif self.read_index == 4:
                    pos = round(float(data), 2)
                    TIMC.axis2.position_box.config(text=("%.2f" % pos))
                    self.read_index += 1
                elif self.read_index == 5:
                    cur = float(data)
                    TIMC.axis2.updateCurrent(cur)
                    self.read_index += 1
                elif self.read_index == 6:
                    vel = round(float(data), 1)
                    TIMC.axis2.velocity_box.config(text=("%.2f" % vel))
                    self.read_index += 1
                elif self.read_index == 7:
                    pos_err = float(data)
                    TIMC.axis2.updatePosErr(pos_err)
                    self.read_index = 0

    def stop(self):
        self._is_running = 0


# This class is starts Main GUI Window and starts communication with controller
class Main:
    def __init__(self, master):
        self.master = master
        master.geometry("650x750")
        master.title("R0: TIMC - Piping")
        master.resizable(width=False, height=False)

        # Open Setup File
        self.params = str()
        self.filename = "TIMC-P-SETUP.txt"
        try:
            f = open(self.filename, "r+")
            self.params = f.readlines()
            f.close()
            print("Setup File Parameters " + str(self.params))
        except FileNotFoundError:
            print("Cannot find file: " + self.filename)
            print("Creating Default " + self.filename)
            f = open(self.filename, "w+")
            self.params = ["NOVA\n", "0\n", "20\n"]     # Default TIMC Parameters
            f.writelines(self.params)
            f.close()
            print(self.params)

        self.baud = 115200
        self.online = 0  # If communication is successful with the controller this value will be set to 1
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

        # Start serial thread
        self.process_serial = SerialThread(self.baud,
                                           self.qControl_read, self.qControl_write,
                                           self.qScan_read, self.qScan_write,
                                           self.qStatus_read, self.qStatus_write,
                                           self.qFBK_read, self.qFBK_write)
        self.process_serial.start()

        # Wait for serial thread to establish communication
        time.sleep(1.0)

        # Setup GUI Frames
        self.tool = ToolFrame(self.master, self.params)
        self.axis1 = AxisFrame(self.master, SetupAxis1())
        self.axis2 = AxisFrame(self.master, SetupAxis2())
        self.scan = ScanFrame(self.master, self.axis1, self.axis2)
        self.fault = FaultFrame(self.master)

        # Determine if GUI should be started offline
        self.is_offline()

    # Main method for sending commands to TIMC, command syntax specified by Aerotech: ASCII Commands
    def acmd(self, queue_name, text):
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
            return 0
        # If the command was successful, and the command sent requested data fro the controller,
        # the "%" precedes the returned data
        elif "%" in data:
            data = data.replace("%", "")
            return data
        else:
            print("Error")

    # if communication is not successful then use Offline Mode
    def is_offline(self):
        if self.process_serial.port_open == 0:  # OFFLINE
            self.fault.update_status("OFFLINE MODE")
            self.process_serial.stop()
            self.online = 0
        elif self.process_serial.port_open == 1:  # ONLINE
            self.online = 1


def on_closing():
    print("Closing...")
    exception_flag = 0

    if TIMC.online:
        print("Disconnecting...")
        try:
            TIMC.axis1.disable_axis()   # Disable Axis 1
        except :
            exception_flag = 1
        try:
            TIMC.axis2.disable_axis()   # Disable Axis 2
        except:
            exception_flag = 1
        try:
            process_status.stop()
        except:
            exception_flag = 1
        try:
            process_feedback.stop()
        except:
            exception_flag = 1
        try:
            time.sleep(0.5)
            TIMC.process_serial.stop()  # Close Serial Port Communication
        except:
            exception_flag = 1

    if exception_flag == 1:
        print("ERROR CLOSING A THREAD")

    # Overwrite setup file with parameters to include any changes during program execution
    try:
        new_f = open(TIMC.filename, "r+")
        new_f.close()
        print("Setup File Parameters " + str(TIMC.params))
        new_f = open(TIMC.filename, "w+")
        new_f.writelines(TIMC.params)
        new_f.close()
    except FileExistsError:
        print("No File to Overwrite")

    root.destroy()


def checkIsDigit(text):
    if "-" in text:
        text = text.replace("-", "0")
    if "." in text:
        text = text.replace(".", "0")
    if text.isdigit():
        return True
    else:
        messagebox.showinfo("Bad Input", "Value is not a number")
        return False


root = Tk()
TIMC = Main(root)

if TIMC.online:
    # Start thread to updated position, current and error feedback for each axis
    process_feedback = UpdateFeedback()
    process_feedback.start()

    # Start thread to monitor for ESTOP and faults etc.
    process_status = UpdateStatus()
    process_status.start()



root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()
