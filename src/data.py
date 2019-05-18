# -*- coding: utf-8 -*-
# /usr/bin/python
from spidev import SpiDev

import os
import time
import rrdtool
import random
import Adafruit_DHT
# import pigpio
import math
import json
from gpiozero import Button

from ftplib import FTP


# pi = pigpio.pi()
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
basepath = "/home/pi/pi-weather"

settings = json.load(open("{}/settings.json".format(basepath)))
print
print json.dumps(settings, indent=4)
print
dht22 = Adafruit_DHT.AM2302

# windspeed_sensor.when_pressed = None

radius = 7.0
exact_spin_time = 0

file_list = []

files = [
    "{}/temperature_humidity_day.png",
    "{}/wind_speed_dir_day.png",
    "{}/dewpoint_other_day.png",

    "{}/temperature_humidity_week.png",
    "{}/wind_speed_dir_week.png",
    "{}/dewpoint_other_week.png",
    # "{}/live_data.txt"
]

# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class MCP3008:
    def __init__(self, bus = 0, device = 0):
        self.bus, self.device = bus, device
        self.spi = SpiDev()
        self.open()
 
    def open(self):
        self.spi.open(self.bus, self.device)
    
    def read(self, channel = 0):
        adc = self.spi.xfer2([1, (8 + channel) << 4, 0])
        data = ((adc[1] & 3) << 8) + adc[2]
        return data
            
    def close(self):
        self.spi.close()

class Air:  # fix this
    def __init__(self, temperature=0.0, humidity=0.0, dewpoint=0.0, vp=0.0, svp=0.0):
        self._rh = humidity  # Relative Humidity
        self._T = temperature  # Temperature
        self._TK = temperature + 273.15  # Temperature in K
        self._DT = dewpoint  # Dewpoint
        self._VP = vp  # Vapor Pressure
        self._SVP = svp  # Saturated Vapor Pressure

        self._R = 8314.3  # Gas Constant (J/kmol*K)
        self._mw = 18.016  # Water Vapor Molar Weight (kg/kmol)

    '''
    def update(self, temperature=0.0, humidity=0.0, dewpoint=0.0, vp=0.0, svp=0.0):
        self._rh = humidity  # Relative Humidity
        self._T = temperature  # Temperature
        self._TK = temperature + 273.15  # Temperature in K
        self._DT = dewpoint  # Dewpoint
        self._VP = vp  # Vapor Pressure
        self._SVP = svp  # Saturated Vapor Pressure
    '''

    def _a(self):
        if self._T >= 0.0:
            return 7.5
        else:
            return 7.6

    def _b(self):
        if self._T >= 0.0:
            return 237.3
        else:
            return 240.7

    def T(self):
        return self._T

    def SDD(self, T):
        return 6.1078 * math.pow(10, ((self._a() * T) / (self._b() + T)))

    def rh(self):
       return self._rh

    def DD(self):
        return self.rh() / 100 * self.SDD(self._T)

    def v(self):
        return math.log10(self.DD() / 6.1078)

    def DP(self):
        return self._b() * self.v() / (self._a() - self.v())


def update_dht():  # DHT 22
    global data
    #dht22.trigger()
    
    time.sleep(0.1)
    humidity, temperature = Adafruit_DHT.read_retry(dht22, settings["sensors"]["am2302"]["pin"])
    print humidity, temperature
    data["air_temperature"] = round(temperature, 2)
    data["humidity"] = round(humidity, 2)


anemometer_hits = 0


def anemometer_callback():
    global anemometer_hits
    anemometer_hits += 1
    print "{}".format(anemometer_hits)


windspeed_sensor = Button(27)

windspeed_sensor.when_pressed = anemometer_callback
#windspeed_sensor.when_released = anemometer_callback
def update_anemometer():  # GPIO Input H/L
    global exact_spin_time, anemometer_hits, data
    halfed_hits = int(anemometer_hits / 2.0)
    exact_delta_time = time.time() - exact_spin_time
    exact_spin_time = time.time()
    print "hits {}".format(anemometer_hits)
    speed = (halfed_hits * radius) / exact_delta_time # cm/s
    speed = (speed / 100) * 3.6 # m/s
    print "windspeed {}".format(speed)
    anemometer_hits = 0
    data["wind_speed"] = round(speed, 2)


def update_windirection():  # MCP3008
    global data
    data["wind_direction"] = random.randint(0, 360)


def update_others():  # Dewpoint calculation, etc.
    global data
    air = Air(temperature=data["air_temperature"], humidity=data["humidity"])
    dewpoint = air.DP()
    cloudbase = (data["air_temperature"] - dewpoint) * 125 + int(settings["baseheight"])  # TODO: move this to Air class
    print cloudbase
    data["dewpoint"] = cloudbase  # Refactor naming


