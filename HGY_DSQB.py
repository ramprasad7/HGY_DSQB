import serial.tools.list_ports as port_list
import serial, time, sys, os, subprocess
import logging

#Logging setup
#logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
# Function to generate a new log file name if one already exists
def get_new_log_file(base_name, extension=".log"):
    if not os.path.exists(f"{base_name}{extension}"):
        return base_name + extension 
    
    if os.path.exists(base_name + extension):
        i = 1
    while os.path.exists(base_name + '_%.2d.log' % (i)):
        i += 1
    os.rename(base_name + extension, base_name + '_%.2d.log' % (i))

    file_name = base_name + extension

    return file_name

md_logger_file = get_new_log_file(base_name="main_domain")
md_logger = logging.getLogger("main domain")
handler = logging.FileHandler(filename=md_logger_file, mode="w")
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
md_logger.addHandler(handler)
md_logger.setLevel(level=logging.DEBUG)

aurix_logger_file = get_new_log_file(base_name="aurix")
aurix_logger = logging.getLogger("aurix domain")
handler = logging.FileHandler(filename=aurix_logger_file,mode="w")
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
aurix_logger.addHandler(handler)
aurix_logger.setLevel(level=logging.DEBUG)

'''
Test Procedure:
    Enable wifi in lagvm:
    #microcom /dev/hvc5
    console$ su
    console# svc wifi enable

    systemctl --failed --no-pager
    cat /proc/interrupts | grep susp

    journalctl --output=short-monotonic -f | grep autoghgvm &
    journalctl --output=short-monotonic -f | grep autoghgvm_lv & 
    journalctl --output=short-monotonic -f | grep "Failed to start" &
    journalctl --output=short-monotonic -f | grep "Notifier" &
    powercyclemgr_test SET 100

    serch string: com_ethqos_exit disconnect phy
'''


