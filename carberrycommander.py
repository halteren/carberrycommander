
import socket
import time
import os 
import subprocess
from gpsdclient import GPSDClient
import haversine as hs
from haversine import Unit

# How long before carberry goes to sleep
CAN_IDLE_DELAY = 600
DEFAULT_IGNITION_TIMER_1 = 300

# maximum time (in seconds) to keep running, even with associated stations
MAX_RUN_TIME = 3600
DEFAULT_HOME = (52.3566777,4.9492952) # somewhere in Amsterdam
HOME_CIRCLE_DIAMETER = 20

"""
    The CanSubsystem takes care of all CAN related commands.
    Use this when the carberry HAT is connected to either channel1 or channel2
    Default is channel1.
    See https://www.carberry.it/wiki/carberry/hw_spec/main_connector and https://www.carberry.it/wiki/carberry/cmds/subsys/canbus/user 
"""
class CanSubsystem:

    def __init__(self,commander, channel = "CH1"):
        self._commander = commander
        self._channel = channel

        # create /tmp files
        tmp_files_command = ['/usr/bin/touch', '/tmp/voltage', '/tmp/fuel_level', '/tmp/rpm', '/tmp/speed', '/tmp/air_intake_temp', '/tmp/coolant_temp']
        try:
            subprocess.Popen(tmp_files_command,stdout=subprocess.PIPE).communicate()
        except Exception as ex:
            print("Failed to create /tmp files. Error: %s" % ex)


    def _sendCommand(self, cmd):
        self._commander._sendCommand(cmd)    

    def open_channel(self):
        reply = self._sendCommand("CAN USER OPEN %s 500K" % self._channel)
        return(reply == "OK")
    
    def close_channel(self):
        reply = self._sendCommand("CAN USER CLOSE %s" % self._channel)
        return(reply == "OK")

    def set_can_wakeup_activity(self):
        #print("Carberry to wakeup on activity.")
        reply = self._sendCommand("CAN WAKEUP ACTIVITY")
        return(reply == "OK")

    def set_can_idle_delay(self, delay):
        reply = self._sendCommand("CAN IDLE_DELAY %s" % delay)
        return(reply == "OK")
    
    def align_channel(self):
        reply = self._sendCommand("CAN USER ALIGN RIGHT")
        return(reply == "OK")
        
    def set_rx_id(self):
        reply = self._sendCommand("OBD SET RXID %s 07E8" % self._channel)
        return(reply == "OK") 
    
    def set_can_idle_delay(self, delay):
        reply = self._sendCommand("CAN IDLE_DELAY %s" % delay)
        return(reply == "OK")
    
    def align_channel(self):
        reply = self._sendCommand("CAN USER ALIGN RIGHT")
        return(reply == "OK")
        
    def set_rx_id(self):
        reply = self._sendCommand("OBD SET RXID %s 07E8" % self._channel)
        return(reply == "OK") 

    def air_intake_temp(self):
        reply = self._sendCommand("OBD QUERY %s 010F" % self._channel)
        if (reply.startswith("41 0F")):
            hex_strings = reply.split()
            result = int(hex_strings[2],16) - 40
            print("Air intake temperature = %0.1f C" % result)
            self._write_to_file("/tmp/air_intake_temp", "%.1f" % result)
            return(True)
        else:
            return(False)
        
    def coolant_temp(self):
        reply = self._sendCommand("OBD QUERY %s 0105" % self._channel)
        if (reply.startswith("41 05")):
            hex_strings = reply.split()
            result = int(hex_strings[2],16) - 40
            print("Coolant temperature = %.0f C" % result)
            self._write_to_file("/tmp/coolant_temp", "%.0f" % result)
            return(True)
        else:
            return(False)

    def vehicle_speed(self):
        reply = self._sendCommand("OBD QUERY %s 010D" % self._channel)
        if (reply.startswith("41 0D")):
            hex_strings = reply.split()
            result = int(hex_strings[2],16) 
            print("Speed = %0.2f km/h" % result)
            self._write_to_file("/tmp/speed", "%.2f" % result)
            return(True)
        else:
            return(False)

    def rpm(self):
        reply = self._sendCommand("OBD QUERY %s 010C" % self._channel)
        if (reply.startswith("41 0C")):
            hex_strings = reply.split()
            a = int(hex_strings[2],16) 
            b = int(hex_strings[3],16)
            result = (a*256+b)/4
            print("RPM = %.0f" % result)
            self._write_to_file("/tmp/rpm", "%.0f" % result)    
            return(True)
        else:
            return(False)

    def voltage(self):  
        reply = self._sendCommand("OBD QUERY %s 0142" % self._channel)
        if reply.startswith("41 42"):
            hex_strings = reply.split()
            a = int(hex_strings[2],16) 
            b = int(hex_strings[3],16)
            result = (a*256+b)/1000
            print("Voltage: %.2f" % result)
            self._write_to_file("/tmp/voltage", "%.2f" % result)    
            return(True)
        else:
            return(False)

    def fuel_level(self):  
        reply = self._sendCommand("OBD QUERY %s 012F" % self._channel)
        if reply.startswith("41 2F"):
            hex_strings = reply.split()
            a = int(hex_strings[2],16) 
            result = (a*100)/256
            print("Fuel level: %.1f percent" % result)  
            self._write_to_file("/tmp/fuel_level", "%.1f" % result )    
            return(True)
        else:
            return(False)
    
    """ Main loop that queries using OBD commands"""
    def obd_query_loop(self):  
        sleeptime = 60
        max_cycles = int(CAN_IDLE_DELAY/sleeptime)

        self.open_channel()
        self.align_channel()
        self.set_rx_id()
        
        while self.connected() and max_cycles > 0:
            if (self.vehicle_speed() and self.air_intake_temp() and self.rpm() and self.voltage() and self.fuel_level() and self.coolant_temp()):
                time.sleep(1)
                max_cycles = int(CAN_IDLE_DELAY/sleeptime)
            else:
                self.close_channel()
                max_cycles -= 1 
                print("Sleeping for %s seconds" % sleeptime)
                time.sleep(sleeptime)
                self.open_channel()
                self.align_channel()
                self.set_rx_id()

        print("Exiting after %d attempts" % int(CAN_IDLE_DELAY/sleeptime))
        self.set_can_idle_delay(10)
