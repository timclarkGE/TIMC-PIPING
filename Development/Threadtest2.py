"""
This program will start a GUI with 2 axes, each with an enable and 2 jog buttons.
The jog buttons will be disabled until the enable button is toggled.
A thread is started when the jog buttons are depressed that incrementally counts depending on which direction button
    is used, and the thread is stopped when the button is released
The value is saved and used for subsequent threads
The label is updated using class inputs rather than hard-coding the axis labels

"""

from tkinter import *
import serial
import threading
import time


# This class sets Frame parameters for the Circ Axis
class SetupCircFrame:
    def __init__(self):
        self.axisName = "CIRC"
        self.axisUnits = "mm"
        self.speedMin = 0.1
        self.speedMax = 25.0
        self.speedRes = 2.5


# This class sets Frame parameters for the Trans Axis
class SetupTransFrame:
    def __init__(self):
        self.axisName = "TRANSLATOR"
        self.axisUnits = "mm"
        self.speedMin = 0.1
        self.speedMax = 50.0
        self.speedRes = 5


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
            self.toolButton.config(text="LPS-1000", fg="Black", bg="Yellow")
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

        frame = Frame(master, relief=SUNKEN, border=2)
        frame.pack(fill=X, padx=10, pady=10)

        self.position = float(0)
        self.setToText = StringVar(master, value="0")
        self.GoToText = StringVar(master, value="0")
        self.moveIncText = StringVar(master, value="0")

        # Create Widgets
        self.label_0 = Label(frame, text=self.axisName, font=("Helvetica", 14))
        self.label_1 = Label(frame, text="Position", font=("Helvetica", 10))
        self.label_2 = Label(frame, text="Current", font=("Helvetica", 10))
        self.label_3 = Label(frame, text="Velocity", font=("Helvetica", 10))
        self.enableButton = Button(frame, text="OFF", fg="Red", bg="Light Grey", height=3, width=8,
                                   command=lambda: self.toggle_axis(), font=("Helvetica", 12))
        self.setToButton = Button(frame, text="SET TO", fg="Gray", bg="Light Grey", height=1, width=10,
                                  state="disabled", command=lambda: self.setTo())
        self.GoToButton = Button(frame, text="GOTO", fg="Gray", bg="Light Grey", height=1, width=10, state="disabled",
                                 command=lambda: self.GoTo())
        self.moveIncButton = Button(frame, text="Move Inc", fg="Gray", bg="Light Grey", height=1, width=10,
                                    state="disabled", command=lambda: self.moveInc())
        self.jogButtonFWD = Button(frame, text="FWD", fg="Gray", bg="Light Grey", height=1, width=10, font=("Helvetica", 12), state="disabled")
        self.jogButtonREV = Button(frame, text="REV", fg="Gray", bg="Light Grey", height=1, width=10, font=("Helvetica", 12), state="disabled")
        self.position_label = Label(frame, text=("%.2f" % self.position), bg="Light Grey", width=8,
                                    relief=SUNKEN, state="disabled", font=("Helvetica", 12))
        self.setToEntry = Entry(frame, textvariable=self.setToText, width=10, font="Courier, 10", justify="center")
        self.GoToEntry = Entry(frame, textvariable=self.GoToText, width=10, font="Courier, 10", justify="center")
        self.moveIncEntry = Entry(frame, textvariable=self.moveIncText, width=10, font="Courier, 10", justify="center")
        self.vel = Scale(frame, from_=self.speedMin, to=self.speedMax, orient=HORIZONTAL, length=150,
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
        self.enableButton.grid(column=0, row=1, rowspan=3, padx=10, pady=10)
        self.jogButtonFWD.grid(column=1, row=1, padx=10, pady=10, sticky=N)
        self.jogButtonREV.grid(column=2, row=1, padx=10, pady=10, sticky=N)
        self.vel.grid(column=1, row=2, rowspan=2, columnspan=2, padx=5, pady=5)
        self.position_label.grid(column=3, row=1, padx=5, pady=10, sticky=N)
        self.setToEntry.grid(column=3, row=2, padx=5, pady=5)
        self.setToButton.grid(column=3, row=3, padx=5, pady=5)
        self.GoToEntry.grid(column=4, row=2, padx=5, pady=5)
        self.GoToButton.grid(column=4, row=3, padx=5, pady=5)
        self.moveIncEntry.grid(column=5, row=2, padx=5, pady=5)
        self.moveIncButton.grid(column=5, row=3, padx=5, pady=5)

# This function toggles the button between OFF and ON
    def toggle_axis(self):
        if self.enableButton["text"] == "OFF":
            self.enableButton.config(text="ON", fg="Black", bg="Lawn Green")
            self.setToButton.config(state="normal", fg="Black", bg="Lawn Green")
            self.GoToButton.config(state="normal", fg="Black", bg="Lawn Green")
            self.moveIncButton.config(state="normal", fg="Black", bg="Lawn Green")
            self.jogButtonFWD.config(state="normal", fg="Black", bg="Lawn Green")
            self.jogButtonREV.config(state="normal", fg="Black", bg="Lawn Green")
            self.position_label.config(state="normal", bg="White")
        else:
            self.enableButton.config(text="OFF", fg="Red", bg="Light Grey")
            self.setToButton.config(state="disabled", fg="Gray", bg="Light Grey")
            self.GoToButton.config(state="disabled", fg="Gray", bg="Light Grey")
            self.moveIncButton.config(state="disabled", fg="Gray", bg="Light Grey")
            self.jogButtonFWD.config(state="disabled", fg="Gray", bg="Light Grey")
            self.jogButtonREV.config(state="disabled", fg="Gray", bg="Light Grey")
            self.position_label.config(state="disabled", bg="Light Grey")

# This function starts the Jogging Thread in the FORWARD Direction
    def jogFWD(self):
        if self.enableButton["text"] != "OFF":
            direction = 1
            global t1
            self.position = float(self.position_label.cget("text"))
            velocity = float(self.vel.get())
            t1 = JoggingThread(self.position, velocity, self.position_label, direction)
            t1.start()

# This function starts the Jogging Thread in the REVERSE Direction
    def jogREV(self):
        if self.enableButton["text"] != "OFF":
            direction = -1
            global t1
            self.position = float(self.position_label.cget("text"))
            velocity = float(self.vel.get())
            t1 = JoggingThread(self.position, velocity, self.position_label, direction)
            t1.start()

# This function stops Jogging Thread
    def stopjog(self):
        t1.stop()

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


# This class starts a thread using a while loop to increment the position value and prints it to the label depending on
# direction.
class JoggingThread(threading.Thread):
    def __init__(self, position, velocity, label, direction):
        threading.Thread.__init__(self)
        self.running = True
        self.position = position
        self.velocity = velocity
        self.pause_time = float()
        self.label = label
        self.direction = direction
        if self.velocity == 0:
            self.running = False
        else:
            self.pause_time = .01/self.velocity
            print(self.pause_time)

    def run(self):
        while self.running:
            if self.direction == 1:
                self.position += 0.01
                time.sleep(self.pause_time)
                self.label.config(text=("%.2f" % round(self.position, 2)))
            elif self.direction == -1:
                self.position -= 0.01
                time.sleep(self.pause_time)
                self.label.config(text=("%.2f" % round(self.position,2)))

    def stop(self):
        self.running = False


# This class is starts Main GUI Window and calls the Circ and Trans frame functions
class Main:
    def __init__(self, master):
        self.master = master
        master.geometry("650x750")
        master.title("R0: TIMC - Piping")
        self.tool = ToolFrame(self.master)
        self.circ = AxisFrame(self.master, SetupCircFrame())
        self.trans = AxisFrame(self.master, SetupTransFrame())
        self.scan = ScanFrame(self.master, self.circ, self.trans)


root = Tk()
TIMC = Main(root)
root.mainloop()
