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

from kivy.clock import Clock

import mqtt
from color import RMColor, StateColor
import backlight
from tasmota import TasmotaDevice
from clock import ClockWidget


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


Builder.load_string('''
<PlayerWidget>:
    size: (470, 190)
    size_hint: (None, None)

    canvas:
        # Border rect
        Color:
            rgba: self.base_color
        Line:
            rounded_rectangle: (2, 2, self.size[0]-4, self.size[1]-4, 20)
            width: 2 
        
        # Divider 
        Color:
            rgba: root.meta_color
        Line:
            points: [10, 110, 460, 110]
            width: 1.5
            cap: 'none'

    # Song Artist
    Image:
        source: 'resources/song_artist.png'
        size: (24, 24)
        size_hint: (None, None)
        pos: (10, root.size[1]-36)
        color: root.meta_color

    Label:
        text: root.song_artist
        font_size: 20
        size: (210, 24)
        text_size: self.size
        pos: (40, root.size[1]-36)
        size_hint: (None, None)
        color: root.meta_color
        shorten: True

    # Song Album
    Image:
        source: 'resources/song_album.png'
        size: (24, 24)
        size_hint: (None, None)
        pos: (255, root.size[1]-36)
        color: root.meta_color

    Label:
        text: root.song_album
        font_size: 20
        size: (180, 24)
        text_size: self.size
        pos: (285, root.size[1]-36)
        size_hint: (None, None)
        color: root.meta_color
        shorten: True

    # Song Title
    Image:
        source: 'resources/song_title.png'
        size: (24, 24)
        size_hint: (None, None)
        pos: (10, root.size[1]-69)
        color: root.meta_color

    Label:
        text: root.song_title
        font_size: 20
        size: (415, 24)
        text_size: self.size
        pos: (40, root.size[1]-69)
        size_hint: (None, None)
        color: root.meta_color
        shorten: True

    # Controls
    Image:
        source: root.player_control_source
        size:  (96, 96)
        size_hint: (None, None)
        pos: (369, 7)
        color: root.ctrl_color

    Image:
        source: 'resources/song_forward.png'
        size:  (64, 64)
        size_hint: (None, None)
        pos: (300, 13)
        color: root.ctrl_color

    # Volume control
    Image:
        source: 'resources/volume_minus.png'
        size:  (64, 64)
        size_hint: (None, None)
        pos: (10, 10)
        color: root.ctrl_color

    Label:
        text: root.volume_text
        font_size: 36
        size: (103, 60)
        text_size: self.size
        pos: (82, 10)
        size_hint: (None, None)
        color: root.ctrl_color
        halign: 'center'
        valign: 'middle'
        bold: True

    Image:
        source: 'resources/volume_plus.png'
        size:  (64, 64)
        size_hint: (None, None)
        pos: (195, 10)
        color: root.ctrl_color

''')


