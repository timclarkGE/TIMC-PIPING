##############################################
# Tooling Inspection Motion Controller GUI   #
# Tool: Jet Pump Beam UT                     #
# PLM Code Storage:  DOC-0009-1257           #
# PLM Parameter File Storage: DOC-0009-1258  #
# Code Revision: 0                           #
##############################################
# Revision Updates:
#   N/A

# Author:   Timothy Clark
# Email:    timoty.clark@ge.com
# Date:     08/22/2018
# Company:  GE Hitachi
# Description
#   - Graphical User Interface using Tkinter package
#   - Requires python 3.6
#   - Lienar amplifiers to reduce EMI: Aerotech Ensemble ML
#   - Serial communication with Aerobasic ASCII commands
#
#
# ###########################################################


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
        self.gui_width = 485
        self.gui_height = 222
        self.baud = 115200


class SetupScanAxisFrame:
    def __init__(self):
        self.axisName = "SCAN"
        self.axisUnits = "in"
        self.jogText1 = "BACKWARD"
        self.jogText2 = "FORWARD"
        self.speedMin = 0.01
        self.speedMax = 1
        self.speedRes = 0.01
        self.maxError = 0.1
        self.queue_name = "CTRL"


# Main GUI window which contains the four other frames: Scan, Status Frame
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
        master.title("Tooling Inspection Motion Controller - Jet Pump Beam UT")

        # Create frames for each axis and function
        self.scan = AxisFrame(self.master, SetupScanAxisFrame())
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
                print("(!) Bad Execution, Queue:",queue_name,"CMD:",text)
                return 0
            elif "#" in data:
                print("(#) ACK but cannot execute, Queue:",queue_name,"CMD:",text)
                return 0
            elif "$" in data:
                print("($) CMD timeout, Queue:",queue_name,"CMD:",text)
                return 0
            elif data == "":
                print("No data returned, check serial connection, Queue:",queue_name,"CMD:",text)
                return 0
            # If the command was successful, and the command sent requested data fro the controller, the "%" precedes the returned data
            elif "%" in data:
                data = data.replace("%", "")
                return data
            else:
                print("Error")
        # process_serial will transfer data from this queue to the main queue processed by process_log
        else:
            self.qLog_write2.put(text)
    # process_serial attempts to communicate with the Aerotech drive, if communcation is not successful then disabled buttons
    def init_communication(self):
        if (self.process_serial.port_open == 0):
            self.fault.update_status("OFFLINE MODE")
            self.scan.enableButton.config(state="disabled")
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

        self.enableButton = Button(self.canvas, text="OFF", fg="black", bg="#d3d3d3", height=2, width=6, padx=3, pady=3,
                                   command=lambda: self.toggle_axis())
        self.jog_neg = Button(self.canvas, text=parameters.jogText1, activeforeground="black",
                              activebackground="#00aa00",
                              bg="#00aa00", width=10, state=DISABLED)
        self.jog_pos = Button(self.canvas, text=parameters.jogText2, activeforeground="black",
                              activebackground="#00aa00",
                              bg="#00aa00", width=10, state=DISABLED)
        self.set_pos = Button(self.canvas, text=" Set ", activeforeground="black", activebackground="#00aa00",
                              bg="#00aa00",
                              state=DISABLED, command=lambda: self.set_position())
        self.go_to = Button(self.canvas, text="GoTo", activeforeground="black", activebackground="#00aa00",
                            bg="#00aa00",
                            state=DISABLED, command=lambda: self.move_to())
        self.inc = Button(self.canvas, text="Index", activeforeground="black", activebackground="#00aa00", bg="#00aa00",
                          state=DISABLED, command=lambda: self.move_inc())
        self.mtrPositionBox = Entry(self.canvas, state="readonly", width=10, textvariable=self.mtr_position)
        self.mtrCurrentBox = Entry(self.canvas, state="readonly", width=10, textvariable=self.mtr_current)
        self.e_setPos = Entry(self.canvas, width=10)
        self.e_goTo = Entry(self.canvas, width=10)
        self.e_inc = Entry(self.canvas, width=10)
        self.vel = Scale(self.canvas, from_=parameters.speedMin, to=parameters.speedMax, orient=HORIZONTAL, length=150,
                         label="            Velocity " + parameters.axisUnits + "/sec", resolution=parameters.speedRes)
        self.vel.set((parameters.speedMax - parameters.speedMin) * 0.25)
        self.vel.config(state="disabled")
        self.label_0 = Label(self.canvas, text=parameters.axisName, height=1, font=("Helvetica", 14))
        self.label_1 = Label(self.canvas, text="Pos. (" + parameters.axisUnits + ")")
        self.label_2 = Label(self.canvas, text="Cur. (mA)")
        self.label_3 = Label(self.canvas, text="Pos. Error")

        # Draw box for position error that looks like disabled entry box.
        self.canvas.create_line(400, 29, 463, 29, fill="#A0A0A0")
        self.canvas.create_line(400, 29, 400, 47, fill="#A0A0A0")
        self.canvas.create_line(400, 47, 464, 47, fill="white")
        self.canvas.create_line(463, 51, 463, 48, fill="white")

        # GRID
        self.label_0.grid(row=0, column=0, columnspan=5, sticky=W)
        self.enableButton.grid(row=1, column=0, rowspan=3, padx=15)
        self.jog_neg.grid(row=1, column=1, rowspan=2, padx=3)
        self.jog_pos.grid(row=1, column=2, rowspan=2, padx=3)
        self.label_1.grid(row=0, column=3, sticky=S)
        self.label_2.grid(row=0, column=4, sticky=S)
        self.label_3.grid(row=0, column=5, sticky=S)
        self.mtrPositionBox.grid(row=1, column=3, padx=3)
        self.mtrCurrentBox.grid(row=1, column=4, padx=3)
        self.e_setPos.grid(row=3, column=3, padx=2)
        self.e_goTo.grid(row=3, column=4, padx=2)
        self.e_inc.grid(row=3, column=5, padx=2)
        self.set_pos.grid(row=4, column=3, pady=5)
        self.go_to.grid(row=4, column=4, pady=5)
        self.inc.grid(row=4, column=5, pady=5)
        self.vel.grid(row=3, column=1, columnspan=2, rowspan=2)

        # When the user clicks jog button or releases the button click these functions are called to jog the axis
        self.jog_pos.bind('<ButtonPress-1>', lambda event: self.jog_positive())
        self.jog_pos.bind('<ButtonRelease-1>', lambda event: self.stop_jog())
        self.jog_neg.bind('<ButtonPress-1>', lambda event: self.jog_negative())
        self.jog_neg.bind('<ButtonRelease-1>', lambda event: self.stop_jog())

        # A red box is drawn to represent position error and the previous box is deleted. This is initializes the first drawn box
        self.red_square = red_square = self.canvas.create_rectangle(401, 30, 401 + 61, 46, fill="SystemButtonFace", outline="SystemButtonFace")


    def toggle_axis(self):
        if (self.state == 0):
            self.enable_axis()
        elif (self.state == 1):
            self.disable_axis()

    def enable_axis(self):
        TIMC.acmd(self.queue, "ENABLE " + self.axisName)
        if ((0b1 & int(TIMC.acmd(self.queue, "AXISSTATUS(" + self.axisName + ")"))) == 1):
            self.state = 1
            self.activate_all_btns()

    def disable_axis(self):
        TIMC.acmd(self.queue, "DISABLE " + self.axisName)
        if ((0b1 & int(TIMC.acmd(self.queue, "AXISSTATUS(" + self.axisName + ")"))) == 0):
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
        if ((0b1 & int(TIMC.acmd(self.queue, "AXISSTATUS(" + self.axisName + ")"))) == 1):
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
        if (self.state == 1 and self.enableButton['state'] != 'disabled'):
            TIMC.acmd(self.queue, "ABORT " + self.axisName)
            speed = str(self.vel.get())
            TIMC.acmd(self.queue, "FREERUN " + self.axisName + " " + speed)

    def jog_negative(self):
        if (self.state == 1 and self.enableButton['state'] != 'disabled'):
            TIMC.acmd(self.queue, "ABORT " + self.axisName)
            speed = str(-1 * self.vel.get())
            TIMC.acmd(self.queue, "FREERUN " + self.axisName + " " + speed)

    def stop_jog(self):
        if (TIMC.online):
            TIMC.acmd(self.queue, "FREERUN " + self.axisName + " 0")

    def updatePosError(self, error):
        # Max Error for x1 = 401+61 = 462
        calc_error = int(abs((error / self.max_pos_error)) * 61)
        # 61 pixels is the maximum length of the box
        if (calc_error > 61):
            calc_error = 61
        x0 = 401
        y0 = 30
        x1 = x0 + calc_error
        y1 = 46

        # Delete the old representation of position error
        self.canvas.delete(self.red_square)
        # Draw the new position error box
        self.red_square = self.canvas.create_rectangle(x0, y0, x1, y1, fill="red", outline="red")

