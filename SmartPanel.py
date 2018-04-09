#!/usr/bin/python3

# SmartPanel - Smart Home control panel
# with Raspberry Pi and RPi Touch Screen

# Author: Stefan Haun <tux@netz39.de>

import rpi_backlight as bl
import queue

from time import sleep
import signal
import sys
from datetime import datetime

import configparser

from threading import Timer, Thread, Event

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle
from kivy.core.text import Label as CoreLabel
from kivy.uix.label import Label
from kivy.uix.image import Image

from kivy.clock import Clock

import paho.mqtt.client as mqtt

class BacklightTimer():

    def __init__(self, timeout=30, brightness=128):
        self.timeout = timeout
        self.brightness = brightness
    
    def handle_timer(self):
        print("Backlight timeout")
        
        bl.set_brightness(11, smooth=True, duration=0.5)
        bl.set_power(False)
    
    def start(self):
        self.timer = Timer(self.timeout, self.handle_timer)
        self.timer.start()
    
    def cancel(self):
        self.timer.cancel()
        
    def turn_on(self):
        bl.set_power(True)
        bl.set_brightness(self.brightness, smooth=True, duration=0.5)
        
    def reset(self):
        self.timer.cancel()
    
        dimmed = not bl.get_power()
    
        if dimmed:
            self.turn_on()
        
        self.start()
        
        return dimmed


class Thing():
    def __init__(self, key, cfg, mqtt, widget):
        self.key = key
        self.cfg = cfg
        self.mqtt = mqtt
        self.widget = widget
    
    def init(self):
        print("initializing thing", self.key)
        section = "Thing:"+self.key
        
        self.name = self.cfg.get(section, "name")
        self.tp = self.cfg.get(section, "type")
        self.topic = self.cfg.get(section, "topic")

        posX = int(self.cfg.get(section, "posX"))
        self.position = (posX, 50)
        self.size = (100, 100)
        
        self.widget.add_widget(
            Label(pos=(self.position[0],150), text=self.name, font_size='20sp', color=(1, 1, 0, 1)))
        
        with self.widget.canvas:
            Color(1, 0, 0, 1, mode='rgba')
            Rectangle(pos=self.position, size=self.size)
        
        return


def on_mqtt_state(client, userdata, message):
    userdata.set_pwr_state(str(message.payload)[2:-1])

