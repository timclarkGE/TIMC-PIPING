from tkinter import *

root = Tk()
ws = root.winfo_screenwidth()
hs = root.winfo_screenheight()
w = 500
h = 300
x = ws * .5 - (w / 2)
y = (hs / 2) - (h / 2)
root.geometry("%dx%d+%d+%d" % (w, h, x, y))

menubar = Menu(root)
root.config(menu=menubar)
fileMenu = Menu(menubar, tearoff=0)

menubar.add_cascade(label="File", menu=fileMenu)
menubar.add_command(label="Open", command=lambda: open_window())
fileMenu.add_command(label="Parameters", command=lambda: open_window())
fileMenu.add_separator()
fileMenu.add_command(label="Exit")

frame = Frame(root)
frame.pack()
bottom_frame = Frame(root)
bottom_frame.pack()
tool_label = Label(frame, text="NOVA PARAMETERS", width=30, font="Helvetica, 18")
axis1label = Label(frame, text="TRANSLATOR", width=12, font="Helvetica, 12 bold")
axis2label = Label(frame, text="CIRC", width=12, font="Helvetica, 12 bold")
tool_label.grid(column=0, row=0, columnspan=3, pady=2)
axis1label.grid(column=1, row=1, padx=5, pady=2)
axis2label.grid(column=2, row=1, padx=5, pady=2)

param_labels = ["Position Error Threshold", "Max Current Clamp", "Max Jog Speed", "Units", "Counts per Unit"]
axis_labels = []
axis1entry = []
axis2entry = []
param = "0.0"

for i in range(0, 5):
    axis_labels.append(Label(frame, text=param_labels[i], font="Helvetica, 10"))
    axis1entry.append(Entry(frame, width=10, textvariable=param, font='Helvetica, 10', justify='center'))
    axis2entry.append(Entry(frame, width=10, textvariable=param, font='Helvetica, 10', justify='center'))
    axis_labels[i].grid(column=0, row=i+2, pady=2, sticky=E)
    axis1entry[i].grid(column=1, row=i+2, pady=2)
    axis2entry[i].grid(column=2, row=i+2, pady=2)

# Motor Direction Check Boxes
axis1_dir = IntVar()
axis2_dir = IntVar()
direction_label = Label(frame, text="Reverse Positive Direction", font="Helvetica, 10")
direction_label.grid(column=0, row=12, pady=2, sticky=E)
axis1_dir_box = Checkbutton(frame, variable=axis1_dir)
axis1_dir_box.grid(column=1, row=12)
axis2_dir_box = Checkbutton(frame, variable=axis2_dir)
axis2_dir_box.grid(column=2, row=12)
axis1_dir.set(1)

save_btn = Button(bottom_frame, text="SAVE", width=10, bg="Yellow", font="Helvetica, 12 bold", command=lambda: save_parameters())
reset_btn = Button(bottom_frame, text="RESET", width=10, bg="Green", font="Helvetica, 12 bold")

save_btn.grid(column=0, row=0, padx=20, pady=15)
reset_btn.grid(column=1, row=0, padx=20, pady=15)


def save_parameters():
    print(axis1_dir.get(), " ", axis2_dir.get())


def open_window():
    print("OPEN")

root.mainloop()
