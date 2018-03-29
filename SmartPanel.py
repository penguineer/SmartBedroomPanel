#!/usr/bin/python3

# SmartPanel - Smart Home control panel
# with Raspberry Pi and RPi Touch Screen

# Author: Stefan Haun <tux@netz39.de>

import rpi_backlight as bl
import queue

from time import sleep
import signal
import sys

import configparser

from threading import Timer, Thread, Event

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle

import paho.mqtt.client as mqtt

class BacklightTimer():

    def __init__(self, t):
        self.t = t
        self.timer = Timer(self.t, self.handle_timer)
    
    def handle_timer(self):
        print("Backlight timeout")
        
        bl.set_brightness(11, smooth=True, duration=0.5)
        bl.set_power(False)
    
    def start(self):
        self.timer.start()
    
    def cancel(self):
        self.timer.cancel()
        
    def turn_on(self):
        bl.set_power(True)
        bl.set_brightness(128, smooth=True, duration=0.5)
        
    def reset(self):
        self.timer.cancel()
    
        dimmed = not bl.get_power()
    
        if dimmed:
            self.turn_on()
        
        self.timer = Timer(self.t, self.handle_timer)
        self.timer.start()
        
        return dimmed

def on_mqtt_state(client, userdata, message):
    userdata.set_pwr_state(str(message.payload)[2:-1])

class SmartPanelWidget(Widget):
    def __init__(self, backlight, mqtt, **kwargs):
        super(SmartPanelWidget, self).__init__(**kwargs)
        
        self.back_tmr = backlight
        self.back_tmr.turn_on()
        self.back_tmr.start()
        
        self.mqtt = mqtt
        self.mqtt.user_data_set(self)
        self.mqtt.message_callback_add(MQTT_SW_TOPIC+"/POWER", on_mqtt_state)

        with self.canvas:
            # instr. for main canvas
            Color(1, 0, 0, 1, mode='rgba')
            Rectangle(pos=self.pos, size=(100,100))
        
        #with self.canvas.before:
            # rendered before
        
        #with self.canvas.after:
            # rendered after
        
    
    def on_touch_down(self, touch):
        if not self.back_tmr.reset():
            pos = touch.pos
            print("Touch at ", pos)
            
            self.mqtt.publish(MQTT_SW_TOPIC+"/cmnd/Power1", "TOGGLE", qos=2)
        
        return True


    def set_pwr_state(self, state):
        with self.canvas:
            if state == "ON":
                Color(0, 1, 0, 1, mode='rgba')
            if state == "OFF":
                Color(1, 0, 0, 1, mode='rgba')
        
        with self.canvas:
            Rectangle(pos=self.pos, size=(100,100))
        


class SmartPanelApp(App):
    def __init__(self, mqtt, **kwargs):
        super(SmartPanelApp, self).__init__(**kwargs)
        
        self.mqtt = mqtt
    
    def build(self):
        self.back_tmr = BacklightTimer(10)
        
        widget = SmartPanelWidget(self.back_tmr, self.mqtt)
        
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
    
    app = SmartPanelApp(client)
    app.run()
    
    client.loop_stop()


# kate: space-indent on; indent-width 4; mixedindent off; indent-mode python; indend-pasted-text false; remove-trailing-space off
