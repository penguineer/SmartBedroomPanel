#!/usr/bin/python3

# SmartPanel - Smart Home control panel
# with Raspberry Pi and RPi Touch Screen

# Author: Stefan Haun <tux@netz39.de>

import queue
from enum import Enum

from time import sleep
import signal
import sys
from datetime import datetime

import configparser

from threading import Timer, Thread, Event

from kivy.app import App
from kivy.config import Config
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, Line
from kivy.core.text import Label as CoreLabel
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import ListProperty, StringProperty, NumericProperty
from kivy.lang import Builder

from kivy.clock import Clock

import paho.mqtt.client as mqtt


class RM_COLOR:
    def get_rgba(name):
        # grey is fallback
        c = (77, 77, 76, 256)

        if name == "fresh" or name == "light blue":
            c = (0, 132, 176, 256)

        if name == "hope" or name == "green":
            c = (0, 163, 86, 256)

        if name == "glint" or name == "yellow":
            c = (249, 176, 0, 256)

        if name == "beat" or name == "red":
            c = (228, 5, 41, 256)

        if name == "tenacity" or name == "lilac":
            c = (68, 53, 126, 256)

        if name == "base" or name == "dark blue":
            c = (24, 56, 107, 256)

        # reboot (grey) is fallback from above

        return list(map(lambda x: x/256, c))


    def get_Color(name):
        c = RM_COLOR.get_rgba(name)
        return Color(c[0], c[1], c[2], c[3], mode='rgba')


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

    def __init__(self, bl, timeout=30, brightness=128):
        self.bl = bl
        self.timeout = timeout
        self.brightness = brightness

        self.timer = None

        self.bl.set_power(True)
        self.bl.set_brightness(128)

    def handle_timer(self):
        print("Backlight timeout")
        
        self.bl.set_brightness(11, smooth=True, duration=0.5)
        self.bl.set_power(False)
    
    def start(self):
        self.timer = Timer(self.timeout, self.handle_timer)
        self.timer.start()
    
    def cancel(self):
        self.timer.cancel()
        
    def turn_on(self):
        self.bl.set_power(True)
        self.bl.set_brightness(self.brightness, smooth=True, duration=0.5)
        
    def reset(self):
        self.timer.cancel()
    
        dimmed = not self.bl.get_power()
    
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


Builder.load_string('''
<Thing>:
    font_size: self.size[1] * 2 / 5
    handle_x: int(self.size[1] * 5 / 7)
    text_s_x: self.size[0] - self.handle_x
    text_s_y: self.size[1] - 10
    text_x: int(self.handle_x / 2) + 20

    canvas:
        Color:
            rgba: self.state_color
        Rectangle:
            size: (self.size[1] * 5 / 7, self.size[1])
        Line:
            rounded_rectangle: (2, 2, self.size[0], self.size[1] - 4, 20)
            width: 2

    Label:
        text: root.name
        color: root.state_color
        pos: (root.text_x, 0)
        text_size: (root.text_s_x, root.text_s_y)
        font_size: root.font_size
        halign: 'left'
        valign: 'middle'

''')


class Thing(RelativeLayout):
    state_color = ListProperty(RM_COLOR.get_rgba("reboot"))
    name = StringProperty("<None>")

    def __init__(self, key, cfg, mqtt, widget, pos=(0, 0), **kwargs):
        self.key = key
        self.cfg = cfg
        self.mqtt = mqtt
        self.widget = widget
        
        self.state = ThingState.UNKNOWN
        self.state_color = self.get_state_color()

        section = "Thing:"+self.key
        self.name = self.cfg.get(section, "name")
        self.tp = self.cfg.get(section, "type")
        self.topic = self.cfg.get(section, "topic")
        
        mqtt_add_topic_callback(self.mqtt, self.get_state_topic(), self.on_pwr_state)

        super(Thing, self).__init__(pos=pos,
                                    size=(300, 80), size_hint=(None, None),
                                    **kwargs)

        self.mqtt_trigger = Clock.create_trigger(self.mqtt_toggle)
        
        # query the state
        self.mqtt.publish(self.topic+"/cmnd/Power1", "?", qos=2)

    def get_state_topic(self):
        pwr = "/POWER1" if self.tp == "TASMOTA WS2812" else "/POWER"
        
        return self.topic+pwr

    def on_touch_down(self, touch):
        if self.collide_point(touch.pos[0], touch.pos[1]):
            self.toggle()

            return True
        else:
            return super(Thing, self).on_touch_down(touch)

    def toggle(self):
        self.state = ThingState.UNKNOWN
        self.state_color = self.get_state_color()

        self.mqtt_trigger()

    def mqtt_toggle(self, *largs):
        self.mqtt.publish(self.topic+"/cmnd/Power1", "TOGGLE", qos=2)
        
        if self.tp == "TASMOTA WS2812":
            sleep(1)
            self.mqtt.publish(self.topic+"/cmnd/Power3", "TOGGLE", qos=2)

    def on_pwr_state(self, client, userdata, message):
        topic = message.topic
        state = str(message.payload)[2:-1]
        self.state = ThingState.for_message(state)
        self.state_color = self.get_state_color()

        print("Power {s} for {t}".format(t=topic, s=state))

    def get_state_color(self):
        col = RM_COLOR.get_rgba("grey")
        if self.state == ThingState.ON:
            col = RM_COLOR.get_rgba("green")
        if self.state == ThingState.OFF:
            col = RM_COLOR.get_rgba("red")
        
        return col