"""
    The IgnitionSubsystem manages ignition events and safe wake up/shutdown 
    based on the ignition status.
    See https://www.carberry.it/wiki/carberry/cmds/subsys/ignition/ignition
"""
class IgnitionSubsystem:

    def __init__(self,commander, rpi):
        self.commander = commander
        self.rpi = rpi

    def _sendCommand(self, cmd):
        self.commander._sendCommand(cmd)  

    def set_can_wakeup_ignition(self):
        #print("Carberry to wakeup on ignition.")
        reply = self._sendCommand("CAN WAKEUP IGNITION")
        return(reply == "OK")
    
    def keep_alive(self):
        reply = self._sendCommand("IGNITION KEEPALIVE")
        return(reply == "OK")
    
    def subscribe_ignition_events(self):
        reply = self._sendCommand("IGNITION EVENTS NOTIFY")
        return(reply == "OK")
    
    def set_ignition_timers(self, timer2):
        timer1 = os.getenv('TIMER1')
        if (timer1==None or int(timer1)<0 or int(timer1)>300):
            timer1 = DEFAULT_IGNITION_TIMER_1
        else:
            timer1 = int(timer1)
        reply = self._sendCommand("IGNITION TIMERS %d %d" % (timer1, timer2))
        return(reply == "OK")
    
    def process_events(self):
        while True:
            evnt = self.commander._processCommand()
            if (evnt.startswith("EVNT IGNITION OFF")):
                self.rpi.ignition_off()
                continue
            if (evnt.startswith("EVNT IGNITION ON")):
                self.rpi.ignition_on()
                continue
            if (evnt.startswith("EVNT GOTOSLEEP")):
                if (self.rpi.need_to_stay_alive()):
                  self.keep_alive()
                  time.sleep(5)  
                else:  
                  self.rpi.shutdown()
                continue

            print("-> Unknown event" )