class DSQB:

    BAUD_RATE: int = 115200

    def __init__(self) -> None:
        print("Starting DS-QB Validation!!")

    def serial_connection(self, com_port, baudrate1= BAUD_RATE):
        if "win" in sys.platform:
            port = com_port
        else:
            port = '/dev/' + com_port
        port = serial.Serial(port, baudrate=self.BAUD_RATE, bytesize=8, timeout=2, stopbits=serial.STOPBITS_ONE)
        port.close()
        port.open()
        try:
            if port.isOpen():
                return port
            else:
                self.serial_connection(com_port,self.BAUD_RATE)
        except Exception as e:
          print(f"Error open serial port: {port}" + str(e))
          exit()
        return port

    def services_checker(self, port) -> bool:
        # checking if any service failed
        #time.sleep(10)
        print("executing : systemctl --failed --no-pager")
        port.write("systemctl --failed --no-pager\r\n".encode())
        rawdata = port.readlines()
        #print(rawdata)
        output = [line.decode('utf-8').strip() for line in rawdata]
        #print(output)
        flag: int = 0
        print("results : ")
        for line in output:
            if '0 loaded' in line:
                #print(line)
                flag = 1
                #port.close() 
                #return True
        for line in output:
            print(line)
            if flag == 1:
                md_logger.debug(line)
            else:
                md_logger.error(line)
        
        if flag == 1:
            return True  
        #if '0 loaded' in output:
        #    print("Present")
        #else:
        #    print("Not Present")
        port.close()
        return False
    
    def wifi_enabling(self, port):
        print("Enabling wifi in LAGVM shell")
        port.write("microcom /dev/hvc5\r\nsu\r\n".encode())
        port.write(b"\r\n")
        #port.write(b"su\r\n")
        port.write(b"cmd wifi set-wifi-enabled enabled\r\n")
        #print("results : ")
        rawdata = port.read(size=100)
        output = rawdata.decode('utf-8', errors='ignore')
        md_logger.debug(output)
        #for string in res :
        #    print(string.decode())
        #0x18 : ctrl + x  to return back to PVM shell
        port.write(b'\x18')
        print("Wifi is enabled!") 

    def send_logging_commands(self, port):
        print("executing : Logging commands")
        port.write("journalctl --output=short-monotonic -f | grep autoghgvm &\r\n".encode())
        port.write("journalctl --output=short-monotonic -f | grep autoghgvm_lv &\r\n".encode())
        port.write('journalctl --output=short-monotonic -f | grep "Failed to start" &\r\n'.encode())
        port.write('journalctl --output=short-monotonic -f | grep "Notifier" &\r\n'.encode())
        rawdata = port.read(size=100)
        output = rawdata.decode('utf-8', errors='ignore')
        md_logger.debug(output)
        #print("results : ")
        #for string in res :
        #    print(string.decode())
    
    def adb_checker(self) -> bool:
        time.sleep(5)
        os.system(r"cmd /C adb disconnect")
        os.system(r"cmd /C adb devices")
        os.system(r"cmd /C adb root")
        result = subprocess.check_output("adb connect 192.168.1.1",shell=True,text=True)
        time.sleep(2)
        if "connected to 192.168.1.1:5555" in result:
            #print("Connected to adb IP: 192.168.1.1 Successfully")
            md_logger.debug("Connected to adb IP: 192.168.1.1 Successfully")
            op = subprocess.check_output("adb -s 192.168.1.1 root",shell=True,text=True)
            time.sleep(2)
            if "root" in op:
                #print(f"{'Restarted adb as root':=^50}")
                md_logger.debug((f"{'Restarted adb as root':=^50}")) 
                return True
        #print(result)
        #print("adb connection failed")
        md_logger.error(result)
        md_logger.error("adb connection failed")
        return False
    
    def deep_sleep(self, md_port) -> bool:
        # connect the serial port
        port1 = self.serial_connection(md_port, self.BAUD_RATE)
        # if connected perform the serial flash
        if port1.isOpen():
            try:
                print("Connected to Serial Port: ", md_port)
                port1.flushInput()  # flush input buffer, discarding all its contents
                port1.flushOutput()  # flush output buffer, aborting current output
                #port1.write("\r".encode())
                port1.write("root\r\n".encode())
                #output = port1.readlines()
                #for string in output :
                #    print(string.decode())
                
                if not self.services_checker(port1):
                    #print("All Services are Not Up and Running...")
                    md_logger.error("All Services are Not Up and Running\nAborting DSQB!!")
                    port1.close()
                    return False
                print("All Services are Up and Running.\nProceeding with DS-QB testing.")

                self.wifi_enabling(port1)
                
                self.send_logging_commands(port1)

                port1.flushInput()
                print("Executing DS-QB with PCM: powercyclemgr_test SET 100")
                port1.write("powercyclemgr_test SET 100\r\n".encode())
                #rawdata = port1.readlines()
                #print(rawdata)
                #output = [line.decode('utf-8').strip() for line in rawdata]
                count = 0
                while count <= 15:
                    count += 1
                    rawdata = port1.readlines()
                    output = [line.decode('utf-8').strip() for line in rawdata]
                    for line in output:
                        md_logger.debug(line)
                        if "com_ethqos_exit disconnect phy" in line:
                            port1.close()
                            return True
                    time.sleep(5)
                port1.close()
                return False
            except Exception as e:
                print(e)
                port1.close()
            finally:
                port1.close()

    def quick_boot(self, aurix_port) -> None:
        # enter e & 1 command on aurix terminal for quickboot
        time.sleep(5)
        port2 = self.serial_connection(aurix_port, self.BAUD_RATE)
        if port2.isOpen():
            try:
                print("Serial port connected: ", aurix_port)
                port2.flushInput()  # flush input buffer, discarding all its contents
                port2.flushOutput()  # flush output buffer, aborting current output
                port2.write("\r".encode())
                #print(port2.readlines())
                #execute quick boot command
                print("Executing : e & 1")
                # time.sleep(10)
                port2.write("e".encode())
                #print("string value", aurix_string)
                port2.write("1\r".encode())
                #print("cat cmd results : ", port2.read(200).decode())
                aurix_string = port2.read(size=500)
                output = aurix_string.decode('utf-8', errors='ignore')
                aurix_logger.debug(output)                
                time.sleep(15)
                if not self.adb_checker():
                    #print("Device bootup failed after quick boot!")
                    aurix_logger.critical("Device bootup failed after quick boot!")
                    port2.close()
                    return False
                return True
            except Exception as e:
                print(e)
                port2.close()
            finally:
                port2.close()

    def DSQB(self, md_port, aurix_port) -> str:
        if not self.deep_sleep(md_port):
            print("Deep Sleep Failed!")
            return "Fail"
        if not self.quick_boot(aurix_port):
            print("Quick Boot Failed!")
            return "Fail"
        port1 = self.serial_connection(md_port, self.BAUD_RATE)
        # Checking after DS-QB if all services are up and running, if any services failed this TC will fail
        if port1.isOpen():
            try:
                print("Connected to Serial Port: ", md_port)
                port1.flushInput()  # flush input buffer, discarding all its contents
                port1.flushOutput()  # flush output buffer, aborting current output
                time.sleep(10)
                if not self.services_checker(port1):
                    print("DS-QB Test Case Failed, All services are not up!!!")
                    md_logger.critical("DS-QB Test Case Failed, All services are not up!!!")
                    port1.close()
                    return "Fail"
                return "Pass"                   
            except Exception as e:
                port1.close()
                print(e)
            finally:
                port1.close()
        else:
            port1.close()
            print(f"Failed to open {port1}, aborting testing...")
            return "Fail"

#Getting Serial Ports details connected to setup
def get_ports() -> list:
    ports = list(port_list.comports())
    ports_list: list = []
    for port in ports:
        #print(port)
        ports_list.append(port)

    ports_list = sorted(ports_list)
    print("Available Ports on the device: ")
    for port in ports_list:
        print(port)
    
    main_domain = input("Please pass main domain port(port number only): ")
    sail_domain = input("Please pass sail domain port(port number only): ")
    aurix_domain = input("Please pass aurix domain port(port number only): ")

    main_domain = 'COM' + main_domain
    sail_domain = 'COM' + sail_domain
    aurix_domain = 'COM' + aurix_domain
    ports: list = []
    ports.append(main_domain)
    ports.append(sail_domain)
    ports.append(aurix_domain)
    print(f'main domain: {main_domain}\nsail domain: {sail_domain}\naurix domain: {aurix_domain}')
    md_logger.debug(f"main domain: {main_domain}")
    md_logger.debug(f"sail domain: {sail_domain}")
    md_logger.debug(f"aurix domain: {aurix_domain}")
    
    return ports

#driver code
def main() -> None:
    
    ports_list = get_ports()
    
    main_domain = ports_list[0]
    sail_domain = ports_list[1]
    aurix = ports_list[2]

    #number of iterations DS-QB to be performed
    iterations: int = int(input("Please enter number of times DS-QB to be tested: "))
    dsqb: DSQB = DSQB()
    result: list[str] = []
    for i in range(0,iterations):
        print(f'Running iteration number: {i+1}')
        result.append(dsqb.DSQB(main_domain,aurix))
    print(result)


if __name__ == "__main__":
    main()
