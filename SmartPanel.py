#!/usr/bin/python3

# SmartPanel - Smart Home control panel
# with Raspberry Pi and RPi Touch Screen

# Author: Stefan Haun <tux@netz39.de>
from builtins import staticmethod
from enum import Enum

from time import sleep
import signal
import sys
from datetime import datetime

import configparser

from threading import Timer

from kivy.app import App
from kivy.config import Config
from kivy.graphics import Color
from kivy.uix.relativelayout import RelativeLayout
from kivy.properties import ListProperty, StringProperty, NumericProperty
from kivy.lang import Builder

from kivy.clock import Clock

import paho.mqtt.client as mqtt


class RMColor:
    @staticmethod
    def get_rgba(name, alpha=1):
        # grey is fallback
        c = (77, 77, 76)

        if name == "off" or name == "black":
            c = (0, 0, 0)

        if name == "fresh" or name == "light blue":
            c = (0, 132, 176)

        if name == "hope" or name == "green":
            c = (0, 163, 86)

        if name == "glint" or name == "yellow":
            c = (249, 176, 0)

        if name == "beat" or name == "red":
            c = (228, 5, 41)

        if name == "tenacity" or name == "lilac":
            c = (68, 53, 126)

        if name == "base" or name == "dark blue":
            c = (24, 56, 107)

        # reboot (grey) is fallback from above

        return list(map(lambda x: x/256, c)) + [alpha]

    @staticmethod
    def get_color(name, alpha=1):
        c = RMColor.get_rgba(name, alpha)
        return Color(c[0], c[1], c[2], c[3], mode='rgba')


MQTT_TOPICS = []


def mqtt_add_topic_callback(mqttc, topic, cb):
    mqttc.subscribe(topic)
    MQTT_TOPICS.append(topic)
    
    mqttc.message_callback_add(topic, cb)


def on_mqtt_connect(mqttc, _userdata, _flags, rc):
    print("Connected with code %s" % rc)
    for topic in MQTT_TOPICS:
        mqttc.subscribe(topic)


class BacklightTimer:
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


class TasmotaState(Enum):
    UNKNOWN = 0
    OFF = 1
    ON = 2

    @staticmethod
    def for_message(msg):
        state = TasmotaState.UNKNOWN
        
        if msg == "ON":
            state = TasmotaState.ON
        if msg == "OFF":
            state = TasmotaState.OFF
        
        return state


class TasmotaDevice:
    def __init__(self, cfg, section, mqttc, on_state=None):
        self.cfg = cfg
        self.mqtt = mqttc
        self.on_state = on_state

        self.tp = self.cfg.get(section, "type")
        self.topic = self.cfg.get(section, "topic")

        self.state = TasmotaState.UNKNOWN

        self.mqtt_trigger = Clock.create_trigger(self._mqtt_toggle)

        mqtt_add_topic_callback(self.mqtt, self._get_state_topic(), self._on_pwr_state)

        # query the state
        self.mqtt.publish(self.topic + "/cmnd/Power1", "?", qos=2)

        # if this is active, toggle actions will be ignored
        self.throttled = False

    def toggle(self):
        if not self.throttled:
            self._set_state(TasmotaState.UNKNOWN)
            self.mqtt_trigger()

            self.throttled = True
            Clock.schedule_once(self._unthrottle, 0.5)

    def _unthrottle(self, *_largs):
        self.throttled = False

    def get_state(self):
        return self.state

    def _set_state(self, state):
        self.state = state
        if self.on_state is not None:
            self.on_state(self.state)

    def _get_state_topic(self):
        pwr = "/POWER1" if self.tp == "TASMOTA WS2812" else "/POWER"

        return self.topic + pwr

    def _mqtt_toggle(self, *_largs):
        self.mqtt.publish(self.topic + "/cmnd/Power1", "TOGGLE", qos=2)

        if self.tp == "TASMOTA WS2812":
            sleep(1)
            self.mqtt.publish(self.topic + "/cmnd/Power3", "TOGGLE", qos=2)

    def _on_pwr_state(self, _client, _userdata, message):
        topic = message.topic
        state = str(message.payload)[2:-1]
        self._set_state(TasmotaState.for_message(state))

        print("Power {s} for {t}".format(t=topic, s=state))


