"""
This program is beginning of the piping GUI, it creates 2 Axis frames, a Scan Frame, and a Fault Frame

It communicates with the Aerotech Controller and sets up a queue thread for Control Commands Enable and Jog only

Currently the program is able to enable axes and jog them *NOTE PROGRAM IS IN MM, PARAMETER FILE MAY BE IN INCHES*

No Fault conditions are handled, be cautious while running

From Threadtest4, added ability to read in text file to set to last used tool configuration
"""

from tkinter import *
from tkinter import messagebox
import serial
import threading
import time
import queue


# This class sets Frame parameters for the Circ Axis
class SetupAxis1Frame:
    def __init__(self):
        self.axisName = "CIRC"
        self.axisUnits = "mm"
        self.speedMin = 0.1
        self.speedMax = 25.0
        self.speedRes = 2.5
        self.queue_name = "CTRL"


# This class sets Frame parameters for the Trans Axis
class SetupAxis2Frame:
    def __init__(self):
        self.axisName = "TRANSLATOR"
        self.axisUnits = "mm"
        self.speedMin = 0.1
        self.speedMax = 50.0
        self.speedRes = 5
        self.queue_name = "CTRL"


# This class places a button on the top of the GUI to select between LAPIS and NOVA
class ToolFrame:
    def __init__(self, master, params):
        self.master = master
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
        self.speedMin = parameters.speedMin
        self.speedMax = parameters.speedMax
        self.speedRes = parameters.speedRes
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
        self.label_0 = Label(self.frame, text=self.axisName, font=("Helvetica", 14))
        self.label_1 = Label(self.frame, text="Position", font=("Helvetica", 10))
        self.label_2 = Label(self.frame, text="Current", font=("Helvetica", 10))
        self.label_3 = Label(self.frame, text="Velocity", font=("Helvetica", 10))
        self.enableButton = Button(self.frame, text="OFF", fg="Red", bg="Light Grey", height=3, width=8,
                                   command=lambda: self.toggle_axis(), font="Helvetica, 12 bold")
        self.setToButton = Button(self.frame, text="SET TO", fg="Gray", bg="Light Grey", height=1, width=8,
                                  state="disabled", command=lambda: self.setTo())
        self.GoToButton = Button(self.frame, text="GOTO", fg="Gray", bg="Light Grey", height=1, width=8,
                                 state="disabled",
                                 command=lambda: self.GoTo())
        self.moveIncButton = Button(self.frame, text="Move Inc", fg="Gray", bg="Light Grey", height=1, width=8,
                                    state="disabled", command=lambda: self.moveInc())
        self.jogButtonFWD = Button(self.frame, text="FWD", fg="Gray", bg="Light Grey", height=1, width=8,
                                   font="Helvetica, 12 bold", state="disabled")
        self.jogButtonREV = Button(self.frame, text="REV", fg="Gray", bg="Light Grey", height=1, width=8,
                                   font="Helvetica, 12 bold", state="disabled")
        self.position_box = Label(self.frame, text=("%.2f" % self.position), bg="Light Grey", width=8,
                                    relief=SUNKEN, state="disabled", font=("Helvetica", 12))
        self.current_box = Label(self.frame, text=("%.1f" % self.current), bg="Light Grey", width=8,
                                    relief=SUNKEN, state="disabled", font=("Helvetica", 12))
        self.velocity_box = Label(self.frame, text=("%.1f" % self.velocity), bg="Light Grey", width=8,
                                    relief=SUNKEN, state="disabled", font=("Helvetica", 12))
        self.setToEntry = Entry(self.frame, textvariable=self.setToText, width=10, font=("Helvetica", 10), justify="center")
        self.GoToEntry = Entry(self.frame, textvariable=self.GoToText, width=10, font=("Helvetica", 10), justify="center")
        self.moveIncEntry = Entry(self.frame, textvariable=self.moveIncText, width=10, font=("Helvetica", 10),
                                  justify="center")
        self.vel = Scale(self.frame, from_=self.speedMin, to=self.speedMax, orient=HORIZONTAL, length=150,
                         label="Speed " + self.axisUnits + "/sec", font=("Helvetica", 10),
                         resolution=self.speedRes)
        self.vel.set((self.speedMax - self.speedMin) * 0.5)

        # Jog Button Actions
        self.jogButtonFWD.bind('<ButtonPress-1>', lambda event: self.jogFWD())
        self.jogButtonFWD.bind('<ButtonRelease-1>', lambda event: self.stopjog())
        self.jogButtonREV.bind('<ButtonPress-1>', lambda event: self.jogREV())
        self.jogButtonREV.bind('<ButtonRelease-1>', lambda event: self.stopjog())

        # Grid Widgets
        self.label_0.grid(column=0, row=0, columnspan=2, sticky=W)
        self.label_1.grid(column=3, row=0, sticky=S)
        self.label_2.grid(column=4, row=0, sticky=S)
        self.label_3.grid(column=5, row=0, sticky=S)
        self.enableButton.grid(column=0, row=1, rowspan=3, padx=10, pady=5)
        self.jogButtonFWD.grid(column=1, row=1, padx=10, pady=5, sticky=N)
        self.jogButtonREV.grid(column=2, row=1, padx=10, pady=5, sticky=N)
        self.vel.grid(column=1, row=2, rowspan=2, columnspan=2, padx=5, pady=5)
        self.position_box.grid(column=3, row=1, padx=5, pady=5, sticky=N)
        self.current_box.grid(column=4, row=1, padx=5, pady=5, sticky=N)
        self.velocity_box.grid(column=5, row=1, padx=5, pady=5, sticky=N)
        self.setToEntry.grid(column=3, row=2, padx=5, pady=5)
        self.setToButton.grid(column=3, row=3, padx=5, pady=5)
        self.GoToEntry.grid(column=4, row=2, padx=5, pady=5)
        self.GoToButton.grid(column=4, row=3, padx=5, pady=5)
        self.moveIncEntry.grid(column=5, row=2, padx=5, pady=5)
        self.moveIncButton.grid(column=5, row=3, padx=5, pady=5)

    # This function toggles the button between OFF and ON
    def toggle_axis(self):
        if self.state == 0:
            self.enable_axis()
        else:
            self.disable_axis()

    # This function enables the axis
    def enable_axis(self):
        self.activate_all_btns()
        if TIMC.online == 1:
            TIMC.acmd(self.queue, "ENABLE " + self.axisName)

    # This function disables the axis
    def disable_axis(self):
        self.inactivate_all_btns()
        if TIMC.online == 1:
            TIMC.acmd(self.queue, "DISABLE " + self.axisName)

    def activate_all_btns(self):
        self.state = 1
        self.enableButton.config(text="ON", fg="Black", bg="Lawn Green")
        self.setToButton.config(state="normal", fg="Black", bg="Lawn Green")
        self.GoToButton.config(state="normal", fg="Black", bg="Lawn Green")
        self.moveIncButton.config(state="normal", fg="Black", bg="Lawn Green")
        self.jogButtonFWD.config(state="normal", fg="Black", bg="Lawn Green")
        self.jogButtonREV.config(state="normal", fg="Black", bg="Lawn Green")
        self.position_box.config(state="normal", bg="White")

    def inactivate_all_btns(self):
        self.state = 0
        self.enableButton.config(text="OFF", fg="Red", bg="Light Grey")
        self.setToButton.config(state="disabled", fg="Gray", bg="Light Grey")
        self.GoToButton.config(state="disabled", fg="Gray", bg="Light Grey")
        self.moveIncButton.config(state="disabled", fg="Gray", bg="Light Grey")
        self.jogButtonFWD.config(state="disabled", fg="Gray", bg="Light Grey")
        self.jogButtonREV.config(state="disabled", fg="Gray", bg="Light Grey")
        self.position_box.config(state="disabled", bg="Light Grey")

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
    def setTo(self):
        position = self.setToEntry.get()
        if not position.isdigit():
            messagebox.showinfo("Bad Input", "Value is not a number")
            return
        position = float(position)
        self.position_box.config(text=("%.2f" % position))

    def GoTo(self):
        position = self.GoToEntry.get()
        if not position.isdigit():
            messagebox.showinfo("Bad Input", "Value is not a number")
            return
        self.position = float(self.GoToEntry.get())
        self.position_box.config(text=("%.2f" % self.position))

    def moveInc(self):
        position = self.moveIncEntry.get()
        if not position.isdigit():
            messagebox.showinfo("Bad Input", "Value is not a number")
            return
        self.position = float(self.moveIncEntry.get())
        self.position_box.config(text=("%.2f" % self.position))


