# MODIFIED CODE FOR PIPING CONTROLLER
#
# - Changed axes names to CIRC and TRANSLATOR

from tkinter import *
from tkinter import messagebox
import serial
import threading
import queue
import time
import datetime
import platform
import sys


THREAD_WAIT = 0.0001
SCAN_THREAD_WAIT = 0.25


# Define classes with variables associated with each type of frame
class SetupMainWindow:
    def __init__(self):
        self.gui_width = 605
        self.gui_height = 695
        self.baud = 115200


class SetupCIRCFrame:
    def __init__(self):
        self.axisName = "CIRC"
        self.axisUnits = "in"
        self.jogText1 = "CCW"
        self.jogText2 = "CW"
        self.speedMin = 0.05
        self.speedMax = 2
        self.speedRes = 0.25
        self.maxError = 0.2
        self.queue_name = "CTRL"


class SetupTRANSLATORFrame:
    def __init__(self):
        self.axisName = "TRANSLATOR"
        self.axisUnits = "in"
        self.jogText1 = "IN"
        self.jogText2 = "OUT"
        self.speedMin = 0.05
        self.speedMax = 2
        self.speedRes = 0.25
        self.maxError = 0.2
        self.queue_name = "CTRL"


class SetupScanFrame:
    def __init__(self):
        self.axisName = "SCAN WINDOW"
        self.scanSpeedMin = 0.05
        self.scanSpeedMax = 2
        self.scanSpeedRes = 0.25
        self.indexSpeedMin = 0.05
        self.indexSpeedMax = 2
        self.indexSpeedRes = 0.25
        self.scanAxisUnits = "deg"
        self.indexAxisUnits = "in"
        self.queue_name = "SCAN"


# Main GUI window which contains the four other frames: CIRC, TRANSLATOR, Scan Frame, Status Frame
class MainWindow:
    def __init__(self, master, parameters):
        self.parameters = parameters
        self.baud = self.parameters.baud
        self.online = 0 # If communication is successful with the controller this value will be set to 1

        # Process Serial Thread monitors and puts data in the queues below
        self.qFBK_read = queue.Queue()      # Results of the qFBK_write commands recorded here
        self.qFBK_write = queue.Queue()     # Commands to update the feedback are sent to this queue
        self.qStatus_read = queue.Queue()   # Results of the qStatus_write commands recorded here
        self.qStatus_write = queue.Queue()  # Fault checking commands are sent to this queue
        self.qScan_read = queue.Queue()     # Results of the qScan_write commands recorded here
        self.qScan_write = queue.Queue()    # Commands from the scan thread are written to this queue
        self.qControl_read = queue.Queue()  # Results of the qControl_write commands recorded here
        self.qControl_write = queue.Queue() # Jog, GoTo, Index, and Set button press commands are sent to this queue
        self.qLog_write1 = queue.Queue()    # All commands are copied to this queue to be processed for the log file
        self.qLog_write2 = queue.Queue()    # Start, Stop, Pause, Resume button clicks recorded to this queue for the log file

        # Start serial thread.
        self.process_serial = SerialThread(self.baud, self.qControl_read, self.qControl_write, self.qScan_read,
                                           self.qScan_write, self.qStatus_read, self.qStatus_write, self.qFBK_read,
                                           self.qFBK_write, self.qLog_write1, self.qLog_write2)
        self.process_serial.start()

        # Wait for serial thread to establish communication
        time.sleep(0.5)

        # Create the main GUI window
        self.master = master
        master.geometry(str(parameters.gui_width) + "x" + str(parameters.gui_height))
        master.title("R1: Tooling Inspection Motion Controller - Piping")

        # Create frames for each axis and function
        self.CIRC = AxisFrame(self.master, SetupCIRCFrame())
        self.TRANSLATOR = AxisFrame(self.master, SetupTRANSLATORFrame())
        self.scan = ScanFrame(self.master, SetupScanFrame())
        self.fault = FaultFrame(self.master)

        # Start communication with TIMC
        self.init_communication()

    # Main method for sending commands to TIMC, command syntax specified by Aerotech: ASCII Commands
    def acmd(self, queue_name, text):
        if (queue_name != "LOG"):
            # There are four read/write queues
            if (queue_name == "CTRL"):
                write_queue = self.qControl_write
                read_queue = self.qControl_read
            elif( queue_name == "SCAN"):
                write_queue = self.qScan_write
                read_queue = self.qScan_read
            elif(queue_name == "STATUS"):
                write_queue = self.qStatus_write
                read_queue = self.qStatus_read
            elif(queue_name == "FBK"):
                write_queue = self.qFBK_write
                read_queue = self.qFBK_read

            # Put command on the queue, process_serial sends the command and returns the result in the read queue
            write_queue.put(text)
            data = read_queue.get()

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
        # process_serial will transfer data from this queue to the main queue processed by process_log
        else:
            self.qLog_write2.put(text)
    # process_serial attempts to communicate with the Aerotech drive,
    # if communication is not successful then disable buttons
    def init_communication(self):
        if (self.process_serial.port_open == 0):
            self.fault.update_status("OFFLINE MODE")
            self.CIRC.enableButton.config(state="disabled")
            self.TRANSLATOR.enableButton.config(state="disabled")
            self.scan.start.config(state="disabled")
            self.process_serial.stop()
            self.online = 0
        elif (self.process_serial.port_open == 1):
            self.online = 1


class SerialThread(threading.Thread):

    def __init__(self, baud, qControl_read, qControl_write, qScan_read, qScan_write, qStatus_read, qStatus_write,
                 qFBK_read, qFBK_write, qLog_write1, qLog_write2):
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
            self.s = serial.Serial(result[0], self.baud, timeout = 0.05)

            # Send a command to check if communication has been established
            self.s.write("ACKNOWLEDGEALL".encode('ascii') + b' \n')
            data = self.s.readline().decode('ascii')
            if ('%' in data):
                self.port_open = 1
                self.s.write("WAIT MODE NOWAIT".encode('ascii') + b' \n')
                # Throw away second response
                data = self.s.readline().decode('ascii')
        elif (len(result) > 1):
            self.port_open = 0
            self._is_running = 0
        else:
            self._is_running = 0

        # Thread main loop
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
            # Check if feedback queue has commands in the queue. This is the least priority and this queue will be serviced only if all other queues are empty
            elif self.qFBK_write.qsize():
                command = self.qFBK_write.get().encode('ascii') + b' \n'
                self.s.write(command)
                data = self.s.readline().decode('ascii')
                self.qFBK_read.put(data)
                # Copy data Log queue for processing
                self.qLog_write1.put("FBK : " + str(command) + str(data))

    # Stop the thread from running
    def stop(self):
        self._is_running = 0
        try:
            self.s.close()
        except:
            print("No Serial Port to Close")