Builder.load_string('''
<ClockWidget>:
    size: (300, 260)
    size_hint: (None, None)

    canvas:
        # Upper rounded rect
        Color:
            rgba: self.base_color
        Line:
            rounded_rectangle: (22, self.size[1]-80, self.size[0]-44, 76, 20)
            width: 2           

        # Alarm rounded rect
        Color:
            rgba: self.alarm_color
        Line:
            rounded_rectangle: (22, 2, self.size[0]-44, 120, 20)
            width: 2                  
        
        # Clock stencil
        Color:
            rgba: [0, 0, 0, 1]
        Rectangle:
            pos: (0, self.size[1]-122-47)
            size: (300, 122)
            
        # Clock rounded rect
        Color:
            rgba: self.base_color
        Line:
            rounded_rectangle: (2, self.size[1]-112-51, 296, 110, 20)
            width: 2           
                    
        # Remove this later
        Color:
            rgba: [0, 0, 0, 0]
        Rectangle:
            pos: (0, 0)
            size: (300, 94)

    BoxLayout
        pos: (5, root.size[1]-53)
        size_hint: (None, None)
        size: (290, 45)

        Label:
            text: root.current_date
            color: root.base_color
            font_size: 40
            font_name: 'resources/FiraMono-Regular.ttf'


    BoxLayout:
        pos: (5, root.size[1]-158)
        size_hint: (None, None)
        size: (290, 100)
               
        Image:
            source: root.clk_image_src_0
            
        Image:
            source: root.clk_image_src_1
        
        Widget:
            size: (root.size[0]*0.05, 1)
            size_hint: (None, 1)
            
        Image:
            source: root.clk_image_src_2
            
        Image:
            source: root.clk_image_src_3
    
    BoxLayout: 
        pos: (18, 22)
        size_hint: (None, None)
        size: (240, 60)
        
        Image:
            source: 'resources/alarm_icon.png'
            color: root.alarm_color
            size_hint: (None, 1)

        Image:
            source: root.alarm_image_src_0
            color: (1, 1, 1, root.alarm_digit_alpha)
            
        Image:
            source: root.alarm_image_src_1
            color: (1, 1, 1, root.alarm_digit_alpha)
        
        Widget:
            size: (10, 1)
            size_hint: (None, 1)
            
        Image:
            source: root.alarm_image_src_2
            color: (1, 1, 1, root.alarm_digit_alpha)
            
        Image:
            source: root.alarm_image_src_3
            color: (1, 1, 1, root.alarm_digit_alpha)
''')


class ClockWidget(RelativeLayout):
    base_color = ListProperty(RM_COLOR.get_rgba("yellow"))
    clk_image_src_0 = StringProperty("")
    clk_image_src_1 = StringProperty("")
    clk_image_src_2 = StringProperty("")
    clk_image_src_3 = StringProperty("")
    alarm_color = ListProperty(RM_COLOR.get_rgba("reboot"))
    alarm_digit_alpha = NumericProperty(0)
    alarm_image_src_0 = StringProperty("")
    alarm_image_src_1 = StringProperty("")
    alarm_image_src_2 = StringProperty("")
    alarm_image_src_3 = StringProperty("")
    current_date = StringProperty("    -  -  ")

    def __init__(self, cfg, basepath, touch_cb=None, **kwargs):
        self.orientation = 'horizontal'
        self.spacing = self.size[0]*0.01
        super(ClockWidget, self).__init__(**kwargs)
        self.cfg = cfg
        
        self.basepath = basepath

        self.clk_image_src_0 = self.basepath + "off.png"
        self.clk_image_src_1 = self.basepath + "off.png"
        self.clk_image_src_2 = self.basepath + "off.png"
        self.clk_image_src_3 = self.basepath + "off.png"

        self.alarm = None

        self.touch_cb = touch_cb

        Clock.schedule_interval(self.set_clock, 1)

    def set_alarm(self, alarm):
        """Alarm in the form of 'HH:MM'"""
        self.alarm = alarm

    def set_clock(self, _):
        datestr = str(datetime.now())

        self.current_date = datestr[0:10]

        self.clk_image_src_0 = "{0}{1}.png".format(self.basepath, datestr[11])
        self.clk_image_src_1 = "{0}{1}.png".format(self.basepath, datestr[12])
        self.clk_image_src_2 = "{0}{1}.png".format(self.basepath, datestr[14])
        self.clk_image_src_3 = "{0}{1}.png".format(self.basepath, datestr[15])

        if not self.alarm:
            self.alarm_digit_alpha = 1
            self.alarm_color = RM_COLOR.get_rgba("reboot")
            self.alarm_image_src_0 = self.basepath + "off.png"
            self.alarm_image_src_1 = self.basepath + "off.png"
            self.alarm_image_src_2 = self.basepath + "off.png"
            self.alarm_image_src_3 = self.basepath + "off.png"
        else:
            self.alarm_digit_alpha = 1
            self.alarm_color = RM_COLOR.get_rgba("yellow")
            self.alarm_image_src_0 = "{0}{1}.png".format(self.basepath, self.alarm[0])
            self.alarm_image_src_1 = "{0}{1}.png".format(self.basepath, self.alarm[1])
            self.alarm_image_src_2 = "{0}{1}.png".format(self.basepath, self.alarm[3])
            self.alarm_image_src_3 = "{0}{1}.png".format(self.basepath, self.alarm[4])

    def on_touch_down(self, touch):
        if self.collide_point(touch.pos[0], touch.pos[1]):
            if self.touch_cb:
                self.touch_cb()

            return True
        else:
            return super(ClockWidget, self).on_touch_down(touch)


