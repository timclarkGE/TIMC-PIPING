filename = "PARAM.txt"
try:
    f = open(filename, "r+")
    print("Success")
    f.close()
except FileNotFoundError:
    print("Error")
    f = open(filename, "w+")
    f.write("NOVA\n")
    f.close()