# Will create an axis frame with all buttons (JOG, GoTo, Index, SET), entry boxes, and scales
class AxisFrame:
    def __init__(self, master, parameters):
        frame = Frame(master, borderwidth=2, relief=SUNKEN)
        self.canvas = Canvas(frame, highlightthickness=0)
        self.canvas.grid(row=0, column=0)
        frame.pack(fill=X, padx=5, pady=5)
        frame.pack()

        self.state = 0
        self.axisName = parameters.axisName
        self.max_pos_error = parameters.maxError
        self.mtr_position = StringVar()
        self.mtr_current = StringVar()
        self.mtr_error = StringVar()
        self.queue = parameters.queue_name

        self.enableButton = Button(self.canvas, text="OFF", font="Courier, 12", fg="black", bg="#d3d3d3", height=2, width=6,
                                   padx=3, pady=3, command=lambda: self.toggle_axis())
        self.jog_neg = Button(self.canvas, text=parameters.jogText1, font="Courier, 12", activeforeground="black",
                              activebackground="#00aa00", bg="#00aa00", width=10, state=DISABLED)
        self.jog_pos = Button(self.canvas, text=parameters.jogText2, font="Courier, 12", activeforeground="black",
                              activebackground="#00aa00", bg="#00aa00", width=10, state=DISABLED)
        self.set_pos = Button(self.canvas, text=" Set ", font="Courier, 12", activeforeground="black",
                              activebackground="#00aa00", bg="#00aa00", state=DISABLED,
                              command=lambda: self.set_position())
        self.go_to = Button(self.canvas, text="GoTo", font="Courier, 12", activeforeground="black",
                            activebackground="#00aa00",
                            bg="#00aa00", state=DISABLED, command=lambda: self.move_to())
        self.inc = Button(self.canvas, text="Index", font="Courier, 12", activeforeground="black",
                          activebackground="#00aa00", bg="#00aa00",
                          state=DISABLED, command=lambda: self.move_inc())
        self.mtrPositionBox = Entry(self.canvas, state="readonly", width=8, textvariable=self.mtr_position, font="Courier, 12 bold")
        self.mtrCurrentBox = Entry(self.canvas, state="readonly", width=8, textvariable=self.mtr_current, font="Courier, 12")
        self.e_setPos = Entry(self.canvas, width=8, font="Courier, 12")
        self.e_goTo = Entry(self.canvas, width=8, font="Courier, 12")
        self.e_inc = Entry(self.canvas, width=8, font="Courier, 12")
        self.vel = Scale(self.canvas, from_=parameters.speedMin, to=parameters.speedMax, orient=HORIZONTAL, length=150,
                         label="     Velocity " + parameters.axisUnits + "/sec", font="Courier, 12", resolution=parameters.speedRes)
        self.vel.set((parameters.speedMax - parameters.speedMin) * 0.25)
        self.vel.config(state="disabled")
        self.label_0 = Label(self.canvas, text=parameters.axisName, height=1, font=("Helvetica", 14))
        self.label_1 = Label(self.canvas, text="Pos. (" + parameters.axisUnits + ")", font="Courier, 12")
        self.label_2 = Label(self.canvas, text="Cur. (mA)", font="Courier, 12")
        self.label_3 = Label(self.canvas, text="Pos. Error", font="Courier, 12")

        # Draw box for position error that looks like disabled entry box.
        self.canvas.create_line(504, 30, 579, 30, fill="#A0A0A0")
        self.canvas.create_line(504, 30, 504, 51, fill="#A0A0A0")
        self.canvas.create_line(504, 51, 579, 51, fill="white")
        self.canvas.create_line(579, 51, 579, 29, fill="white")

        # GRID
        self.label_0.grid(row=0, column=0, columnspan=5, sticky=W)
        self.enableButton.grid(row=1, column=0, rowspan=3, padx=15)
        self.jog_neg.grid(row=1, column=1, rowspan=2, padx=3)
        self.jog_pos.grid(row=1, column=2, rowspan=2, padx=3)
        self.label_1.grid(row=0, column=3, sticky=S)
        self.label_2.grid(row=0, column=4, sticky=S)
        self.label_3.grid(row=0, column=5, sticky=S)
        self.mtrPositionBox.grid(row=1, column=3, padx=10)
        self.mtrCurrentBox.grid(row=1, column=4, padx=10)
        self.e_setPos.grid(row=3, column=3, padx=2, sticky=S)
        self.e_goTo.grid(row=3, column=4, padx=2, sticky=S)
        self.e_inc.grid(row=3, column=5, padx=2, sticky=S)
        self.set_pos.grid(row=4, column=3, pady=5, sticky=N)
        self.go_to.grid(row=4, column=4, pady=5, sticky=N)
        self.inc.grid(row=4, column=5, pady=5, sticky=N)
        self.vel.grid(row=3, column=1, columnspan=2, rowspan=2, pady=22)

        # When the user clicks jog button or releases the button click these functions are called to jog the axis
        self.jog_pos.bind('<ButtonPress-1>', lambda event: self.jog_positive())
        self.jog_pos.bind('<ButtonRelease-1>', lambda event: self.stop_jog())
        self.jog_neg.bind('<ButtonPress-1>', lambda event: self.jog_negative())
        self.jog_neg.bind('<ButtonRelease-1>', lambda event: self.stop_jog())

        # A red box is drawn to represent position error and the previous box is deleted. This is initializes the first drawn box
        self.red_square = red_square = self.canvas.create_rectangle(505, 31, 505 + 61, 50, fill="SystemButtonFace", outline="SystemButtonFace")

    def toggle_axis(self):
        if self.state == 0:
            self.enable_axis()
        elif self.state == 1:
            self.disable_axis()

    def enable_axis(self):
        TIMC.acmd(self.queue, "ENABLE " + self.axisName)
        if 0b1 & int(TIMC.acmd(self.queue, "AXISSTATUS(" + self.axisName + ")")) == 1:
            self.state = 1
            self.activate_all_btns()
            if TIMC.scan.start['state'] == "disabled":
                self.inactivate_all_btns()

    def disable_axis(self):
        TIMC.acmd(self.queue, "DISABLE " + self.axisName)
        if 0b1 & int(TIMC.acmd(self.queue, "AXISSTATUS(" + self.axisName + ")")) == 0:
            self.enableButton.config(text="OFF", bg="#d3d3d3")
            self.state = 0
            self.inactivate_all_btns()

    def inactivate_all_btns(self):
        self.jog_pos.config(state="disabled")
        self.jog_neg.config(state="disabled")
        self.set_pos.config(state="disabled")
        self.go_to.config(state="disabled")
        self.inc.config(state="disabled")
        self.vel.config(state="disabled")

    def activate_all_btns(self):
        # Check the status of the axis before activating the buttons
        if 0b1 & int(TIMC.acmd(self.queue, "AXISSTATUS(" + self.axisName + ")")) == 1:
            self.state = 1
            self.enableButton.config(text="ON", bg="#00aa00", state="normal")
            self.jog_pos.config(state="active")
            self.jog_neg.config(state="active")
            self.set_pos.config(state="active")
            self.go_to.config(state="active")
            self.inc.config(state="active")
            self.vel.config(state="active")

    def set_position(self):
        posToSet = str(self.e_setPos.get())
        TIMC.acmd(self.queue, "POSOFFSET SET " + self.axisName + ", " + posToSet)

    def move_to(self):
        distance = str(self.e_goTo.get())
        if (distance == ""):
            return
        speed = str(self.vel.get())
        TIMC.acmd(self.queue, "MOVEABS " + self.axisName + " " + distance + " F " + speed)

    def move_inc(self):
        TIMC.acmd(self.queue, "ABORT " + self.axisName)
        distance = str(self.e_inc.get())
        speed = str(self.vel.get())
        TIMC.acmd(self.queue, "MOVEINC " + self.axisName + " " + distance + " F " + speed)

    def jog_positive(self):
        if self.state == 1 and self.enableButton['state'] != 'disabled' and TIMC.scan.scan_flag == 0:
            TIMC.acmd(self.queue, "ABORT " + self.axisName)
            speed = str(self.vel.get())
            TIMC.acmd(self.queue, "FREERUN " + self.axisName + " " + speed)

    def jog_negative(self):
        if self.state == 1 and self.enableButton['state'] != 'disabled' and TIMC.scan.scan_flag == 0:
            TIMC.acmd(self.queue, "ABORT " + self.axisName)
            speed = str(-1 * self.vel.get())
            TIMC.acmd(self.queue, "FREERUN " + self.axisName + " " + speed)

    def stop_jog(self):
        if (TIMC.online and TIMC.scan.scan_flag == 0):
            TIMC.acmd(self.queue, "FREERUN " + self.axisName + " 0")

    def updatePosError(self, error):
        # Max Error for x1 = 401+61 = 462
        calc_error = int(abs((error / self.max_pos_error)) * 73)
        # 61 pixels is the maximum length of the box
        if calc_error > 73:
            calc_error = 73
        x0 = 505
        y0 = 31
        x1 = x0 + calc_error
        y1 = 50

        # Delete the old representation of position error
        self.canvas.delete(self.red_square)
        # Draw the new position error box
        self.red_square = self.canvas.create_rectangle(x0, y0, x1, y1, fill="red", outline="red")


