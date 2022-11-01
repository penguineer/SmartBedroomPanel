#!/usr/bin/python3

# SmartPanel - Smart Home control panel
# with Raspberry Pi and RPi Touch Screen

# Author: Stefan Haun <tux@netz39.de>
import signal
import sys

import configparser

from kivy.app import App
from kivy.config import Config
from kivy.lang import Builder
from kivy.properties import ObjectProperty, StringProperty
from kivy.uix.relativelayout import RelativeLayout

import mqtt
import backlight
from thing import Thing, WifiRepeater

Builder.load_string('''
#:import ClockWidget clock.ClockWidget
#:import EnvironmentWidget environment.EnvironmentWidget
#:import FavButtonWidget player.FavButtonWidget
#:import PlayerWidget player.PlayerWidget

<SmartPanelWidget>:
    ClockWidget:
        pos: [0, 200]
        cfg: root.cfg
        basepath: root.IMGDIR
        touch_cb: None
        
    EnvironmentWidget:
        pos: [330, 220]
        cfg: root.cfg
        mqtt: root.mqtt
        
    PlayerWidget:        
        pos: [330, 0]
        cfg: root.cfg
        mqtt: root.mqtt

    FavButtonWidget:        
        pos: [700, 220]
        cfg: root.cfg
        mqtt: root.mqtt
''')


class SmartPanelWidget(RelativeLayout):
    backlight_cb = ObjectProperty()
    cfg = ObjectProperty()
    mqtt = ObjectProperty()

    IMGDIR = StringProperty("resources/nixie/")

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


def main():
    signal.signal(signal.SIGINT, sigint_handler)

    Config.set('kivy', 'default_font', [
        ' FiraSans-Regular',
        './resources/FiraSans-Regular.ttf',
        './resources/FiraSans-Regular.ttf',
        './resources/FiraSans-Regular.ttf',
        './resources/FiraSans-Regular.ttf'
    ])

    config = configparser.ConfigParser()
    config.read("smartpanel.cfg")

    client = mqtt.create_client(config)

    app = SmartPanelApp(client, config, backlight_cb=backlight.load_backlight_tmr(config))
    app.run()

    client.loop_stop()


if __name__ == '__main__':
    main()