# Fault frame to display fault text and fault reset button to clear faults
class FaultFrame():
    def __init__(self, master):
        self.frame = Frame(master, borderwidth=2, relief=SUNKEN)
        self.canvas = Canvas(self.frame, highlightthickness=0)
        self.canvas.grid(row=0, column=0)
        self.frame.pack(fill=X, padx=5, pady=5)
        self.frame.pack()
        self.status_text = StringVar()

        self.label_0 = Label(self.canvas, text="FAULT STATUS", height=1, font=("Helvetica", 14))
        self.button = Button(self.canvas, text="FAULT\nRESET", fg="black", bg="#d3d3d3", height=2, width=5,
                             command=lambda: self.fault_ack())
        # self.label_0 = Label(canvas, text="GE HITACHI", height=2, font=("Helvetica", 10))
        self.entry = Entry(self.canvas, width=59, textvariable=self.status_text)
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

# Thread will assess if a fault has occurred and call the apropriate methods to change the state of the GUI
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
            s_fault = int(TIMC.acmd("STATUS", "AXISFAULT (SCAN)"))

            # Bitwise AND the fault data with a mask to check specifically for ESTOP
            if (0b100000000000 & s_fault):
                TIMC.fault.update_status("ESTOP was pressed")
                TIMC.scan.disable_axis()
            else:
                faultMask = 1
                # If there is a fault and scan is not yet disabled
                if (s_fault != 0):
                    TIMC.scan.disable_axis()
                    # Create fault masks to bitwise AND the data to determine which type of fault has occured.
                    for i in range(0, len(self.fault_array)):
                        if ((s_fault & (faultMask << i)) != 0):
                            TIMC.fault.update_status("FAULT: Scan " + str(self.fault_array[i]))

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
        self.write_cmd = ["PFBKPROG(SCAN)", "IFBK(SCAN)", "PERR(SCAN)"]
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
                    TIMC.scan.mtr_position.set(pos)
                    self.read_index += 1
                elif (self.read_index == 1):
                    cur = float(data) * 1000
                    cur = round(cur)
                    TIMC.scan.mtr_current.set(cur)
                    self.read_index += 1
                elif (self.read_index == 2):
                    err = data.replace("\n", "")
                    err = float(err)
                    TIMC.scan.updatePosError(err)
                    self.read_index = 0


            # Auto-populate the feedback write queue with commands so the queue is never empty
            if (TIMC.qFBK_write.qsize() == 0):
                TIMC.qFBK_write.put(self.write_cmd[self.write_index])
                if (self.write_index < 2):
                    self.write_index += 1
                else:
                    self.write_index = 0
    def stop(self):
        self._is_running = 0