# Will create a scan frame with all buttons, entry boxes, and scales
class ScanFrame:
    def __init__(self, master, parameters):

        mainFrame = Frame(master, borderwidth=2, relief=SUNKEN)
        topFrame = Frame(mainFrame)
        leftFrame = Frame(mainFrame)
        middleFrame = Frame(mainFrame)
        rightFrame = Frame(mainFrame)

        rightFrame.grid(row=1, column=2)
        middleFrame.grid(row=1, column=1)
        leftFrame.grid(row=1, column=0)
        topFrame.grid(row=0, column=0, columnspan=3)
        mainFrame.pack(fill=X, padx=5, pady=5)
        mainFrame.pack()

        self.scanType = IntVar()
        self.scanTimeText = StringVar()
        self.scanTimeText.set("00:00:00")
        self.queue = parameters.queue_name

        # LEFT FRAME WIDGETS
        self.start = Button(topFrame, text="START", font="Courier, 12 bold", activeforeground="black", activebackground="#00aa00",
                            bg="#00aa00", width=10, command=lambda: self.start_scan())
        self.stop = Button(topFrame, text="STOP", font="Courier, 12 bold", activeforeground="black", activebackground="#00aa00",
                           bg="#00aa00", width=10, state=DISABLED, command=lambda: self.stop_scan())
        self.pause = Button(topFrame, text="PAUSE", activeforeground="black", activebackground="#00aa00",
                            bg="#00aa00", width=8, state=DISABLED, command=lambda: self.pause_scan())
        self.resume = Button(topFrame, text="RESUME", activeforeground="black",
                             activebackground="#00aa00", bg="#00aa00", width=8, state=DISABLED,
                             command=lambda: self.resume_scan())
        self.scanVelocity = Scale(leftFrame, from_=parameters.scanSpeedMin, to=parameters.scanSpeedMax,
                                  orient=HORIZONTAL,
                                  length=175,
                                  label="  Scan Speed " + parameters.scanAxisUnits + "/sec", font="Courier, 12",
                                  resolution=parameters.scanSpeedRes)
        self.indexVelocity = Scale(leftFrame, from_=parameters.indexSpeedMin, to=parameters.indexSpeedMax,
                                   orient=HORIZONTAL,
                                   length=175,
                                   label="    Index Speed " + parameters.indexAxisUnits + "/sec", font="Courier, 12",
                                   resolution=parameters.indexSpeedRes)
        self.scanVelocity.set((parameters.scanSpeedMax - parameters.scanSpeedMin) * 0.25)
        self.indexVelocity.set((parameters.indexSpeedMax - parameters.indexSpeedMin) * 0.25)
        self.label_0 = Label(topFrame, text=parameters.axisName, height=1, font=("Helvetica", 14))
        self.label_1 = Label(rightFrame, text="Scan Start (deg)", font="Courier, 12")
        self.label_2 = Label(rightFrame, text="Scan Stop (deg)", font="Courier, 12")
        self.label_3 = Label(rightFrame, text="Index Start (in)", font="Courier, 12")
        self.label_4 = Label(rightFrame, text="Index Stop (in)", font="Courier, 12")
        self.label_5 = Label(rightFrame, text="Index Size (in)", font="Courier, 12")
        self.label_6 = Label(middleFrame, text="Remaining Time", font="Courier, 12")

        self.e_scanStart = Entry(rightFrame, width=8, font="Courier, 12")
        self.e_scanStop = Entry(rightFrame, width=8, font="Courier, 12")
        self.e_indexStart = Entry(rightFrame, width=8, font="Courier, 12")
        self.e_indexStop = Entry(rightFrame, width=8, font="Courier, 12")
        self.e_indexSize = Entry(rightFrame, width=8, font="Courier, 12")
        self.radio_0 = Radiobutton(middleFrame, text="Bi-directional", font="Courier, 12", variable=self.scanType, value=0)
        self.radio_1 = Radiobutton(middleFrame, text="Uni-directional", font="Courier, 12", variable=self.scanType, value=1)
        self.time = Entry(middleFrame, state="readonly", width=8, font="Courier, 12", textvariable=self.scanTimeText)
        self.scan_flag = 0

        # GRID TOP
        rowSpaceTop = 32
        self.label_0.grid(row=0, column=0, columnspan=5, sticky=W)
        self.start.grid(row=1, column=0, pady=5, padx=rowSpaceTop)
        self.stop.grid(row=1, column=1, pady=5, padx=rowSpaceTop)
        self.pause.grid(row=1, column=2, pady=5, padx=rowSpaceTop)
        self.resume.grid(row=1, column=3, pady=5, padx=rowSpaceTop)

        # GRID LEFT
        self.scanVelocity.grid(row=0, column=0, padx=5)
        self.indexVelocity.grid(row=1, column=0, padx=5, pady=5)

        # GRID MIDDLE
        middleFrame.grid_rowconfigure(2, minsize=20)
        self.radio_0.grid(row=0, column=0, sticky=W, padx=20)
        self.radio_1.grid(row=1, column=0, sticky=W, padx=20)
        self.label_6.grid(row=3, column=0)
        self.time.grid(row=4, column=0)

        # GRID RIGHT
        rowSpaceRight = 1
        self.label_1.grid(row=2, column=3, pady=rowSpaceRight)
        self.label_2.grid(row=3, column=3, pady=rowSpaceRight)
        self.label_3.grid(row=4, column=3, pady=rowSpaceRight)
        self.label_4.grid(row=5, column=3, pady=rowSpaceRight)
        self.label_5.grid(row=6, column=3, pady=rowSpaceRight)
        self.e_scanStart.grid(row=2, column=4)
        self.e_scanStop.grid(row=3, column=4)
        self.e_indexStart.grid(row=4, column=4)
        self.e_indexStop.grid(row=5, column=4)
        self.e_indexSize.grid(row=6, column=4)

    def start_scan(self):

        # Get user data and store to variable array to check for correct type of input
        check_data = [self.e_scanStart.get(), self.e_scanStop.get(), self.e_indexStart.get(), self.e_indexStop.get(), self.e_indexSize.get()]

        # Check if user has entered numbers and/or one decimal place and/or a negative only at the beginning
        for i in range(0,4):
            # Check if user has entered data
            if(check_data[i] == ""):
                messagebox.showinfo("Bad Scan Input", "User must enter all five scan window inputs")
                return
            # If there is a negative sign
            if("-" in check_data[i]):
                # There should only be one and it should be at the beginning
                if(check_data[i].count("-") == 1 and check_data[i].index('-') == 0):
                    # Remove the negative sign and continue to next check
                    check_data[i] = check_data[i].replace("-","",1)
                else:
                    messagebox.showinfo("Bad Scan Input", "Error associated with '-' character")
                    return
            # If there is a period sign there should only be one
            if("." in check_data[i]):
                # There should only be one period
                if(check_data[i].count(".") == 1):
                    check_data[i] = check_data[i].replace(".", "", 1)
                else:
                    messagebox.showinfo("Bad Scan Input", "Error associated with '.' character")
                    return

            # Check that remaining characters are only numbers
            if(not check_data[i].isdigit()):
                messagebox.showinfo("Bad Scan Input", "Error scan inputs have characters")
                return

        # Convert user data to type float
        self.scan_start = float(self.e_scanStart.get())
        self.scan_stop = float(self.e_scanStop.get())
        self.index_start = float(self.e_indexStart.get())
        self.index_stop = float(self.e_indexStop.get())
        self.index_size = float(self.e_indexSize.get())
        self.scan_speed = float(self.scanVelocity.get())
        self.index_speed = float(self.indexVelocity.get())

        # Check user inputs for correctness as it relates to a scan
        if (self.scan_stop == self.scan_start):
            messagebox.showinfo("Bad Scan Input", "Scan Stop equals Scan Start")
            return
        if (self.index_stop == self.index_start):
            messagebox.showinfo("Bad Scan Input", "Index Stop equals Index Start")
            return
        if (self.index_stop > self.index_start):
            messagebox.showinfo("Bad Scan Input", "Index Start must be greater than Index Stop")
            return

        rounded = round((self.index_stop - self.index_start) / self.index_size)
        actual = (self.index_stop - self.index_start) / self.index_size

        if (rounded != round(actual,10)):
            messagebox.showinfo("Bad Scan Input", "Index Size must be a multiple of Index Start - Index Stop")
            return

        #Check to make sure both scan axes are enabled
        scan_status = int(TIMC.acmd(self.queue, "AXISSTATUS(CIRC)"))
        scan_enabled = 0b1 & scan_status

        index_status = int(TIMC.acmd(self.queue, "AXISSTATUS(TRANSLATOR)"))
        index_enabled = 0b1 & index_status

        if(scan_enabled != 1 or index_enabled != 1):
            messagebox.showinfo("Error with Scan", "One or both of the axes are not enabled")
            return

        # Calculate the scan points with the given user input, self.scan_points will be created and initialized
        self.create_scan_points()

        #Prepare the buttons in the GUI for a scan by disabling most
        self.deactivate_scan_widgets()
        TIMC.CIRC.inactivate_all_btns()
        TIMC.CIRC.enableButton.config(state="disabled")
        TIMC.TRANSLATOR.inactivate_all_btns()
        TIMC.TRANSLATOR.enableButton.config(state="disabled")

        # Scan flag is used to keep the axis from being able to be commanded to jog
        self.scan_flag = 1
        if(self.scanType.get() == 1):
            scan_type = "UNI-DIRECTIONAL"
        elif(self.scanType.get() == 0):
            scan_type = "BI-DIRECTIONAL"

        # Create a scan thread which will command movements to each scan point in self.scan_points
        self.process_scan = ScanThread(self.scan_points,
                                       self.scan_speed,
                                       self.index_speed,
                                       self.scan_start,
                                       self.scan_stop,
                                       self.index_start,
                                       self.index_stop,
                                       self.index_size,
                                       scan_type,
                                       self.queue)
        self.process_scan.start()

    def stop_scan(self):
        self.process_scan.stop()

    def pause_scan(self):
        self.process_scan.pause()

    def resume_scan(self):
        self.process_scan.resume()

    # Method calculates the scan points based on the user input
    def create_scan_points(self):
        # Scan type variable: 0 = bidirectional, 1 unidirectional

        # Variables for generating scan points
        i_var = self.index_start + self.index_size      # Initialize index variable
        s_var = self.scan_start                         # Initialize scan variable
        s_toggle = [self.scan_start, self.scan_stop]    # Toggle values for the scan axis scan points
        x = 0                                           # Toggle control variable

        # Calculate the number of points in the scan
        # Uni-directional
        if (self.scanType.get() == 1):
            size = int(abs(self.index_stop - self.index_start) / self.index_size * 3 + 3)

        # Bi-directional
        elif (self.scanType.get() == 0):
            size = int(abs(self.index_stop - self.index_start) / self.index_size * 2 + 2)

        # 2D array for scan points [scan][index]
        w, h = 2, size
        self.scan_points = [[0 for x in range(w)] for y in range(h)]

        # Calculate scan points and store to 2D array scan_points
        # Uni-directional
        if (self.scanType.get() == 1):
            for i in range(0, size):
                # Set s_var
                if (i % 3 == 1):
                    s_var = self.scan_stop
                # Increment i_var
                elif (i % 3 == 0):
                    i_var -= self.index_size
                else:
                    s_var = self.scan_start
                self.scan_points[i][0] = s_var
                self.scan_points[i][1] = i_var

        # Bi-directional
        elif (self.scanType.get() == 0):
            for i in range(0, size):
                # Toggle s_var
                if (i % 2):
                    x = 1 if x == 0 else 0
                    s_var = s_toggle[x]
                # Increment i_var
                else:
                    i_var -= self.index_size
                self.scan_points[i][0] = s_var
                self.scan_points[i][1] = i_var

    # At the conclusion of a scan or stopped scan, activate all widgets for scan
    def activate_scan_widgets(self):
        # Configure widgets in scan frame
        self.start.config(state="active")
        self.stop.config(state="disabled")
        self.pause.config(state="disabled")
        self.resume.config(state="disabled")
        self.e_scanStart.config(state="normal")
        self.e_scanStop.config(state="normal")
        self.e_indexStart.config(state="normal")
        self.e_indexStop.config(state="normal")
        self.e_indexSize.config(state="normal")
        self.radio_0.config(state="normal")
        self.radio_1.config(state="normal")
        self.scanVelocity.config(state="normal")
        self.indexVelocity.config(state="normal")
        self.scanTimeText.set("00:00:00")

        # If scan motion is taking place, abort the movement
        time.sleep(0.25)
        TIMC.acmd(self.queue, "ABORT CIRC")
        TIMC.acmd(self.queue, "ABORT TRANSLATOR")

    # Prepares scan window widgets for scan by disabling all inputs
    def deactivate_scan_widgets(self):
        self.start.config(state="disabled")
        self.stop.config(state="active")
        self.pause.config(state="active")
        self.e_scanStart.config(state="disabled")
        self.e_scanStop.config(state="disabled")
        self.e_indexStart.config(state="disabled")
        self.e_indexStop.config(state="disabled")
        self.e_indexSize.config(state="disabled")
        self.radio_0.config(state="disabled")
        self.radio_1.config(state="disabled")
        self.scanVelocity.config(state="disabled")
        self.indexVelocity.config(state="disabled")


