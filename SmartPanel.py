#!/usr/bin/python3

# SmartPanel - Smart Home control panel
# with Raspberry Pi and RPi Touch Screen

# Author: Stefan Haun <tux@netz39.de>

import rpi_backlight as bl
import queue
from enum import Enum

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
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.boxlayout import BoxLayout

from kivy.clock import Clock

import paho.mqtt.client as mqtt



MQTT_TOPICS = []

def mqtt_add_topic_callback(mqtt, topic, cb):
    mqtt.subscribe(topic)
    MQTT_TOPICS.append(topic)
    
    mqtt.message_callback_add(topic, cb)


def on_mqtt_connect(client, userdata, flags, rc):
    print("Connected with code %s" % rc)
    for topic in MQTT_TOPICS:
        client.subscribe(topic)


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

class ThingState(Enum):
    UNKNOWN = 0
    OFF = 1
    ON = 2
    
    
    def for_message(msg):
        state = ThingState.UNKNOWN
        
        if msg == "ON":
            state = ThingState.ON
        if msg == "OFF":
            state = ThingState.OFF
        
        return state


class Thing():
    def __init__(self, key, cfg, mqtt, widget):
        self.key = key
        self.cfg = cfg
        self.mqtt = mqtt
        self.widget = widget
        
        self.state = ThingState.UNKNOWN
        
        section = "Thing:"+self.key
        self.name = self.cfg.get(section, "name")
        self.tp = self.cfg.get(section, "type")
        self.topic = self.cfg.get(section, "topic")
        
        mqtt_add_topic_callback(self.mqtt, self.get_pwr_topic(), self.on_pwr_state)
        
        posX = int(self.cfg.get(section, "posX"))
        self.position = (posX, 50)
        self.size = (100, 100)
        
        self.widget.add_widget(
            Label(pos=(self.position[0],150), text=self.name,
                  font_size='20sp', color=(1, 1, 0, 1),
                  size_hint=(None, None)))
        
        self.repaint()
        
        return
    
    def get_pwr_topic(self):
        pwr = "/POWER1" if self.tp == "TASMOTA WS2812" else "/POWER"
        
        return self.topic+pwr


    def check_bounds(self, pos):
        return (pos[0] > self.position[0]) and \
               (pos[1] > self.position[1]) and \
               (pos[0] < self.position[0] + self.size[0]) and \
               (pos[1] < self.position[1] + self.size[1])


    def toggle(self):
        self.state = ThingState.UNKNOWN
        self.repaint()
        
        self.mqtt.publish(self.topic+"/cmnd/Power1", "TOGGLE", qos=2)
        
        if self.tp == "TASMOTA WS2812":
            sleep(1)
            self.mqtt.publish(self.topic+"/cmnd/Power3", "TOGGLE", qos=2)
    
    
    def on_pwr_state(self, client, userdata, message):
        topic = message.topic
        state = str(message.payload)[2:-1]
        self.state = ThingState.for_message(state)
        
        print("Power {s} for {t}".format(t=topic, s=state))
        
        
        self.repaint()
    
    
    def get_state_color(self):
        col = Color(0.8, 0.8, 0.8, 1, mode='rgba')
        if self.state == ThingState.ON:
            col = Color(0, 1, 0, 1, mode='rgba')
        if self.state == ThingState.OFF:
            col = Color(1, 0, 0, 1, mode='rgba')
        
        return col
    
    
    def repaint(self):
        with self.widget.canvas:
            Rectangle(color=self.get_state_color(), pos=self.position, size=self.size)

class ClockWidget(BoxLayout):
    def __init__(self, cfg, basepath, **kwargs):
        self.orientation = 'horizontal'
        self.spacing = self.size[0]*0.01
        super(ClockWidget, self).__init__(**kwargs)
        self.cfg = cfg
        
        self.basepath = basepath
        
        self.clock_img = []
        for i in range(0,4):
            img = Image(source=self.basepath+"off.png")
            self.clock_img.append(img)
            self.add_widget(img)
            if i == 1:
                self.add_widget(
                    Widget(size=(self.size[0]*0.05, 1), 
                           size_hint=(None, 1)))
        
        Clock.schedule_interval(self.set_clock, 1)


    def set_clock(self, dt):
        datestr = str(datetime.now())
        
        ds = datestr[11:13] + datestr[14:16]
        
        for i in range(0,4):
            src = self.basepath+ds[i]+".png"
            
            if not src == self.clock_img[i].source:
                self.clock_img[i].source=src
                self.clock_img[i].reload()


class SmartPanelWidget(RelativeLayout):
    def __init__(self, backlight, mqtt, cfg, **kwargs):
        super(SmartPanelWidget, self).__init__(**kwargs)
        
        self.back_tmr = backlight
        self.back_tmr.turn_on()
        self.back_tmr.start()
        
        self.cfg = cfg
        
        self.mqtt = mqtt

        # Initialize the things
        self.things = []
        for sec in filter(lambda s: s.startswith("Thing:"),
                          self.cfg.sections()):
            t = Thing(sec[6:], self.cfg, self.mqtt, self)
            self.things.append(t)
        
        self.IMGDIR="resources/nixie/"
        clock_pos = (380, 280)
        
        self.clock = ClockWidget(self.cfg, self.IMGDIR,
                                 pos=clock_pos, size=(370, 150),
                                 size_hint=(None, None))
        self.add_widget(self.clock)
        
    
    
    def filter_things_by_bounds(self, pos):
        return filter(lambda t: t.check_bounds(pos), self.things)
    
    
    def on_touch_down(self, touch):
        if not self.back_tmr.reset():
            pos = touch.pos
            print("Touch at ", pos)
            
            things = self.filter_things_by_bounds(pos)
            for thing in things:
                print("Match at thing", thing.name)
                thing.toggle()
            
        return True


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
        
        widget = SmartPanelWidget(self.back_tmr, self.mqtt, self.cfg,
                                  pos = (0,0), size = (800, 480))
        
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
    MQTT_TOPICS.append(MQTT_SW_TOPIC+"/#")
    
    bl.set_power(True)
    bl.set_brightness(128)
    
    client = mqtt.Client()
    client.on_connect = on_mqtt_connect
    client.connect(MQTT_HOST, 1883, 60)
#    client.subscribe(MQTT_SW_TOPIC+"/#")
    client.loop_start()
    
    app = SmartPanelApp(client, config)
    app.run()
    
    client.loop_stop()


# kate: space-indent on; indent-width 4; mixedindent off; indent-mode python; indend-pasted-text false; remove-trailing-space off
