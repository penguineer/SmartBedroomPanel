#!/usr/bin/python3

# SmartPanel - Smart Home control panel
# with Raspberry Pi and RPi Touch Screen

# Author: Stefan Haun <tux@netz39.de>
import signal
import sys

import configparser

from kivy.app import App
from kivy.config import Config
from kivy.uix.relativelayout import RelativeLayout
from kivy.properties import ListProperty, StringProperty
from kivy.lang import Builder


import mqtt
from color import StateColor
import backlight
from tasmota import TasmotaDevice
from clock import ClockWidget
from player import PlayerWidget, FavButtonWidget

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
    state_color = ListProperty()
    name = StringProperty("<None>")

    def __init__(self, key, cfg, mqttc, widget, pos=(0, 0), **kwargs):
        self.key = key
        self.cfg = cfg
        self.widget = widget
        
        section = "Thing:"+self.key
        self.name = self.cfg.get(section, "name")

        self.tasmota = TasmotaDevice(cfg, section, mqttc, on_state=self.on_state)

        self.sc = StateColor(cfg, section)
        self.on_state(self.tasmota)

        super(Thing, self).__init__(pos=pos,
                                    size=(300, 80), size_hint=(None, None),
                                    **kwargs)

    def on_touch_down(self, touch):
        if self.collide_point(touch.pos[0], touch.pos[1]):
            if self.tasmota.get_online_state().online():
                self.tasmota.toggle()

            return True
        else:
            return super(Thing, self).on_touch_down(touch)

    def on_state(self, state):
        self.state_color = self.sc.get(state)


Builder.load_string('''
<WifiRepeater>:
    size: (100, 100)
    size_hint: (None, None)

    canvas:
        # Border rect
        Color:
            rgba: self.state_color
        Line:
            rounded_rectangle: (2, 2, self.size[0]-4, self.size[1]-4, 20)
            width: 2 

    # Button
    Image:
        source: 'resources/wifi_repeater.png'
        size: (64, 64)
        size_hint: (None, None)
        pos: (18, 18)
        color: root.state_color
''')


class WifiRepeater(RelativeLayout):
    state_color = ListProperty()

    def __init__(self, cfg, mqttc, pos=(0, 0), **kwargs):
        self.cfg = cfg

        section = "WifiRepeater"

        self.tasmota = TasmotaDevice(cfg, section, mqttc, on_state=self.on_state)

        self.sc = StateColor(cfg, section,
                             default_on="light blue",
                             default_off="grey")
        self.on_state(self.tasmota)

        super(WifiRepeater, self).__init__(pos=pos,
                                           **kwargs)

    def on_touch_down(self, touch):
        if self.collide_point(touch.pos[0], touch.pos[1]):
            self.tasmota.toggle()

            return True
        else:
            return super(WifiRepeater, self).on_touch_down(touch)

    def on_state(self, state):
        self.state_color = self.sc.get(state)


class SmartPanelWidget(RelativeLayout):
    def __init__(self, mqttc, cfg, backlight_cb=None, **kwargs):
        super(SmartPanelWidget, self).__init__(**kwargs)

        self.backlight_cb = backlight_cb

        self.cfg = cfg
        
        self.mqtt = mqttc

        # Initialize the things
        self.things = []
        for sec in filter(lambda s: s.startswith("Thing:"),
                          self.cfg.sections()):
            section = sec[6:]
            pos_x = int(self.cfg.get("Thing:"+section, "posX"))
            pos_y = int(self.cfg.get("Thing:"+section, "posY"))

            t = Thing(section, self.cfg, self.mqtt, self, pos=(pos_x, pos_y))
            self.things.append(t)
            self.add_widget(t)
        
        self.IMGDIR = "resources/nixie/"
        clock_pos = (0, 220)
        
        self.clock = ClockWidget(self.cfg, self.IMGDIR,
                                 pos=clock_pos, touch_cb=None)
        self.add_widget(self.clock)

        self.player = PlayerWidget(self.cfg, self.mqtt,
                                   pos=(330, 0))
        self.add_widget(self.player)

        self.fav = FavButtonWidget(self.cfg, self.mqtt,
                                   pos=(700, 220))
        self.add_widget(self.fav)

        if "WifiRepeater" in self.cfg.sections():
            self.wifi_repeater = WifiRepeater(self.cfg, self.mqtt,
                                              pos=(700, 380))
            self.add_widget(self.wifi_repeater)

    def on_touch_down(self, touch):
        if self.backlight_cb is not None and self.backlight_cb():
            # Kill event when back-light is not active
            return True
        else:
            return super(SmartPanelWidget, self).on_touch_down(touch)


class SmartPanelApp(App):
    def __init__(self, mqttc, cfg, backlight_cb, **kwargs):
        super(SmartPanelApp, self).__init__(**kwargs)
        
        self.mqtt = mqttc
        self.cfg = cfg
        self.backlight_cb = backlight_cb

    def build(self):
        widget = SmartPanelWidget(self.mqtt, self.cfg, backlight_cb=self.backlight_cb,
                                  size=(800, 480))
        
        return widget


running = True


def sigint_handler(_signal, _frame):
    global running
    
    if running:
        print("SIGINT received. Stopping the queue.")
        running = False
    else:
        print("Receiving SIGINT the second time. Exit.")
        sys.exit(0)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, sigint_handler)
    
    config = configparser.ConfigParser()
    config.read("smartpanel.cfg")

    Config.set('kivy', 'default_font', [
        ' FiraSans-Regular',
        './resources/FiraSans-Regular.ttf',
        './resources/FiraSans-Regular.ttf',
        './resources/FiraSans-Regular.ttf',
        './resources/FiraSans-Regular.ttf'
    ])

    client = mqtt.create_client(config)

    app = SmartPanelApp(client, config, backlight_cb=backlight.load_backlight_tmr(config))
    app.run()
    
    client.loop_stop()
