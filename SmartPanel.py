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
from kivy.core.text import Label as CoreLabel
from kivy.uix.label import Label

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

        mylabel = CoreLabel(text="Hi there!", font_size=25, color=(0, 0.50, 0.50, 1))
        mylabel.refresh()
        texture = mylabel.texture
        texture_size = list(texture.size)
        
        with self.canvas:
            # instr. for main canvas
            Color(1, 0, 0, 1, mode='rgba')
            Rectangle(pos=(50, 50), size=(100,100))
            Rectangle(pos=(250, 50), size=(100,100))
        
        self.add_widget(Label(pos=(50,150), text="Bed Room", font_size='20sp', color=(1, 1, 0, 1)))
        self.add_widget(Label(pos=(250,150), text="Living Room", font_size='20sp', color=(1, 1, 0, 1)))
        
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
            Rectangle(pos=(50,50), size=(100,100))
        


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
    
    app = SmartPanelApp(client, config)
    app.run()
    
    client.loop_stop()


# kate: space-indent on; indent-width 4; mixedindent off; indent-mode python; indend-pasted-text false; remove-trailing-space off