# Thread to updated the log file. All commands send to the Aerotech drive are sent to this thread which decides what information to keep
class UpdateLog(threading.Thread):

    def __init__(self, queue, fault_array):
        threading.Thread.__init__(self)
        self._is_running = 1
        self.fault_flag = 0
        self.queue = queue
        self.fault_array = fault_array

        # Create log file with date and time as apart of the file name
        text = "JPBUT_LOG_" + str(time.strftime("%Y-%m-%d__%H-%M-%S", time.localtime())) + ".txt"
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
                        if("SCAN" in data):
                            data = int(data.replace("AXISFAULT (SCAN)", ""))
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
                                            self.file.write(self.pt() + "FAULT: Scan " + str(self.fault_array[i]) + '\n')
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
        self.file.write("          Tooling Inspection Motion Controller - JPBUT         \n")
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
    exception_flag = 0
    if(TIMC.online):
        try:
            TIMC.scan.disable_axis()
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
    if(exception_flag):
        print("ERROR CLOSING A THREAD")

    root.destroy()

######################################
#             Main Code              #
######################################

root = Tk()
TIMC = MainWindow(root, SetupMainWindow())

if (TIMC.online):
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
    TIMC.scan.disable_axis()

# Start the update loop for the GUI and define what to do when closing the GUI
root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()