"""
    The LocationSubsystem manages the gpsd (if available)
    It is used to determine if we're already at a known location (e.g. at home) where we don't need to rely on the car for Wifi
"""
class LocationSubsystem:

    def __init__(self):
        self._gpsd = GPSDClient(host="127.0.0.1") # connection will be established on first read
        self._enabled = True
        self._init_home_coord()

    def _init_home_coord(self):
        coord = os.getenv('HOME_COORD')
        if(coord == None):
            self._home_coord = DEFAULT_HOME
        else:
            lat = float(coord.split(",")[0])
            lng = float(coord.split(",")[1])
            self._home_coord = (lat,lng)

    def _current_location(self):
        loc = (0,0)
        if (self._enabled):
            try:
                result = next(self._gpsd.dict_stream(convert_datetime=True, filter=["TPV"]))
                loc = (result.get("lat", "n/a"), result.get("lon", "n/a"))
                dist = hs.haversine(loc,self._home_coord,unit=Unit.METERS)

                print("Currently %.2f m away from home, at (%s,%s)" % (dist, result.get("lat", "n/a"), result.get("lon", "n/a")))
            except ConnectionRefusedError as conn_error:
                print("Can't connect to gpsd on port 2947. Disabling LocationSubsystem")
                self._enabled = False
        
        # in case of an exception or subsystem not enabled, return (0,0) tuple
        return loc

    def distance_from_home(self):
        return hs.haversine(self._current_location(),self._home_coord,unit=Unit.METERS)
    

    
""" 
    The RpiSubsystem checks if a shutdown is needed.
    The implemented strategy currently is to postpone shutdown (upto a maximum of MAX_RUN_TIME seconds)
    as long as there is an active device connected to the Wifi (hostapd).
"""
class RpiSubsystem:

    _hostapd_control_path = '/var/run/hostapd'
    _hostapd_cli_path = '/usr/sbin/hostapd_cli'
    _hostapd_interface = None
    _ignition_off_time = None
    _shutdown_in_progress = False

    def __init__(self):
        # talk to GPSD if available
        self.location_subsystem = LocationSubsystem()

        # initialize time for ignition off - will be updated when the even really happens
        self._ignition_off_time = time.time()

        # get number of interfaces served by hostapd (usually only 'wlan0')
        try:
            self._hostapd_interfaces = os.listdir(self._hostapd_control_path)
        except FileNotFoundError as not_found_error:
            self._hostapd_interfaces = []
            print("Check hostapd config. Error: %s" % not_found_error)

        # set list of Wifi stations that need to be ignored
        self._init_ignore_stations()

    def _init_ignore_stations(self):
        station_list = os.getenv('IGNORE_STATIONS')
        if(station_list == None):
            self._ignore_stations = []
        else:
            self._ignore_stations = station_list.split(",")


    """ Return a list of MAC address of Wifi clients associated with hostapd """
    def _list_associated_stations(self):
        stations = []
        for hostapd_iface in self._hostapd_interfaces:
            hostapd_cli_cmd = [self._hostapd_cli_path,'-i',hostapd_iface,'list_sta']
            list_sta_output = subprocess.Popen(hostapd_cli_cmd,stdout=subprocess.PIPE).communicate()[0].decode()
            stations += list_sta_output.strip().split('\n')
        return(stations)
    
    def ignition_off(self):
        self._ignition_off_time = time.time()

    def ignition_on(self):
        self._ignition_off_time = None    

    def _within_max_runtime(self):
       if (self._ignition_off_time):
           current_runtime = int(time.time() - self._ignition_off_time)
           print("Running for %d seconds." % current_runtime)
           return (current_runtime < MAX_RUN_TIME)
       else:
           print("!! _ignition_off_time not set")
           return False        
       
    def _not_at_home(self):
        return (self.location_subsystem.distance_from_home() > HOME_CIRCLE_DIAMETER)

        
    """ Check if we have any client stations associated for which we'd like to stay alive"""    
    def need_to_stay_alive(self):
        stations = self._list_associated_stations()
        print("Associated stations: %s. Ignoring stations: %s" % (stations, self._ignore_stations))
        relevant_stations = set(stations).difference(set(self._ignore_stations)) 
        # only want to know the length
        return ((len(relevant_stations) > 0) and self._within_max_runtime() and self._not_at_home())
    
    def shutdown(self):
        if (not self._shutdown_in_progress):
            try:
                self._shutdown_in_progress = True
                print("Shutting RPi down...")
                shutdown_cmd = ['/usr/bin/systemctl', 'halt']
                subprocess.Popen(shutdown_cmd)
            except FileNotFoundError as not_found_error:
                self._shutdown_in_progress = False
                print("!! Cannot shutdown. Error: %s" % not_found_error)