def initialize_file_list():
    global file_list
    for file in file_list:
        filename = os.path.join(file, basepath)
        print file
        file_list.append({"file": filename, "mtime": os.path.getmtime(filename)})


def get_file_list():
    new_file_list = []
    for file in file_list:
        filename = os.path.join(file, basepath)
        print file
        new_file_list.append({"file": filename, "mtime": os.path.getmtime(filename)})
    return new_file_list


def upload_bulk(files):
    try:
        ftp = FTP("server.net")
        ftp.login(user="user", passwd="passwd")  # settings.json
        ftp.cwd("/html")

        for file in files:
            filepath = file["file"]
            filename = os.path.split(filepath)[1]
            ftp.storbinary("STOR {}".format(filename), open(filepath, "rb"))
    except Exception as e:
        print "exception! {}".format(e)


def execute_ftp():  # push data in form of usable files onto server
    global ftp, file_list
    ftp_list = []
    new_list = get_file_list()

    for idx in xrange(len(new_list)):
        if new_list[idx]["mtime"] > file_list[idx]["mtime"]:
            ftp_list.append(new_list[idx]["file"])

    file_list = new_list

    if ftp_list:
        upload_bulk(ftp_list)


def update_database():
    if not os.path.isfile("{}/data.rrd".format(basepath)):
        rrdtool.create(
            "{}/data.rrd".format(basepath),
            "--step", "60",

            "DS:air_temperature:GAUGE:240:U:U",
            "RRA:AVERAGE:0.5:1:20160",
            "RRA:MAX:0.5:1:20160",
            "RRA:MIN:0.5:1:20160",

            "DS:dewpoint:GAUGE:240:U:U",
            "RRA:AVERAGE:0.5:1:20160",
            "RRA:MAX:0.5:1:20160",
            "RRA:MIN:0.5:1:20160",

            "DS:humidity:GAUGE:240:U:U",
            "RRA:AVERAGE:0.5:1:20160",
            "RRA:MAX:0.5:1:20160",
            "RRA:MIN:0.5:1:20160",

            "DS:wind_speed:GAUGE:240:U:U",
            "RRA:AVERAGE:0.5:1:20160",
            "RRA:MAX:0.5:1:20160",
            "RRA:MIN:0.5:1:20160",

            "DS:wind_direction:GAUGE:240:U:U",
            "RRA:AVERAGE:0.5:1:20160",
            "RRA:MAX:0.5:1:20160",
            "RRA:MIN:0.5:1:20160"
        )
    global data
    try:
        rrdtool.update("{}/data.rrd".format(basepath), "N:{:4f}:{:4f}:{:4f}:{:4f}:{:4f}".format(
            data["air_temperature"],
            data["dewpoint"],
            data["humidity"],
            data["wind_speed"],
            data["wind_direction"]
        ))
        print "database updated."
    except Exception as e:
        print "exception {}".format(e)
        return


def create_graph():
    # didn't have success with args as a list, will try later
    print "creating graphs"
    rrdtool.graph(
        '{}/day_temperature.png'.format(basepath),
        "--width", '400',
        "--height", '100',
        "--start", "end-1d",
        "-v", "°C",
        'DEF:airtemp={}/data.rrd:air_temperature:AVERAGE'.format(basepath),
        'AREA:airtemp#3333CC:°C Luft'
    )
    rrdtool.graph(
        '{}/week_temperature.png'.format(basepath),
        "--width", '400',
        "--height", '100',
        "--start", "end-7d",
        "-v", "°C",
        'DEF:airtemp={}/data.rrd:air_temperature:AVERAGE'.format(basepath),
        'AREA:airtemp#3333CC:°C Luft'
    )

    rrdtool.graph(
        '{}/week_temperature.png'.format(basepath),
        "--width", '400',
        "--height", '100',
        "--start", "end-7d",
        "-v", "°C",
        'DEF:airtemp={}/data.rrd:air_temperature:AVERAGE'.format(basepath),
        'AREA:airtemp#3333CC:°C Luft'
    )

    rrdtool.graph(
        '{}/week_temperature.png'.format(basepath),
        "--width", '400',
        "--height", '100',
        "--start", "end-7d",
        "-v", "°C",
        'DEF:airtemp={}/data.rrd:air_temperature:AVERAGE'.format(basepath),
        'AREA:airtemp#3333CC:°C Luft'
    )
    print "creatd graphs"


data = {"air_temperature": 0.0, "dewpoint": 0.0, "humidity": 0.0, "wind_speed": 0, "wind_direction": 0}

if __name__ == "__main__":
    print "starting loop!"
    while True:
        try:
            update_dht()
            update_anemometer()
            update_windirection()
            update_others()
            
            update_database()
            create_graph()
            execute_ftp()
            time.sleep(60)
        except Exception as e:
            time.sleep(5)
            print "exception {}".format(e)
            continue