# This class creates a Scan Window in the GUI
class ScanFrame:
    def __init__(self, master, parameters1, parameters2):
        self.master = master
        self.axis1 = parameters1
        self.axis2 = parameters2
        self.scanConfig = IntVar()
        self.scanType = IntVar()
        self.scan_setup = ["0.0", "20.0", "0.0", "10.0", "1.0"]

        scan_frame = Frame(master, relief=SUNKEN, border=2)
        left_frame = Frame(scan_frame, relief=RAISED, border=2)
        right_frame = Frame(scan_frame, relief=RAISED, border=2)
        bottom_frame = Frame(master, relief=RAISED, border=2)
        scan_frame.pack(fill=X, padx=10)

        left_frame.grid(column=0, row=0, sticky=W)
        right_frame.grid(column=1, row=0, padx=10)
        bottom_frame.pack(fill=X, padx=10)

        # Labels and Axis Names
        self.label_0 = Label(left_frame, text="SCAN WINDOW", font=("Helvetica", 14))
        self.axis_label_1 = Label(left_frame, text=self.axis1.axisName, font=("Helvetica", 12))
        self.axis_label_2 = Label(left_frame, text=self.axis2.axisName, font=("Helvetica", 12))

        # Start, Stop, Pause, and Resume Buttons
        self.start = Button(bottom_frame, text="START", font="Helvetica, 12 bold", fg="Gray", bg="Lawn Green", height=2,
                            width=10, command=lambda: self.start_scan())
        self.stop = Button(bottom_frame, text="STOP", font="Helvetica, 12 bold", fg="Gray", bg="Indian Red", height=2,
                           width=10, command=lambda: self.stop_scan())
        self.pause = Button(bottom_frame, text="PAUSE", font="Helvetica, 10 bold", fg="Gray", bg="gold", height=1, width=10,
                            command=lambda: self.pause_scan())
        self.resume = Button(bottom_frame, text="RESUME", font="Helvetica, 10 bold", fg="Gray", bg="Light Blue", height=1, width=10,
                             command=lambda: self.resume_scan())

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

    def start_scan(self):
        print("start scan")

    def stop_scan(self):
        print("stop scan")

    def pause_scan(self):
        print("pause scan")

    def resume_scan(self):
        print("resume scan")


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
        self.button.grid(row=1, column=2, pady=5, padx=5)

    # Method to display the fault text and change the background color to red
    def fault_status(self, text):
        self.canvas.config(bg="red")
        self.label_0.config(bg="red")
        self.status_text.set(text)

    # Method to display information text and keep the background color default
    def update_status(self, text):
        self.canvas.config(bg="SystemButtonFace")
        self.label_0.config(bg="SystemButtonFace")
        self.status_text.set(text)

    # Method to reset the fault and change background color back to default
    def fault_ack(self):
        if TIMC.online:
            TIMC.acmd("CTRL", "ACKNOWLEDGEALL")
            self.canvas.config(bg="SystemButtonFace")
            self.label_0.config(bg="SystemButtonFace")
            self.status_text.set("")