"""
    The Commander sends commands to the TCP socket and processes the results
    It also acts as a facade to the CanSubsystem, Ignition and RpiSubsystem.
    See https://refactoring.guru/design-patterns/facade/python/example
"""
class CarberryCommander:
    
    """
    A reference to the carberry daemon connection
    """
    _carberry  = None


    def __init__(self, port=7070):
        print("Connecting to localhost:%d" % port)

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # instantiate
        client.connect(("localhost", port))  # connect to the carberry daemon
        self._carberry = client.makefile(mode = "rwb") # turn it into a file

        # init subsystems
        self.rpi_subsystem = RpiSubsystem()
        self.can_subsystem = CanSubsystem(self)
        self.ignition_subsystem = IgnitionSubsystem(self, self.rpi_subsystem)

    def _sendCommand(self, command):
        print("-> %s" % command)
        self._carberry.write(bytes(command + '\r\n', 'utf-8') )
        self._carberry.flush()
        reply = self._carberry.readline().decode().strip()
        print("<- %s..." % reply)
        # absorb trailing OK too
        if not (reply.startswith("ERROR") or reply.startswith("EVNT") or reply == "OK" ):
            ok_reply = self._carberry.readline().decode().strip()
            if ok_reply != "OK":
                # something is wrong
                print("!!! <- %s" % ok_reply)

        return(reply) 
    
    def _processCommand(self):
        command = self._carberry.readline().decode().strip()
        print("<- %s..." % command)
        return(command)

    
    def _write_to_file(self, path, value_str):
        with open(path, 'w') as f:
            f.write(value_str)

    def connected(self):
        return(self._carberry != None)

    """ Check if the TCP connection accepts AT command """
    def check_connection(self):
        max_attempts = 2
        attempts = 0
        reply = self._sendCommand("AT")
        while (reply != "OK" and attempts < max_attempts):
            # One more try
            attempts += 1
            reply = self._sendCommand("AT")
        
        # Close connection if too many attempts
        if (attempts == max_attempts):
            self._carberry.close()
            self._carberry = None
            return(False)
        else:
            return(True)

"""
    Entry point
"""
if __name__ == '__main__':
    connected = False
    commander = None

    while not connected:
        print("Sleeping for 1 seconds...")
        time.sleep(1)
        commander = CarberryCommander(7070)
        connected = commander.check_connection()

    # Configure carberry to use the ignition signal
    # See https://www.carberry.it/wiki/carberry/cmds/subsys/canbus/wakeup
    commander.ignition_subsystem.set_can_wakeup_ignition()
    commander.ignition_subsystem.set_ignition_timers(20) # TIMER1 is set in environment variable
    commander.ignition_subsystem.subscribe_ignition_events()
    commander.ignition_subsystem.process_events()

    # following commands are useful when connecting the Carberry via CAN
    #commander.can_subsystem.set_can_wakeup_activity()
    #commander.can_subsystem.set_can_idle_delay(CAN_IDLE_DELAY)    
    #commander.can_subsystem.obd_query_loop()

    time.sleep(60) # take some time before we really exit

    # systemd should restart the python process, if the following is set in carberrycommander.service
    # 
    #[Service]
    #Restart=always