class StateColor:
    def __init__(self, cfg, section,
                 default_on="yellow", default_off="black", default_neutral="grey"):
        self.cfg = cfg

        self.color_on = self.cfg.get(section, "color_on", fallback=default_on)
        self.color_off = self.cfg.get(section, "color_off", fallback=default_off)
        self.color_neutral = self.cfg.get(section, "color_neutral", fallback=default_neutral)

        self.state_color = dict()
        self.state_color['text'] = [self.color_neutral, self.color_off, self.color_on]
        self.state_color['background'] = [self.color_off, self.color_on, self.color_off]
        self.state_color['border'] = [self.color_neutral, self.color_on, self.color_on]

    def get(self, state, el=None):
        if el in self.state_color.keys():
            colors = self.state_color[el]
        else:
            colors = [self.color_neutral, self.color_on, self.color_off]

        idx = 0
        if state == TasmotaState.ON:
            idx = 1
        if state == TasmotaState.OFF:
            idx = 2

        return RMColor.get_rgba(colors[idx], alpha=(1 if el != "background" else 0.8))


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
        RoundedRectangle:
            pos: (2, 2)
            size: (self.size[0] , self.size[1] - 4)
            radius: [20,]
        Color:
            rgba: self.border_color
        Line:
            rounded_rectangle: (2, 2, self.size[0], self.size[1] - 4, 20)
            width: 2

    Label:
        text: root.name
        color: root.text_color
        pos: (root.text_x, 0)
        text_size: (root.text_s_x, root.text_s_y)
        font_size: root.font_size
        halign: 'left'
        valign: 'middle'

''')


class Thing(RelativeLayout):
    border_color = ListProperty()
    state_color = ListProperty()
    text_color = ListProperty()
    name = StringProperty("<None>")

    def __init__(self, key, cfg, mqttc, widget, pos=(0, 0), **kwargs):
        self.key = key
        self.cfg = cfg
        self.widget = widget
        
        section = "Thing:"+self.key
        self.name = self.cfg.get(section, "name")

        self.tasmota = TasmotaDevice(cfg, section, mqttc, self.on_state)

        self.sc = StateColor(cfg, section)
        self.on_state(TasmotaState.UNKNOWN)

        super(Thing, self).__init__(pos=pos,
                                    size=(300, 80), size_hint=(None, None),
                                    **kwargs)

    def on_touch_down(self, touch):
        if self.collide_point(touch.pos[0], touch.pos[1]):
            self.tasmota.toggle()

            return True
        else:
            return super(Thing, self).on_touch_down(touch)

    def on_state(self, state):
        self.border_color = self.sc.get(state, el="border")
        self.text_color = self.sc.get(state, el="text")
        self.state_color = self.sc.get(state, el="background")


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

        self.tasmota = TasmotaDevice(cfg, section, mqttc, self.on_state)

        self.sc = StateColor(cfg, section,
                             default_on="light blue",
                             default_off="grey")
        self.on_state(TasmotaState.UNKNOWN)

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
    base_color = ListProperty()
    clk_image_src_0 = StringProperty("")
    clk_image_src_1 = StringProperty("")
    clk_image_src_2 = StringProperty("")
    clk_image_src_3 = StringProperty("")
    alarm_color = ListProperty()
    alarm_digit_alpha = NumericProperty(0)
    alarm_image_src_0 = StringProperty("")
    alarm_image_src_1 = StringProperty("")
    alarm_image_src_2 = StringProperty("")
    alarm_image_src_3 = StringProperty("")
    current_date = StringProperty("    -  -  ")

    def __init__(self, cfg, basepath, touch_cb=None, **kwargs):
        self.base_color = RMColor.get_rgba("yellow")
        self.alarm_color = RMColor.get_rgba("reboot")

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
            self.alarm_color = RMColor.get_rgba("reboot")
            self.alarm_image_src_0 = self.basepath + "off.png"
            self.alarm_image_src_1 = self.basepath + "off.png"
            self.alarm_image_src_2 = self.basepath + "off.png"
            self.alarm_image_src_3 = self.basepath + "off.png"
        else:
            self.alarm_digit_alpha = 1
            self.alarm_color = RMColor.get_rgba("yellow")
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
        mqtt_add_topic_callback(self.mqtt,
                                self.topic_base+"/song/#",
                                self.on_song_state)
        mqtt_add_topic_callback(self.mqtt,
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


def load_backlight_tmr(cfg):
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

    timeout_s = cfg.get("Backlight", "timeout")
    brightness_s = cfg.get("Backlight", "brightness")
    back_tmr = BacklightTimer(bl,
                              timeout=int(timeout_s),
                              brightness=int(brightness_s))
    back_tmr.turn_on()
    back_tmr.start()

    return back_tmr.reset


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

    if "MQTT" not in config.keys():
        print("Missing MQTT section in configuration. See template for an example.")
        sys.exit(1)
    
    MQTT_HOST = config.get("MQTT", "host")
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