# Scan thread will assess the status of each axis, command movement to next scan point, if the axis are
# in position after a commanded move then increment to next scan point
class ScanThread(threading.Thread):
    def __init__(self, scan_points, scan_speed, index_speed, scan_start, scan_stop, index_start, index_stop,
                 index_size, scan_type, queue):
        threading.Thread.__init__(self)
        self._is_running = 1
        self._is_paused = 0
        self.scan_points = scan_points
        self.scan_speed = scan_speed
        self.index_speed = index_speed
        self.scan_start = scan_start
        self.scan_stop = scan_stop
        self.index_start = index_start
        self.index_stop = index_stop
        self.index_size = index_size
        self.scan_type = scan_type
        self.queue = queue
        self.i = 0

        # Variables for calculating the running average movement of each axis.
        self.CIRC_moved = 0
        self.number_CIRC_moves = 0
        self.TRANSLATOR_moved = 0
        self.number_TRANSLATOR_moves = 0
        self.movement_start_time = 0
        self.movement_elapsed_time = 0
        self.avg_CIRC_move_time = abs(scan_start - scan_stop) / scan_speed
        self.avg_TRANSLATOR_move_time = abs(index_size / index_speed)
        self.last_update_time = time.time()
        self.setDaemon(True) # Set this value to true in the event the user closes the screen without stopping the scan

    def run(self):
        # Create entry in logbook for start of scan
        TIMC.acmd("LOG", "LOG SCAN STARTED: " + self.scan_type + ", " + str(self.scan_start) + ", " + str(
            self.scan_stop) + ", " + str(self.index_start) + ", " + str(self.index_stop) + ", " + str(
            self.index_size) + "\n")

        while (self._is_running):
            time.sleep(SCAN_THREAD_WAIT)

            # If a second has elapsed then call the method to update the remaining scan time
            if ((time.time() - self.last_update_time) > 1 and self.i != 0 and self.i < len(self.scan_points)):
                self.calc_rem_scan_time()

            # Check the status of each axis to determine if it is time to move to the next scan point
            scan_status = int(TIMC.acmd(self.queue, "AXISSTATUS(CIRC)"))
            scan_enabled = 0b1 & scan_status
            scan_in_pos = 0b100 & scan_status

            index_status = int(TIMC.acmd(self.queue, "AXISSTATUS(TRANSLATOR)"))
            index_enabled = 0b1 & index_status
            index_in_pos = 0b100 & index_status

            # Check if CIRC and TRANSLATOR are in position and not disabled
            if (scan_enabled and scan_in_pos and self._is_paused != 1 and index_enabled and index_in_pos):
                # If both axes are not faulted, they are in position, and there are scan points remaining, then command movement
                if self.i < (len(self.scan_points)):
                    # Command CIRC to move to next scan point
                    TIMC.acmd(self.queue,
                              "MOVEABS CIRC " + str(self.scan_points[self.i][0]) + " F " + str(
                                  self.scan_speed))
                    # Check if CIRC is in position despite being told to move to the next scan point.
                    scan_status = int(TIMC.acmd(self.queue, "AXISSTATUS(CIRC)"))
                    scan_enabled = 0b1 & scan_status
                    scan_in_pos = 0b100 & scan_status
                    # If the CIRC is in position then the TRANSLATOR axis needs to be commanded to move
                    if (scan_enabled and scan_in_pos and self._is_paused != 1):
                        # Command TRANSLATOR to move to next scan point
                        TIMC.acmd(self.queue,
                                  "MOVEABS TRANSLATOR " + str(self.scan_points[self.i][1]) + " F " + str(
                                      self.index_speed))
                        # Check if TRANSLATOR is in position despite being told to move to the next scan point.
                        index_status = int(TIMC.acmd(self.queue, "AXISSTATUS(TRANSLATOR)"))
                        index_enabled = 0b1 & index_status
                        index_in_pos = 0b100 & index_status
                        # If both axes are in position then movement is complete and the scan points index must be incremented
                        if (index_enabled and index_in_pos and self._is_paused != 1):
                            # Movement complete, calculate move time for each axis
                            if (self.i == 0):
                                self.movement_start_time = time.time()
                            else:
                                self.movement_elapsed_time = time.time() - self.movement_start_time + self.movement_elapsed_time
                                self.CIRC_moved = self.scan_points[self.i][0] - self.scan_points[self.i - 1][0]
                                self.TRANSLATOR_moved = self.scan_points[self.i][1] - self.scan_points[self.i - 1][1]
                                if (self.CIRC_moved):
                                    self.avg_CIRC_move_time = (
                                            self.avg_CIRC_move_time * self.number_CIRC_moves + self.movement_elapsed_time)
                                    self.number_CIRC_moves += 1
                                    self.avg_CIRC_move_time /= self.number_CIRC_moves
                                elif (self.TRANSLATOR_moved):
                                    self.avg_TRANSLATOR_move_time = (
                                            self.avg_TRANSLATOR_move_time * self.number_TRANSLATOR_moves + self.movement_elapsed_time)
                                    self.number_TRANSLATOR_moves += 1
                                    self.avg_TRANSLATOR_move_time /= self.number_TRANSLATOR_moves
                                # Reset time variables
                                self.movement_start_time = time.time()
                                self.movement_elapsed_time = 0

                            # Ready for next scan point
                            self.i += 1
                else:
                    messagebox.showinfo("", "Scan is Complete")
                    TIMC.acmd("LOG", "LOG SCAN COMPLETE")
                    self.stop()
            # Scan or index has faulted has faulted
            elif (scan_enabled == 0 or index_enabled == 0):
                self.pause()

    # This method is called when the "STOP" button is pressed or the end of scan has been reached
    def stop(self):
        # Setting the scan as paused immediately stops sending movement commands
        self._is_paused = 1
        TIMC.acmd(self.queue, "ABORT CIRC")
        TIMC.acmd(self.queue, "ABORT TRANSLATOR")
        self._is_running = 0

        # Axis enable buttons were previously disabled
        TIMC.CIRC.enableButton.config(state="normal")
        TIMC.TRANSLATOR.enableButton.config(state="normal")

        # All other buttons needs to be restored to active state
        TIMC.scan.activate_scan_widgets()
        TIMC.CIRC.activate_all_btns()
        TIMC.TRANSLATOR.activate_all_btns()

        # Setting this allows the jog buttons to be active again
        TIMC.scan.scan_flag = 0

        # Create a log entry
        TIMC.acmd("LOG", "LOG SCAN STOPPED \n")

    # This method is called when the "PAUSE" button is pressed or an axis has faulted
    def pause(self):
        # If this is the first time calling pause, put an entry in the log book.
        if (self._is_paused == 0):
            TIMC.acmd("LOG", "LOG SCAN PAUSED \n")
        self._is_paused = 1
        TIMC.acmd(self.queue, "ABORT CIRC")
        TIMC.acmd(self.queue, "ABORT TRANSLATOR")
        TIMC.scan.pause.config(state="disabled")
        TIMC.scan.resume.config(state="active")
        # Axis enable buttons were previously disabled, in the event of a fault the user will need to enable the axis after resetting the fault
        TIMC.CIRC.enableButton.config(state="normal")
        TIMC.TRANSLATOR.enableButton.config(state="normal")
        # The move times are recorded for the running average so the elapsed timer must be paused
        self.movement_elapsed_time = time.time() - self.movement_start_time

    # This method is called when the "RESUME" button is pressed
    def resume(self):
        self._is_paused = 0
        TIMC.scan.pause.config(state="active")
        TIMC.scan.resume.config(state="disabled")
        # Axis enable buttons were enabled when the PAUSE button was pressed
        TIMC.CIRC.enableButton.config(state="disabled")
        TIMC.TRANSLATOR.enableButton.config(state="disabled")
        self.movement_start_time = time.time()
        # Create entry in log book
        TIMC.acmd("LOG", "LOG SCAN RESUMED \n")

    # Method to calculate and update the timer in the scan window
    def calc_rem_scan_time(self):
        CIRC_pos = float(TIMC.acmd(self.queue, "PFBKPROG(CIRC)"))
        TRANSLATOR_pos = float(TIMC.acmd(self.queue, "PFBKPROG(TRANSLATOR)"))
        scan_time = 0

        # Determine which axis is moving
        self.CIRC_moving = abs(self.scan_points[self.i][0] - self.scan_points[self.i - 1][0])
        self.TRANSLATOR_moving = abs(self.scan_points[self.i][1] - self.scan_points[self.i - 1][1])
        # Calculate time to complete move to next scan point
        if (self.CIRC_moving and self.TRANSLATOR_moving == 0 and self.i != (len(self.scan_points) - 1)):
            scan_time = abs(CIRC_pos - self.scan_points[self.i][0]) / self.scan_speed
        elif (self.TRANSLATOR_moving and self.CIRC_moving == 0):
            scan_time = abs(TRANSLATOR_pos - self.scan_points[self.i][1]) / self.index_speed
        # If not on the last move, then calculate remaining scan time
        for i in range(self.i+1, len(self.scan_points)):
            CIRC_move = abs(self.scan_points[i][0] - self.scan_points[i - 1][0])
            TRANSLATOR_move = abs(self.scan_points[i][1] - self.scan_points[i - 1][1])
            if (CIRC_move and TRANSLATOR_move == 0):
                scan_time += self.avg_CIRC_move_time
            elif (TRANSLATOR_move and CIRC_move == 0):
                scan_time += self.avg_TRANSLATOR_move_time

        hours = int(scan_time / 3600)
        mins = int((scan_time - (hours * 3600)) / 60)
        seconds = int(scan_time - hours * 3600 - mins * 60)
        TIMC.scan.scanTimeText.set(str(hours).zfill(2) + ":" + str(mins).zfill(2) + ":" + str(seconds).zfill(2))