class SmartPanelWidget(Widget):
    def __init__(self, backlight, mqtt, cfg, **kwargs):
        super(SmartPanelWidget, self).__init__(**kwargs)
        
        self.back_tmr = backlight
        self.back_tmr.turn_on()
        self.back_tmr.start()
        
        self.cfg = cfg
        
        self.mqtt = mqtt
        self.mqtt.user_data_set(self)
        self.mqtt.message_callback_add(MQTT_SW_TOPIC+"/POWER", on_mqtt_state)

        # Initialize the things
        self.things = []
        for sec in filter(lambda s: s.startswith("Thing:"),
                          self.cfg.sections()):
            t = Thing(sec[6:], self.cfg, self.mqtt, self)
            t.init()
            self.things.append(t)

        mylabel = CoreLabel(text="Hi there!", font_size=25, color=(0, 0.50, 0.50, 1))
        mylabel.refresh()
        texture = mylabel.texture
        texture_size = list(texture.size)
        
        self.IMGDIR="resources/nixie/"
        clock_pos = (300, 250)
        self.clock_img = []
        # Hour 1
        self.clock_img.append(
            Image(pos=(clock_pos[0]+0*(88+5), clock_pos[1]),
                        source=self.IMGDIR+"off.png",
                        size=(200, 172),
                        allow_stretch="false"))
        # Hour 2
        self.clock_img.append(
            Image(pos=(clock_pos[0]+1*(88+5), clock_pos[1]),
                        source=self.IMGDIR+"off.png",
                        size=(200, 172),
                        allow_stretch="false"))
        # Minute 1
        self.clock_img.append(
            Image(pos=(clock_pos[0]+20+2*(88+5), clock_pos[1]),
                        source=self.IMGDIR+"off.png",
                        size=(200, 172),
                        allow_stretch="false"))
        # Minute 2
        self.clock_img.append(
            Image(pos=(clock_pos[0]+20+3*(88+5), clock_pos[1]),
                        source=self.IMGDIR+"off.png",
                        size=(200, 172),
                        allow_stretch="false"))
        
        for img in self.clock_img:
            self.add_widget(img)
        
        Clock.schedule_interval(self.set_clock, 1)
        
        self.repaint_canvas()
        
    
    
    def set_clock(self, dt):
        datestr = str(datetime.now())
        
        ds = datestr[11:13] + datestr[14:16]
        
        for i in range(0,4):
            src = self.IMGDIR+ds[i]+".png"
            
            if not src == self.clock_img[i].source:
                self.clock_img[i].source=src
                self.clock_img[i].reload()
    
    
    def on_touch_down(self, touch):
        if not self.back_tmr.reset():
            pos = touch.pos
            print("Touch at ", pos)
            
            thing = None
            for t in self.things:
                if ((pos[0] > t.position[0]) and
                   (pos[1] > t.position[1]) and
                   (pos[0] < t.position[0] + t.size[0]) and
                   (pos[1] < t.position[1] + t.size[1])):
                    thing = t;
                    break;
            
            if not thing == None:
                print("Match at thing", thing.name)
                
                self.mqtt.publish(thing.topic+"/cmnd/Power1", "TOGGLE", qos=2)
                
                if thing.tp == "TASMOTA WS2812":
                    sleep(1)
                    self.mqtt.publish(thing.topic+"/cmnd/Power3", "TOGGLE", qos=2)
        
        return True


    def set_pwr_state(self, state):
        with self.canvas:
            if state == "ON":
                Color(0, 1, 0, 1, mode='rgba')
            if state == "OFF":
                Color(1, 0, 0, 1, mode='rgba')
        
        with self.canvas:
            Rectangle(pos=(50,50), size=(100,100))
    
    def repaint_canvas(self):
        with self.canvas:
            Color(1, 0, 0, 1, mode='rgba')
            Rectangle(pos=(50, 50), size=(100,100))
            Rectangle(pos=(250, 50), size=(100,100))
        


class SmartPanelApp(App):
    def __init__(self, mqtt, cfg, **kwargs):
        super(SmartPanelApp, self).__init__(**kwargs)
        
        self.mqtt = mqtt
        self.cfg = cfg
    
    
    def build(self):
        timeout_s = self.cfg.get("Backlight", "timeout")
        brightness_s = self.cfg.get("Backlight", "brightness")
        
        self.back_tmr = BacklightTimer(timeout = int(timeout_s), 
                                       brightness = int(brightness_s))
        
        widget = SmartPanelWidget(self.back_tmr, self.mqtt, self.cfg)
        
        return widget


global running
running = True

def sigint_handler(signal, frame):
    global running
    
    if running:
        print("SIGINT received. Stopping the queue.")
        running = False
    else:
        print("Receiving SIGINT the second time. Exit.");
        sys.exit(0)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, sigint_handler)
    
    config = configparser.ConfigParser()
    config.read("smartpanel.cfg")
    
    MQTT_HOST = config.get("MQTT", "host");
    MQTT_SW_TOPIC = config.get("MQTT", "topic")
    
    bl.set_power(True)
    bl.set_brightness(128)
    
    client = mqtt.Client()
    client.connect(MQTT_HOST, 1883, 60)
    client.subscribe(MQTT_SW_TOPIC+"/#")
    client.loop_start()
    
    app = SmartPanelApp(client, config)
    app.run()
    
    client.loop_stop()


# kate: space-indent on; indent-width 4; mixedindent off; indent-mode python; indend-pasted-text false; remove-trailing-space off
