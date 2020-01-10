"""
This code will open up a GUI with 2 overlapping frames
A button will raise the other frame
"""
from tkinter import *


class AxisFrame:
    def __init__(self, master):
        self.master = master

        # Make Frame 1 with Button to Raise Frame 2
        self.frame1 = Frame(master, relief=SUNKEN, border=2)
        self.frame1.grid(row=0, column=0, sticky="nsew")
        self.toolButton = Button(self.frame1, text="NOVA", width=10, fg="Black", bg="Sky Blue",
                                 font=("Helvetica", 14), command=lambda: self.show_lps())
        self.tool = Label(self.frame1, text="FRAME 1", font=("Helvetica", 14))

        self.toolButton.pack(side=LEFT, padx=10, pady=10)
        self.tool.pack(side=RIGHT, padx=10, pady=10)

        # Make Frame 2 with Button to Raise Frame 1
        self.frame2 = Frame(master, relief=SUNKEN, border=2)
        self.frame2.grid(row=0, column=0, sticky="nsew")
        self.toolButton = Button(self.frame2, text="LPS-1000", width=10, fg="Black", bg="Yellow",
                                 font=("Helvetica", 14), command=lambda: self.show_nova())
        self.tool = Label(self.frame2, text="FRAME 2", font=("Helvetica", 14))

        self.toolButton.pack(side=LEFT, padx=10, pady=10)
        self.tool.pack(side=RIGHT, padx=10, pady=10)

    def show_nova(self):
        self.frame1.lift()

    def show_lps(self):
        self.frame2.lift()


class Main:
    def __init__(self, master):
        self.master = master
        master.geometry("650x650")
        master.title("R0: TIMC - Piping")
        self.circ = AxisFrame(self.master)


root = Tk()
TIMC = Main(root)
root.mainloop()