Builder.load_string('''
<PlayerWidget>:
    size: (470, 190)
    size_hint: (None, None)

    canvas:
        # Upper rounded rect
        Color:
            rgba: self.base_color
        Line:
            rounded_rectangle: (2, 2, self.size[0]-4, self.size[1]-4, 20)
            width: 2           
''')


class PlayerWidget(RelativeLayout):
    base_color = ListProperty(RM_COLOR.get_rgba("light blue"))

    def __init__(self, cfg, mqtt, **kwargs):
        super(PlayerWidget, self).__init__(**kwargs)

        self.cfg = cfg
        self.mqtt = mqtt

        pass


class SmartPanelWidget(RelativeLayout):
    def __init__(self, mqtt, cfg, backlight_cb=None, **kwargs):
        super(SmartPanelWidget, self).__init__(**kwargs)

        self.backlight_cb = backlight_cb

        self.cfg = cfg
        
        self.mqtt = mqtt

        # Initialize the things
        self.things = []
        for sec in filter(lambda s: s.startswith("Thing:"),
                          self.cfg.sections()):
            section = sec[6:]
            posX = int(self.cfg.get("Thing:"+section, "posX"))
            posY = int(self.cfg.get("Thing:"+section, "posY"))

            t = Thing(section, self.cfg, self.mqtt, self, pos=(posX, posY))
            self.things.append(t)
            self.add_widget(t)
        
        self.IMGDIR="resources/nixie/"
        clock_pos = (0, 220)
        
        self.clock = ClockWidget(self.cfg, self.IMGDIR,
                                 pos=clock_pos, touch_cb=None)
        self.add_widget(self.clock)

        self.player = PlayerWidget(self.cfg, self.mqtt,
                                   pos=(330, 0))
        self.add_widget(self.player)

    def on_touch_down(self, touch):
        if self.backlight_cb is not None and self.backlight_cb():
            # Kill event when back-light is not active
            return True
        else:
            return super(SmartPanelWidget, self).on_touch_down(touch)


class SmartPanelApp(App):
    def __init__(self, mqtt, cfg, backlight_cb, **kwargs):
        super(SmartPanelApp, self).__init__(**kwargs)
        
        self.mqtt = mqtt
        self.cfg = cfg
        self.backlight_cb = backlight_cb
    
    
    def build(self):
        widget = SmartPanelWidget(self.mqtt, self.cfg, backlight_cb=self.backlight_cb,
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


def load_backlight_tmr(config):
    import importlib.util

    spec = importlib.util.find_spec('rpi_backlight')
    if spec is None:
        print("can't find the rpi_backlight module")
        return None
    else:
        # If you chose to perform the actual import ...
        bl = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bl)
        # Adding the module to sys.modules is optional.
        sys.modules['bl'] = bl

    timeout_s = config.get("Backlight", "timeout")
    brightness_s = config.get("Backlight", "brightness")
    back_tmr = BacklightTimer(bl,
                              timeout = int(timeout_s),
                              brightness = int(brightness_s))
    back_tmr.turn_on()
    back_tmr.start()

    return back_tmr.reset


if __name__ == '__main__':
    signal.signal(signal.SIGINT, sigint_handler)
    
    config = configparser.ConfigParser()
    config.read("smartpanel.cfg")

    fonts = ['./resources/FiraSans-Regular.ttf']
    Config.set('kivy', 'default_font', fonts)

    MQTT_HOST = config.get("MQTT", "host");
    MQTT_SW_TOPIC = config.get("MQTT", "topic")
    MQTT_TOPICS.append(MQTT_SW_TOPIC+"/#")

    client = mqtt.Client()
    client.on_connect = on_mqtt_connect
    client.connect(MQTT_HOST, 1883, 60)
#    client.subscribe(MQTT_SW_TOPIC+"/#")
    client.loop_start()

    app = SmartPanelApp(client, config, backlight_cb=load_backlight_tmr(config))
    app.run()
    
    client.loop_stop()


# kate: space-indent on; indent-width 4; mixedindent off; indent-mode python; indend-pasted-text false; remove-trailing-space off
