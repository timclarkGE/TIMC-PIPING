"""
This program is beginning of the piping GUI, it creates 2 Axis frames, a Scan Frame, and a Fault Frame


"""

from tkinter import *
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
    def __init__(self, master):
        self.master = master

        topFrame = Frame(master, relief=SUNKEN, border=2)
        topFrame.pack(fill=X, padx=10, pady=10)
        self.toolButton = Button(topFrame, text="NOVA", fg="Black", bg="Sky Blue", font=("Helvetica", 14),
                                 command=lambda: self.toggle_tool())
        self.toolButton.pack(fill=X)

    def toggle_tool(self):
        if self.toolButton["text"] == "NOVA":
            self.toolButton.config(text="LPS-1000", fg="Black", bg="Goldenrod")
        else:
            self.toolButton.config(text="NOVA", fg="Black", bg="Sky Blue")


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
        self.frame.pack(fill=X, padx=10, pady=10)

        self.position = float(0)
        self.setToText = StringVar(master, value="0")
        self.GoToText = StringVar(master, value="0")
        self.moveIncText = StringVar(master, value="0")

        # Create Widgets
        self.label_0 = Label(self.frame, text=self.axisName, font=("Helvetica", 14))
        self.label_1 = Label(self.frame, text="Position", font=("Helvetica", 10))
        self.label_2 = Label(self.frame, text="Current", font=("Helvetica", 10))
        self.label_3 = Label(self.frame, text="Velocity", font=("Helvetica", 10))
        self.enableButton = Button(self.frame, text="OFF", fg="Red", bg="Light Grey", height=3, width=8,
                                   command=lambda: self.toggle_axis(), font=("Helvetica", 12))
        self.setToButton = Button(self.frame, text="SET TO", fg="Gray", bg="Light Grey", height=1, width=10,
                                  state="disabled", command=lambda: self.setTo())
        self.GoToButton = Button(self.frame, text="GOTO", fg="Gray", bg="Light Grey", height=1, width=10,
                                 state="disabled",
                                 command=lambda: self.GoTo())
        self.moveIncButton = Button(self.frame, text="Move Inc", fg="Gray", bg="Light Grey", height=1, width=10,
                                    state="disabled", command=lambda: self.moveInc())
        self.jogButtonFWD = Button(self.frame, text="FWD", fg="Gray", bg="Light Grey", height=1, width=10,
                                   font=("Helvetica", 12), state="disabled")
        self.jogButtonREV = Button(self.frame, text="REV", fg="Gray", bg="Light Grey", height=1, width=10,
                                   font=("Helvetica", 12), state="disabled")
        self.position_label = Label(self.frame, text=("%.2f" % self.position), bg="Light Grey", width=8,
                                    relief=SUNKEN, state="disabled", font=("Helvetica", 12))
        self.setToEntry = Entry(self.frame, textvariable=self.setToText, width=10, font="Courier, 10", justify="center")
        self.GoToEntry = Entry(self.frame, textvariable=self.GoToText, width=10, font="Courier, 10", justify="center")
        self.moveIncEntry = Entry(self.frame, textvariable=self.moveIncText, width=10, font="Courier, 10",
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
        self.position_label.grid(column=3, row=1, padx=5, pady=5, sticky=N)
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
        TIMC.acmd(self.queue, "ENABLE " + self.axisName)
        if 0b1 & int(TIMC.acmd(self.queue, "AXISSTATUS(" + self.axisName + ")")) == 1:
            self.activate_all_btns()

    # This function disables the axis
    def disable_axis(self):
        TIMC.acmd(self.queue, "DISABLE " + self.axisName)
        self.inactivate_all_btns()

    def activate_all_btns(self):
        if 0b1 & int(TIMC.acmd(self.queue, "AXISSTATUS(" + self.axisName + ")")) == 1:
            self.state = 1
            self.enableButton.config(text="ON", fg="Black", bg="Lawn Green")
            self.setToButton.config(state="normal", fg="Black", bg="Lawn Green")
            self.GoToButton.config(state="normal", fg="Black", bg="Lawn Green")
            self.moveIncButton.config(state="normal", fg="Black", bg="Lawn Green")
            self.jogButtonFWD.config(state="normal", fg="Black", bg="Lawn Green")
            self.jogButtonREV.config(state="normal", fg="Black", bg="Lawn Green")
            self.position_label.config(state="normal", bg="White")

    def inactivate_all_btns(self):
        self.state = 0
        self.enableButton.config(text="OFF", fg="Red", bg="Light Grey")
        self.setToButton.config(state="disabled", fg="Gray", bg="Light Grey")
        self.GoToButton.config(state="disabled", fg="Gray", bg="Light Grey")
        self.moveIncButton.config(state="disabled", fg="Gray", bg="Light Grey")
        self.jogButtonFWD.config(state="disabled", fg="Gray", bg="Light Grey")
        self.jogButtonREV.config(state="disabled", fg="Gray", bg="Light Grey")
        self.position_label.config(state="disabled", bg="Light Grey")

    # This function starts Jogging in the FORWARD Direction
    def jogFWD(self):
        if self.enableButton["text"] != "OFF":
            TIMC.acmd(self.queue, "ABORT " + self.axisName)
            speed = str(self.vel.get())
            TIMC.acmd(self.queue, "FREERUN " + self.axisName + " " + speed)

    # This function starts Jogging in the REVERSE Direction
    def jogREV(self):
        if self.enableButton["text"] != "OFF":
            TIMC.acmd(self.queue, "ABORT " + self.axisName)
            speed = str(-1 * self.vel.get())
            TIMC.acmd(self.queue, "FREERUN " + self.axisName + " " + speed)

    # This function stops Jogging
    def stopjog(self):
        if self.enableButton["text"] != "OFF":
            TIMC.acmd(self.queue, "FREERUN " + self.axisName + " 0")

    # This function sets the position in the position label based on Set To Entry Box
    def setTo(self):
        self.position = float(self.setToEntry.get())
        self.position_label.config(text=("%.2f" % self.position))

    def GoTo(self):
        self.position = float(self.GoToEntry.get())
        self.position_label.config(text=("%.2f" % self.position))

    def moveInc(self):
        self.position = float(self.moveIncEntry.get())
        self.position_label.config(text=("%.2f" % self.position))


# This class creates a Scan Window in the GUI
class ScanFrame:
    def __init__(self, master, parameters1, parameters2):
        self.master = master
        self.axis1 = parameters1
        self.axis2 = parameters2
        self.scanConfig = IntVar()

        frame = Frame(master, relief=SUNKEN, border=2)
        frame.pack(fill=X, padx=10, pady=10)

        self.label_0 = Label(frame, text="SCAN WINDOW", font=("Helvetica", 14))
        self.axis_label_1 = Label(frame, text=self.axis1.axisName, font=("Helvetica", 12))
        self.axis_label_2 = Label(frame, text=self.axis2.axisName, font=("Helvetica", 12))
        self.vel1 = Scale(frame, from_=self.axis1.speedMin, to=self.axis1.speedMax, orient=HORIZONTAL, length=150,
                          label="Speed " + self.axis1.axisUnits + "/sec", font=("Helvetica", 10),
                          resolution=self.axis1.speedRes)
        self.vel1.set((self.axis1.speedMax - self.axis1.speedMin) * 0.5)
        self.vel2 = Scale(frame, from_=self.axis2.speedMin, to=self.axis2.speedMax, orient=HORIZONTAL, length=150,
                          label="Speed " + self.axis2.axisUnits + "/sec", font=("Helvetica", 10),
                          resolution=self.axis2.speedRes)
        self.vel2.set((self.axis2.speedMax - self.axis2.speedMin) * 0.5)
        self.axis1_radio_0 = Radiobutton(frame, text="Scan", font="Courier, 10", variable=self.scanConfig, value=0)
        self.axis1_radio_1 = Radiobutton(frame, text="Index", font="Courier, 10", variable=self.scanConfig, value=1)
        self.axis2_radio_0 = Radiobutton(frame, text="Scan", font="Courier, 10", variable=self.scanConfig, value=1)
        self.axis2_radio_1 = Radiobutton(frame, text="Index", font="Courier, 10", variable=self.scanConfig, value=0)

        self.label_0.grid(column=0, row=0, columnspan=2, sticky=W)
        self.axis_label_1.grid(column=0, row=1, rowspan=2, sticky=E, pady=5)
        self.axis_label_2.grid(column=0, row=3, rowspan=2, sticky=E, pady=5)
        self.vel1.grid(column=1, row=1, rowspan=2, columnspan=2, pady=5)
        self.vel2.grid(column=1, row=3, rowspan=2, columnspan=2, pady=5)
        self.axis1_radio_0.grid(column=3, row=1, sticky=S)
        self.axis1_radio_1.grid(column=3, row=2, sticky=N)
        self.axis2_radio_0.grid(column=3, row=3, sticky=S)
        self.axis2_radio_1.grid(column=3, row=4, sticky=N)


# This class creates a Fault Frame in the GUI
class FaultFrame:
    def __init__(self, master):
        self.frame = Frame(master, borderwidth=2, relief=SUNKEN)
        self.canvas = Canvas(self.frame, highlightthickness=0)
        self.canvas.pack(fill=X)
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
        if TIMC.online:
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
        self.tool = ToolFrame(self.master)
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
            TIMC.fault.update_status("(!) Bad Execution, Queue: " + queue_name + " CMD: " + text)
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
            # self.circ.enableButton.config(state="disabled")
            # self.trans.enableButton.config(state="disabled")
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

    root.destroy()


root = Tk()
TIMC = Main(root)
root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()
