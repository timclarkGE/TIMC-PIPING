"""
This program uses settings stored in a text file named "TIMC-P-PARAM.txt"
The first line states which tool was used last (selected by a button)
so on startup, that tool is displayed on the button
"""

from tkinter import *
tool = str()
filename = "TIMC-P-PARAM.txt"
try:
    f = open(filename, "r+")
    tool = f.readlines()
    f.close()
    print(tool)
except FileNotFoundError:
    print("Cannot find file: " + filename)
    f = open(filename, "w+")
    f.write("NOVA\n")
    f.close()


root = Tk()
root.geometry("200x200")
root.resizable(width=False, height=False)

frame = Frame(root)
frame.pack()

toolButton = Button(frame, text="LPS-1000", fg="Black", bg="Goldenrod", width=10, command=lambda: toggle_tool())
if tool[0] == "LPS-1000\n":
    toolButton.config(text="LPS-1000", fg="Black", bg="Goldenrod")
elif tool[0] == "NOVA\n":
    toolButton.config(text="NOVA", fg="Black", bg="Sky Blue")
toolButton.pack()


def toggle_tool():
    if toolButton["text"] == "NOVA":
        toolButton.config(text="LPS-1000", fg="Black", bg="Goldenrod")
        tool[0] = "LPS-1000\n"
    else:
        toolButton.config(text="NOVA", fg="Black", bg="Sky Blue")
        tool[0] = "NOVA\n"


def on_closing():
    new_f = open(filename, "w+")
    new_f.writelines(tool)
    new_f.close()
    root.destroy()


root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()
