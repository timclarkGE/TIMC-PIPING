"""
Simple program to send commands to Aerotech to see how the queue is used
"""
from tkinter import *
import serial
import threading
import time
import queue


class Comm:
    def __init__(self, baud):
        self.port_open = 0
        self.baud = baud
        self.s = serial.Serial()
        # Open the serial port
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
            self.s = serial.Serial(result[0], self.baud, timeout=0.05)

            # Send a command to check if communication has been established
            self.s.write("ACKNOWLEDGEALL".encode('ascii') + b' \n')
            data = self.s.readline().decode('ascii')
            if '%' in data:
                self.port_open = 1
                self.s.write("WAIT MODE NOWAIT".encode('ascii') + b' \n')
                data = self.s.readline().decode('ascii')
                print(data)
            self.s.close()
        elif len(result) > 1:
            self.port_open = 0


# This class starts a thread that opens communication and puts queued commands to the Ensemble
class SerialThread(threading.Thread):
    def __init__(self, baud, q_read, q_write):
        threading.Thread.__init__(self)
        self.q_read = q_read
        self.q_write = q_write
        self.s = serial.Serial()
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
                print(result)
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
    def __init__(self, master):
        self.master = master

        frame = Frame(master)
        frame.pack()

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
        self.comm = Comm(self.baud)

        # Start serial thread
        self.process_serial = SerialThread(self.baud, self.q_read, self.q_write)
        self.process_serial.start()

        self.axis1 = AxisFrame(self.master)

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


root = Tk()
TIMC = Main(root)
root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()