# Fault frame to display fault text and fault reset button to clear faults
class FaultFrame:
    def __init__(self, master):
        self.frame = Frame(master, borderwidth=2, relief=SUNKEN)
        self.canvas = Canvas(self.frame, highlightthickness=0)
        self.canvas.grid(row=0, column=0)
        self.frame.pack(fill=X, padx=5, pady=5)
        self.frame.pack()
        self.status_text = StringVar()

        self.label_0 = Label(self.canvas, text="FAULT STATUS", height=1, font=("Helvetica", 14))
        self.button = Button(self.canvas, text="FAULT\nRESET", font="Courier, 12", fg="black", bg="#d3d3d3", height=2,
                             width=6, command=lambda: self.fault_ack())
        self.entry = Entry(self.canvas, width=50, textvariable=self.status_text, font="Courier, 12")
        self.label_0.grid(row=0, column=0, columnspan=2, sticky=W)
        self.entry.grid(row=1, column=0, columnspan=2, padx=30)
        self.button.grid(row=1, column=2, pady=5, padx=5)

    # Method to display the fault text and change the background color to red
    def update_status(self, text):
        self.canvas.config(bg="red")
        self.label_0.config(bg="red")
        self.status_text.set(text)
    # Method to reset the fault and change background color back to default
    def fault_ack(self):
        if (TIMC.online):
            TIMC.acmd("CTRL", "ACKNOWLEDGEALL")
            self.canvas.config(bg="SystemButtonFace")
            self.label_0.config(bg="SystemButtonFace")
            self.status_text.set("")


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
        while(self._is_running):
            time.sleep(1)
            s_fault = int(TIMC.acmd("STATUS", "AXISFAULT (CIRC)"))
            p_fault = int(TIMC.acmd("STATUS", "AXISFAULT (TRANSLATOR)"))

            # Bitwise AND the fault data with a mask to check specifically for ESTOP
            if (0b100000000000 & s_fault or 0b100000000000 & p_fault):
                TIMC.fault.update_status("ESTOP was pressed")
                TIMC.CIRC.disable_axis()
                TIMC.TRANSLATOR.disable_axis()
            else:
                faultMask = 1
                # If there is a fault and CIRC is not yet disabled
                if (s_fault != 0):
                    TIMC.CIRC.disable_axis()
                    # Create fault masks to bitwise AND the data to determine which type of fault has occured.
                    for i in range(0, len(self.fault_array)):
                        if ((s_fault & (faultMask << i)) != 0):
                            TIMC.fault.update_status("FAULT: CIRC " + str(self.fault_array[i]))

                # If there is a fault and TRANSLATOR is not yet disabled
                if (p_fault != 0):
                    TIMC.TRANSLATOR.disable_axis()
                    # Create fault masks to bitwise AND the data to determine which type of fault has occured.
                    for i in range(0, len(self.fault_array)):
                        if ((p_fault & (faultMask << i)) != 0):
                            TIMC.fault.update_status("FAULT: TRANSLATOR " + str(self.fault_array[i]))

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
        self.write_cmd = ["PFBKPROG(CIRC)", "IFBK(CIRC)", "PERR(CIRC)", "PFBKPROG (TRANSLATOR)", "IFBK(TRANSLATOR)",
                          "PERR(TRANSLATOR)"]
    def run(self):
        while (self._is_running):
            time.sleep(THREAD_WAIT)
            # If there is something in the read queue, update the correct variable
            if (TIMC.qFBK_read.qsize()):

                data = TIMC.qFBK_read.get()
                data = data.replace("%", "")
                if (self.read_index == 0):
                    pos = round(float(data), 2)
                    pos = format(pos, '.2f')
                    TIMC.CIRC.mtr_position.set(pos)
                    self.read_index += 1
                elif (self.read_index == 1):
                    cur = float(data) * 1000
                    cur = round(cur)
                    TIMC.CIRC.mtr_current.set(cur)
                    self.read_index += 1
                elif (self.read_index == 2):
                    err = data.replace("\n", "")
                    err = float(err)
                    TIMC.CIRC.updatePosError(err)
                    self.read_index += 1
                elif (self.read_index == 3):
                    pos = round(float(data), 2)
                    pos = format(pos, '.2f')
                    TIMC.TRANSLATOR.mtr_position.set(pos)
                    self.read_index += 1
                elif (self.read_index == 4):
                    cur = float(data) * 1000
                    cur = round(cur)
                    TIMC.TRANSLATOR.mtr_current.set(cur)
                    self.read_index += 1
                elif (self.read_index == 5):
                    err = data.replace("\n", "")
                    err = float(err)
                    TIMC.TRANSLATOR.updatePosError(err)
                    self.read_index = 0

            # Auto-populate the feedback write queue with commands so the queue is never empty
            if (TIMC.qFBK_write.qsize() == 0):
                TIMC.qFBK_write.put(self.write_cmd[self.write_index])
                if (self.write_index < 5):
                    self.write_index += 1
                else:
                    self.write_index = 0
    def stop(self):
        self._is_running = 0


