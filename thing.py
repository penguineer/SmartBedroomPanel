from kivy.lang import Builder
from kivy.uix.relativelayout import RelativeLayout
from kivy.properties import ListProperty, StringProperty, ObjectProperty

import color
from color import StateColor
from tasmota import TasmotaDevice


Builder.load_string('''
<Thing>:
    size: 300, 80
    size_hint: None, None
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
    state_color = ListProperty(color.RMColor.get_rgba("reboot"))
    name = StringProperty("<None>")

    cfg = ObjectProperty(None)
    cfg_name = StringProperty(None)
    mqtt = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(Thing, self).__init__(**kwargs)

        self.sc = None
        self.tasmota = None

        self._setup()

    def _setup(self):
        if self.cfg is None or self.cfg_name is None or self.mqtt is None:
            return

        pos_x = int(self.cfg.get(self.cfg_name, "posX"))
        pos_y = int(self.cfg.get(self.cfg_name, "posY"))
        self.pos = (pos_x, pos_y)

        self.name = self.cfg.get(self.cfg_name, "name")
        self.sc = StateColor(self.cfg, self.cfg_name)

        self.tasmota = TasmotaDevice(self.cfg, self.cfg_name, self.mqtt, on_state=self.on_state)
        self.on_state(self.tasmota)

    def on_touch_down(self, touch):
        if self.collide_point(touch.pos[0], touch.pos[1]):
            if self.tasmota.get_online_state().online():
                self.tasmota.toggle()

            return True
        else:
            return super(Thing, self).on_touch_down(touch)

    def on_state(self, state):
        self.state_color = self.sc.get(state) if self.sc is not None else color.RMColor.get_rgba("reboot")


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
