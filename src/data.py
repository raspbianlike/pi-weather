# -*- coding: utf-8 -*-
# /usr/bin/python
import os
import time
import rrdtool
import random

basepath = "/home/raspbian/wetterstation/"


def update_temperature():  # DHT 22
    data["air_temperature"] = random.randint(15, 30)


def update_humidity():  # DHT 22
    data["humidity"] = random.randint(40, 100)


def update_windspeed():  # GPIO Input H/L
    data["wind_speed"] = random.randint(2, 30)


def update_windirection():  # MCP3008
    data["wind_direction"] = random.randint(0, 360)


def update_others():  # Dewpoint calculation, etc.
    pass

def ftp(): # push data in form of parsable file onto serverg
    pass

def update_database():
    if not os.path.isfile("/home/raspbian/wetterstation/data.rrd"):
        print "no file"
        rrdtool.create(
            "/home/raspbian/wetterstation/data.rrd",
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
        rrdtool.update("/home/raspbian/wetterstation/data.rrd", "N:{:4f}:{:4f}:{:4f}:{:4f}:{:4f}".format(
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
    rrdtool.graph(
        '{}temperature.png'.format(basepath),
        "--width", '400',
        "--height", '100',
        "--start", "end-1d",
        "-v", "°C",
        'DEF:airtemp={}data.rrd:airtemperature:AVERAGE'.format(basepath),
        'AREA:airtemp#3333CC:°C Luft'
    )


data = {"air_temperature": 0.0, "dewpoint": 0.0, "humidity": 0.0, "wind_speed": 0, "wind_direction": 0}

if __name__ == "__main__":
    print "starting loop!"
    while True:
        try:
            update_temperature()
            update_humidity()
            update_windspeed()
            update_windirection()
            update_others()

            update_database()
            create_graph()
            time.sleep(60)
        except Exception as e:
            time.sleep(5)
            print "exception {}".format(e)
            continue
