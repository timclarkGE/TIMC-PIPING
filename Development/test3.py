"""
This code will start a GUI with a title frame with a button labeled "NOVA" and two frames for CIRC and TRANS
When the button is clicked it will change the button from NOVA to LPS-1000 but not modify either of the frames
"""

from tkinter import *


# This class sets Frame parameters for the Circ Axis
class SetupCircFrame:
    def __init__(self):
        self.axisName = "CIRC"


# This class sets Frame parameters for the Trans Axis
class SetupTransFrame:
    def __init__(self):
        self.axisName = "TRANS"


class ToolFrame:
    def __init__(self, master):
        self.master = master
        top_frame = Frame(master, relief=SUNKEN, border=2)
        top_frame.pack(fill=X, padx=10, pady=10)
        self.toolButton = Button(top_frame, text="NOVA", fg="Black", bg="Sky Blue", font=("Helvetica", 14),
                                 command=lambda: self.toggle_tool())
        self.toolButton.pack()
        self.circ = AxisFrame(master, SetupCircFrame())
        self.trans = AxisFrame(master, SetupTransFrame())

    def toggle_tool(self):
        if self.toolButton["text"] == "NOVA":
            self.toolButton.config(text="LPS-1000", fg="Black", bg="Yellow")
        else:
            self.toolButton.config(text="NOVA", fg="Black", bg="Sky Blue")


# This class pulls parameters from the specific axis and puts them in the GUI
class AxisFrame:
    def __init__(self, master, parameters):
        self.axisName = parameters.axisName
        frame = Frame(master, relief=SUNKEN, border=2)
        frame.pack(fill=X, padx=10, pady=10)

        self.position = 0
        # Create Widgets
        self.label_0 = Label(frame, text=parameters.axisName, font=("Helvetica", 14))
        self.label_1 = Label(frame, text="Position", font=("Helvetica", 10))
        self.enableButton = Button(frame, text="OFF", fg="Red", bg="Light Grey", height=3, width=8,
                                   command=lambda: self.toggle_axis())
        self.jogButtonFWD = Button(frame, text="FWD", fg="Gray", bg="Light Grey", height=1, width=10, state="disabled")
        self.jogButtonREV = Button(frame, text="REV", fg="Gray", bg="Light Grey", height=1, width=10, state="disabled")
        self.position_label = Label(frame, bg="White", width=10, relief=SUNKEN)
        print(str(parameters.axisName))
        self.jogButtonFWD.bind('<ButtonPress-1>', lambda event: self.jogFWD())
        self.jogButtonFWD.bind('<ButtonRelease-1>', lambda event: self.stopjog())
        self.jogButtonREV.bind('<ButtonPress-1>', lambda event: self.jogREV())
        self.jogButtonREV.bind('<ButtonRelease-1>', lambda event: self.stopjog())

        # Grid Widgets
        self.label_0.grid(column=0, row=0)
        self.label_1.grid(column=3, row=0, sticky=S)
        self.enableButton.grid(column=0, row=1, padx=10, pady=10)
        self.jogButtonFWD.grid(column=1, row=1, padx=10, pady=10, sticky=N)
        self.jogButtonREV.grid(column=2, row=1, padx=10, pady=10, sticky=N)
        self.position_label.grid(column=3, row=1, padx=10, pady=10, sticky=N)

    # This function toggles the button between OFF and ON
    def toggle_axis(self):
        if self.enableButton["text"] == "OFF":
            self.enableButton.config(text="ON", fg="Black", bg="Lawn Green")
            self.jogButtonFWD.config(state="normal", fg="Black", bg="Lawn Green")
            self.jogButtonREV.config(state="normal", fg="Black", bg="Lawn Green")
        else:
            self.enableButton.config(text="OFF", fg="Red", bg="Light Grey")
            self.jogButtonFWD.config(state="disabled", fg="Gray", bg="Light Grey")
            self.jogButtonREV.config(state="disabled", fg="Gray", bg="Light Grey")

    # This function jogs the axis FWD
    def jogFWD(self):
        if self.jogButtonFWD["state"] == "normal":
            self.position += 1
            self.position_label.config(text=str(self.position))

    # This function stops jogging the axis FWD
    def stopjog(self):
        self.position_label.config(text=" ")

    # This function jogs the axis REV
    def jogREV(self):
        if self.jogButtonREV["state"] == "normal":
            self.position -= 1
            self.position_label.config(text=str(self.position))


# This class is starts Main GUI Window and calls the Circ and Trans frame functions
class Main:
    def __init__(self, master):
        self.master = master
        master.geometry("650x650")
        master.title("R0: TIMC - Piping")
        self.tool = ToolFrame(self.master)


root = Tk()
TIMC = Main(root)
root.mainloop()