class PlayerWidget(RelativeLayout):
    base_color = ListProperty()
    meta_color = ListProperty()
    ctrl_color = ListProperty()
    song_artist = StringProperty("<Artist>")
    song_album = StringProperty("<Album>")
    song_title = StringProperty("<Title>")
    player_control_source = StringProperty("")
    volume_text = StringProperty("100")

    def __init__(self, cfg, mqttc, **kwargs):
        self.base_color = RMColor.get_rgba("light blue")
        self.meta_color = RMColor.get_rgba("reboot")
        self.ctrl_color = RMColor.get_rgba("reboot")

        super(PlayerWidget, self).__init__(**kwargs)

        self.cfg = cfg
        self.mqtt = mqttc

        self.metadata = dict()
        self._set_metadata('state', 'stop')
        self._set_metadata('single', '0')
        self._set_metadata('volume', 0)
        self._set_metadata('artist', "<Artist>")
        self._set_metadata('album', "<Album>")
        self._set_metadata('title', "<Title>")

        self.volume_levels = [0, 61, 74, 78, 83, 87, 91, 94, 97, 100]

        # True if the last action has resulted in a report back
        self.state_is_reported = False

        self.topic_base = self.cfg.get('Player', "topic")
        mqtt.add_topic_callback(self.mqtt,
                                self.topic_base+"/song/#",
                                self.on_song_state)
        mqtt.add_topic_callback(self.mqtt,
                                self.topic_base+"/player/#",
                                self.on_player_state)

        Clock.schedule_interval(self._player_ui_state, 0.2)

        # query the state
        self.mqtt.publish(self.topic_base+"/CMD", "query", qos=2)

    def _set_metadata(self, key, value):
        self.metadata[key] = value
        self.state_is_reported = True

    def _get_metadata(self, key, default=None):
        return self.metadata[key] if key in self.metadata.keys() else default

    def on_song_state(self, _client, _userdata, message):
        topic = message.topic
        payload = message.payload.decode("utf-8")

        if mqtt.topic_matches_sub(self.topic_base+"/song/artist", topic):
            self._set_metadata('artist', payload)

        if mqtt.topic_matches_sub(self.topic_base+"/song/album", topic):
            self._set_metadata('album', payload)

        if mqtt.topic_matches_sub(self.topic_base+"/song/title", topic):
            self._set_metadata('title', payload)

    def on_player_state(self, _client, _userdata, message):
        topic = message.topic
        payload = message.payload.decode("utf-8")

        if mqtt.topic_matches_sub(self.topic_base+"/player/state", topic):
            self._set_metadata('state', payload)

        if mqtt.topic_matches_sub(self.topic_base+"/player/single", topic):
            self._set_metadata('single', payload)

        if mqtt.topic_matches_sub(self.topic_base+"/player/volume", topic):
            self._set_metadata('volume', int(payload))

    def _player_ui_state(self, _dt):
        self.song_artist = self._get_metadata('artist')
        self.song_album = self._get_metadata('album')
        self.song_title = self._get_metadata('title')

        self.meta_color = RMColor.get_rgba(
            "light blue" if self._get_metadata('state') == "play" else "reboot")

        if not self._get_metadata('state') == "play":
            self.player_control_source = "resources/song_play.png"
        else:
            if self._get_metadata('single') == "0":
                self.player_control_source = "resources/song_stopnext.png"
            else:
                self.player_control_source = "resources/song_stop.png"

        if self.state_is_reported:
            self.ctrl_color = RMColor.get_rgba("light blue")
        else:
            self.ctrl_color = RMColor.get_rgba("reboot")

        self.volume_text = str(self._get_metadata('volume', '---'))

    def on_touch_down(self, touch):
        if self.collide_point(touch.pos[0], touch.pos[1]):
            tp = self.to_local(touch.pos[0], touch.pos[1])

            def in_circle_bounds(center, radius, pt):
                return (center[0]-pt[0])**2 + (center[1]-pt[1])**2 < radius**2

            # check for main control
            if in_circle_bounds([417, 56], 48, tp):
                self.on_main_control()

            # check for forward control
            if in_circle_bounds([332, 45], 32, tp):
                self.on_forward_control()

            # check for volume down
            if in_circle_bounds([47, 45], 32, tp):
                self.on_adjust_volume(up=False)

            # check for volume up
            if in_circle_bounds([232, 45], 32, tp):
                self.on_adjust_volume(up=True)

            return True
        else:
            return super(PlayerWidget, self).on_touch_down(touch)

    def on_main_control(self):
        if not self._get_metadata('state') == "play":
            cmd = "play"
        else:
            if self._get_metadata('single') == "0":
                cmd = "stop after"
            else:
                cmd = "pause"

        self.mqtt.publish(self.topic_base+"/CMD", cmd, qos=2)

        self.state_is_reported = False

    def on_forward_control(self):
        self.mqtt.publish(self.topic_base+"/CMD", "next", qos=2)
        # call "play" so reset "single play" status
        self.mqtt.publish(self.topic_base+"/CMD", "play", qos=2)

        self.state_is_reported = False

    def on_adjust_volume(self, up):
        vol = min(self.volume_levels, key=lambda x: abs(x - self._get_metadata('volume', 0)))
        idx = self.volume_levels.index(vol)

        idx += 1 if up else -1
        idx = max(idx, 0)
        idx = min(idx, len(self.volume_levels)-1)

        self.mqtt.publish(self.topic_base+"/CMD/volume", str(self.volume_levels[idx]), qos=2)

        self.state_is_reported = False


Builder.load_string('''
<FavButtonWidget>:
    size: (100, 100)
    size_hint: (None, None)

    canvas:
        # Border rect
        Color:
            rgba: self.base_color
        Line:
            rounded_rectangle: (2, 2, self.size[0]-4, self.size[1]-4, 20)
            width: 2 

    # Button
    Image:
        source: 'resources/hugging-face.png'
        size: (64, 64)
        size_hint: (None, None)
        pos: (18, 18)
        color: root.meta_color
''')


class FavButtonWidget(RelativeLayout):
    base_color = ListProperty()
    meta_color = ListProperty()

    def __init__(self, cfg, mqttc, **kwargs):
        self.base_color = RMColor.get_rgba("light blue")
        self.meta_color = RMColor.get_rgba("light blue")

        super(FavButtonWidget, self).__init__(**kwargs)

        self.cfg = cfg
        self.mqtt = mqttc

        # True if the last action has resulted in a report back
        self.state_is_reported = False

        self.topic_base = self.cfg.get('Player', "topic")

    def on_touch_down(self, touch):
        if self.collide_point(touch.pos[0], touch.pos[1]):
            tp = self.to_local(touch.pos[0], touch.pos[1])

            def in_circle_bounds(center, radius, pt):
                return (center[0]-pt[0])**2 + (center[1]-pt[1])**2 < radius**2

            # check for main control
            if in_circle_bounds([50, 50], 32, tp):
                self.on_play_fav()

            return True
        else:
            return super(FavButtonWidget, self).on_touch_down(touch)

    def on_play_fav(self):
        self.mqtt.publish(self.topic_base+"/CMD", "fav", qos=2)


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
