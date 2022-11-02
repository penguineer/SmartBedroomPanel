#!/usr/bin/python3
import asyncio
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

from shelly import ShellyButton
from thing import Thing, WifiRepeater

Builder.load_string('''
#:import BacklightControl backlight.BacklightControl
#:import MqttClient mqtt.MqttClient
#:import ClockWidget clock.ClockWidget
#:import EnvironmentWidget environment.EnvironmentWidget
#:import FavButtonWidget player.FavButtonWidget
#:import PlayerWidget player.PlayerWidget
#:import ShellyButton shelly.ShellyButton

<SmartPanelWidget>:
    BacklightControl:
        id: backlight
        cfg: root.cfg
        power: True        

    MqttClient:
        id: mqtt
        cfg: root.cfg
        pos: [800-32, 460-48]

    ClockWidget:
        pos: [0, 200]
        cfg: root.cfg
        basepath: root.IMGDIR
        touch_cb: None
        
    EnvironmentWidget:
        pos: [330, 200]
        cfg: root.cfg
        mqtt: root.mqtt
        
    PlayerWidget:        
        pos: [330, 0]
        cfg: root.cfg
        mqtt: root.mqtt

    FavButtonWidget:        
        pos: [700, 200]
        cfg: root.cfg
        mqtt: root.mqtt
''')


class SmartPanelWidget(RelativeLayout):
    cfg = ObjectProperty()
    mqtt = ObjectProperty()

    IMGDIR = StringProperty("resources/nixie/")

    def __init__(self, cfg, **kwargs):
        super(SmartPanelWidget, self).__init__(**kwargs)

        self.cfg = cfg
        
        self.mqtt = self.ids.mqtt

        # Initialize the things
        for sec in filter(lambda s: s.startswith("Thing:"),
                          self.cfg.sections()):
            t = Thing(cfg_name=sec,
                      cfg=self.cfg,
                      mqtt=self.mqtt)
            self.bind(cfg=t.setter('cfg'))
            self.bind(mqtt=t.setter('mqtt'))
            self.add_widget(t)

        for sec in filter(lambda s: s.startswith("Shelly"),
                          self.cfg.sections()):
            sb = ShellyButton(cfg_name=sec,
                              cfg=self.cfg,
                              mqtt=self.mqtt)
            self.bind(cfg=sb.setter('cfg'))
            self.bind(mqtt=sb.setter('mqtt'))
            self.add_widget(sb)

        if "WifiRepeater" in self.cfg.sections():
            self.wifi_repeater = WifiRepeater(self.cfg, self.mqtt,
                                              pos=(700, 380))
            self.add_widget(self.wifi_repeater)

    def on_touch_down(self, touch):
        if self.ids.backlight is not None and not self.ids.backlight.power:
            block = not self.ids.backlight.power
            # Switch on
            self.ids.backlight.power = True
            # Kill event when back-light is not active
            if block:
                return True

        return super(SmartPanelWidget, self).on_touch_down(touch)


class SmartPanelApp(App):
    def __init__(self, cfg, **kwargs):
        super(SmartPanelApp, self).__init__(**kwargs)
        
        self.cfg = cfg

    def build(self):
        widget = SmartPanelWidget(self.cfg,
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


async def main():
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

    app = SmartPanelApp(config)
    await app.async_run()


if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