# Thread to updated the log file. All commands send to the Aerotech drive are sent to this thread 
# which decides what information to keep
class UpdateLog(threading.Thread):

    def __init__(self, queue, fault_array):
        threading.Thread.__init__(self)
        self._is_running = 1
        self.fault_flag = 0
        self.queue = queue
        self.fault_array = fault_array

        # Create log file with date and time as apart of the file name
        text = "JPIT_LOG_" + str(time.strftime("%Y-%m-%d__%H-%M-%S", time.localtime())) + ".txt"
        self.file = open(text, "w+")
        self.print_header()

        # Set variable to monitor if day has changed
        now = datetime.datetime.now()
        self.day = now.day

    def run(self):
        while(self._is_running):
            time.sleep(THREAD_WAIT)
            if (self.queue.qsize()):
                # Remove unnecessary text from the command
                data = self.queue.get()
                data = data.replace("b'","")
                data = data.replace("\n", "")
                data = data.replace("\\n","")
                data = data.replace("%", "")
                data = data.replace("'","")
                # Eliminate all results from feedback, log file would too large if this data was kept
                if("FBK :" not in data):
                    # "STAT:" has information about ESTOP or Faults, save this data if there is a fault
                    if("STAT:" in data):
                        data = data.replace("STAT:", "")
                        if("CIRC" in data):
                            data = int(data.replace("AXISFAULT (CIRC)", ""))
                            # If there is a fault data will be a number other than 0
                            if (data and self.fault_flag == 0):
                                # Check which type of fault occurred with Bitwise AND and a fault mask
                                for i in range(0, len(self.fault_array)):
                                    faultMask = 1
                                    if ((data & (faultMask << i)) != 0):
                                        self.fault_flag = 1
                                        if(i == 11):
                                            self.file.write(self.pt() + "ESTOP Pressed\n")
                                        else:
                                            self.file.write(self.pt() + "FAULT: CIRC " + str(self.fault_array[i]) + '\n')

                        elif("TRANSLATOR" in data):
                            data = int(data.replace("AXISFAULT (TRANSLATOR)", ""))
                            # If there is a fault data will be a number other than 0
                            if (data and self.fault_flag == 0):
                                # Check which type of fault occurred with Bitwise AND and a fault mask
                                for i in range(0, len(self.fault_array)):
                                    faultMask = 1
                                    if ((data & (faultMask << i)) != 0):
                                        self.fault_flag = 1
                                        if (i == 11):
                                            self.file.write(self.pt() + "ESTOP Pressed\n")
                                        else:
                                            self.file.write(self.pt() + "FAULT: TRANSLATOR " + str(self.fault_array[i]) + '\n')
                    # CTRL: has information about buttons pressed in the axisframe, but filter out data about AXISSTATUS
                    elif("CTRL:" in data and not "STATUS" in data and not "ABORT" in data):
                        if("ACKNOWLEDGEALL" in data):
                            self.file.write(self.pt() + "ACKNOWLEDGEALL\n")
                            self.fault_flag = 0
                        else:
                            self.file.write(self.pt() + data + '\n')
                    elif("LOG" in data):
                        self.file.write(self.pt() + data + '\n')

    def stop(self):
        self._is_running = 0
        time.sleep(0.5)
        self.file.close()

    # Method to print the time
    def pt(self):
        # Check if the day has changed
        now = datetime.datetime.now()
        if(self.day != now.day):
            self.new_day()      # Insert a new day into the log file
            self.day = now.day  # Update current day
        # Return the time for the log entry
        result = time.strftime("%H:%M:%S ", time.localtime())
        return result

    # Header at the beginning of the log file
    def print_header(self):
        self.file.write("===============================================================\n")
        self.file.write("          Tooling Inspection Motion Controller - JPIT          \n")
        self.file.write("                       Code Revision: 1                        \n")
        self.file.write("                         - LOG FILE -                          \n")
        self.file.write("===============================================================\n")
        self.file.write("Controller Initialized:\n")
        self.file.write("    Date: " + time.strftime("%Y-%m-%d", time.localtime()) + '\n')
        self.file.write("    Time: " + time.strftime("%H:%M:%S", time.localtime()) + '\n')
        self.file.write("    COM Port: \n")
        self.file.write("    File: " + sys.argv[0] + "\n\n")
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