# This class starts communication with Aerotech and runs a thread which puts queued commands to the Ensemble
class SerialThread(threading.Thread):
    def __init__(self, baud, qControl_read, qControl_write):
        threading.Thread.__init__(self)
        self.qControl_read = qControl_read
        self.qControl_write = qControl_write

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
                print(port)
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
            time.sleep(.001)
            # Check if control queue has commands in the queue to send to the Aerotech drive
            if self.qControl_write.qsize():
                command = self.qControl_write.get().encode('ascii') + b' \n'
                self.s.write(command)
                data = self.s.readline().decode('ascii')
                self.qControl_read.put(data)

    # Stop the thread from running
    def stop(self):
        self._is_running = 0
        try:
            self.s.close()
            print("Serial Port Closed")
        except:
            print("No Serial Port to Close")


# This class is starts Main GUI Window and starts communication with controller
class Main:
    def __init__(self, master):
        self.master = master
        master.geometry("650x750")
        master.title("R0: TIMC - Piping")
        master.resizable(width=False, height=False)

        self.params = str()
        self.filename = "TIMC-P-PARAM.txt"
        try:
            f = open(self.filename, "r+")
            self.params = f.readlines()
            f.close()
            print(self.params)
        except FileNotFoundError:
            print("Cannot find file: " + self.filename)

        self.baud = 115200
        self.online = 0  # If communication is successful with the controller this value will be set to 1
        self.qControl_read = queue.Queue()  # Results of the qControl_write commands recorded here
        self.qControl_write = queue.Queue()  # Jog, GoTo, Index, and Set button press commands are sent to this queue
        self.write_queue = queue.Queue()
        self.read_queue = queue.Queue()

        # Start serial thread
        self.process_serial = SerialThread(self.baud, self.qControl_read, self.qControl_write,)
        self.process_serial.start()

        # Wait for serial thread to establish communication
        time.sleep(1.0)

        # Setup GUI Frames
        self.tool = ToolFrame(self.master, self.params)
        self.axis1 = AxisFrame(self.master, SetupAxis1Frame())
        self.axis2 = AxisFrame(self.master, SetupAxis2Frame())
        self.scan = ScanFrame(self.master, self.axis1, self.axis2)
        self.fault = FaultFrame(self.master)

        # Determine if GUI should be started offline
        self.is_offline()

    # Main method for sending commands to TIMC, command syntax specified by Aerotech: ASCII Commands
    def acmd(self, queue_name, text):
        if queue_name == "CTRL":
            self.write_queue = self.qControl_write
            self.read_queue = self.qControl_read

        # Put command on the queue, process_serial sends the command and returns the result in the read queue
        self.write_queue.put(text)
        data = self.read_queue.get()

        # Aerotech drive sends back special characters in response to the command given
        if "!" in data:
            print("(!) Bad Execution, Queue: " + queue_name + " CMD: " + text)
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
        elif "%" in data:
            data = data.replace("%", "")
            return data
        else:
            print("Error")

    # if communication is not successful then disable buttons
    def is_offline(self):
        if self.process_serial.port_open == 0:  # OFFLINE
            self.fault.update_status("OFFLINE MODE")
            # self.axis1.enableButton.config(state="disabled")
            # self.axis2.enableButton.config(state="disabled")
            # self.scan.start.config(state="disabled")
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
        except:
            exception_flag = 1
        try:
            TIMC.axis2.disable_axis()   # Disable Axis 2
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
        print(TIMC.params)
        new_f = open(TIMC.filename, "w+")
        new_f.writelines(TIMC.params)
        new_f.close()
    except FileExistsError:
        print("No File to Overwrite")

    root.destroy()


root = Tk()
TIMC = Main(root)
root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()
