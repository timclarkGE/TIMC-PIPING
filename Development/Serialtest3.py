"""
Simple program to send commands to Aerotech to see how the queue is used

Modified to open port and pull parameter values off of Ensemble
"""

from tkinter import *
import serial
import threading
import time
import queue
baud = 115200


class SetupAxis1:
    def __init__(self):
        self.axisName = "CIRC"
        self.s = serial.Serial()
        result = find_port()
        if result:
            self.s = serial.Serial(result[0], baud, timeout=0.05)
            # Get Parameters from Aerotech
            parm_num_list = ["39", "123", "129", "2"]
            parm_output_list = []
            for i in parm_num_list:
                command = ("GETPARM(" + self.axisName + ", " + i)
                self.s.write(command.encode('ascii') + b' \n')
                data = self.s.readline().decode('ascii')
                if "%" in data:
                    data = data.replace("%", " ")
                parm_output_list.append(str(data.strip()))

            print(parm_output_list)
            self.curMax = parm_output_list[0]
            self.speedMax = parm_output_list[1]
            self.axisUnits = parm_output_list[2]
            self.s.close()
        else:
            self.curMax = "N/A"
            self.speedMax = "N/A"
            self.axisUnits = "N/A"
            print("Serial Port Can't Be Opened")


# This class starts a thread that opens communication and puts queued commands to the Ensemble
class SerialThread(threading.Thread):
    def __init__(self, q_read, q_write):
        threading.Thread.__init__(self)
        self.q_read = q_read
        self.q_write = q_write
        self.s = serial.Serial()
        self._is_running = 1
        self.port_open = 0

    def run(self):
        result = find_port()
        if result:
            self.s = serial.Serial(result[0], baud, timeout=0.05)

            # Send a command to check if communication has been established
            self.s.write("ACKNOWLEDGEALL".encode('ascii') + b' \n')
            data = self.s.readline().decode('ascii')
            if '%' in data:
                self.port_open = 1
        else:
            self.port_open = 0
            self._is_running = 0

        # Serial Thread Main Loop - Check Queue for Commands to Send to Aerotech Drive
        while self._is_running:
            time.sleep(.0001)
            # Check if control queue has commands in the queue to send to the Aerotech drive
            if self.q_write.qsize():
                command = self.q_write.get().encode('ascii') + b' \n'
                self.s.write(command)
                data = self.s.readline().decode('ascii')
                self.q_read.put(data)

    # Stop the thread from running
    def stop(self):
        self._is_running = 0
        try:
            self.s.close()
            print("Serial Port Closed")
        except:
            print("No Serial Port to Close")


class AxisFrame:
    def __init__(self, master, parameters):
        self.master = master
        self.curMax = parameters.curMax
        self.axisUnits = parameters.axisUnits

        frame = Frame(master)
        frame.pack()

        self.cur_label = Label(frame, text=str(self.curMax))
        self.cur_label.pack(pady=5)
        self.units_label = Label(frame, text=self.axisUnits)
        self.units_label.pack(pady=5)

        self.com_entry = Entry(frame, width=30, bg="White")
        self.com_entry.pack(pady=5)

        button = Button(frame, text="COMMAND", command=lambda: self.send_command(), width=8)
        button.pack(pady=5)

        self.ret_label = Label(frame, height=1, width=20, bg="White")
        self.ret_label.pack(pady=5)

    def send_command(self):
        command = str(self.com_entry.get())

        # Either the acmd function can be called or q_write can be overwritten directly
        data = str(TIMC.acmd(command))
        self.ret_label.config(text=str(data.strip()))

        # TIMC.q_write.put(command)
        # data = TIMC.q_read.get()


class Main:
    def __init__(self, master):
        self.master = master
        master.geometry("200x200")
        master.title("R0: TIMC - Piping")

        self.baud = 115200
        self.online = 0  # If communication is successful with the controller this value will be set to 1
        self.q_read = queue.Queue()
        self.q_write = queue.Queue()
        self.write_queue = queue.Queue()
        self.read_queue = queue.Queue()

        # Open Comms and Pull parameters
        self.axis1 = AxisFrame(self.master, SetupAxis1())

        # Start serial thread
        self.process_serial = SerialThread(self.q_read, self.q_write)
        self.process_serial.start()

    def acmd(self, text):
        self.write_queue = self.q_write
        self.read_queue = self.q_read

        self.write_queue.put(text)
        data = self.read_queue.get()

        # Aerotech drive sends back special characters in response to the command given
        if "!" in data:
            print("(!) Bad Execution CMD: " + text)
            return 0
        elif "#" in data:
            print("(#) ACK but cannot execute CMD:", text)
            return 0
        elif "$" in data:
            print("($) CMD timeout CMD:", text)
            return 0
        elif data == "":
            print("No data returned, check serial connection CMD:", text)
            return 0
        elif "%" in data:
            data = data.replace("%", "")
            return data
        else:
            print("Error")


def on_closing():
    print("Closing...")
    TIMC.process_serial.stop()  # Close Serial Port Communication
    root.destroy()


def find_port():
    ports = ['COM%s' % (i + 1) for i in range(100)]
    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
            print(result)
        except (OSError, serial.SerialException):
            pass
    if len(result) == 1:
        return result


root = Tk()
TIMC = Main(root)
root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()