# Function that is called when the user closes the screen
def on_closing():
    print("Closing...")
    exception_flag = 0
    if(TIMC.online):
        print("Disconnecting...")
        try:
            TIMC.CIRC.disable_axis()
        except:
            exception_flag = 1
        try:
            TIMC.TRANSLATOR.disable_axis()
        except:
            exception_flag = 1
        try:
            process_status.stop()
        except:
            exception_flag = 1
        try:
            process_log.stop()
        except:
            exception_flag = 1
        try:
            process_feedback.stop()
        except:
            exception_flag = 1
        try:
            time.sleep(0.5)
            TIMC.process_serial.stop()
        except:
            exception_flag = 1


    if exception_flag == 1:
        print("ERROR CLOSING A THREAD")

    root.destroy()

######################################
#             Main Code              #
######################################


root = Tk()
TIMC = MainWindow(root, SetupMainWindow())

if TIMC.online:
    # Start thread to updated position, current and error feedback for each axis
    process_feedback = UpdateFeedback()
    process_feedback.start()

    # Start thread to monitor for ESTOP and faults etc.
    process_status = UpdateStatus()
    process_status.start()

    # Start thread for generating log file
    process_log = UpdateLog(TIMC.qLog_write1, process_status.fault_array)
    process_log.start()

    # If axis are enabled at startup, disabled them
    TIMC.CIRC.disable_axis()
    TIMC.TRANSLATOR.disable_axis()

# Start the update loop for the GUI and define what to do when closing the GUI
root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()

