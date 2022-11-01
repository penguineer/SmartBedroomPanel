from kivy.lang import Builder
from kivy.properties import StringProperty, ObjectProperty, ColorProperty
from kivy.uix.button import Button

from color import RMColor

Builder.load_string("""
<ShellyButton>:
    size: 100, 150
    size_hint: None, None
    background_normal: ''
    background_down: ''
    background_color: 0, 0, 0, 1
   
    RelativeLayout:
        pos: self.parent.pos
        size: self.parent.size
        
        Image:
            source: root.icon_path
            x: 2
            y: 24 
            size: 96, 96
            color: root.state_color
            
        Label:
            text: root.label_text
            color: root.state_color
            size: self.texture_size
            pos:  0, -50
            font_size: 24
            halign: 'center'
            valign: 'middle'
            
        RelativeLayout:
            canvas:
                Color:
                    rgba: root.state_color
                Line:
                    rounded_rectangle: (2, 2, self.size[0], self.size[1] - 4, 20)
                    width: 2
""")


class ShellyButton(Button):
    icon_path = StringProperty("")
    state_color = ColorProperty(RMColor.get_rgba("reboot"))
    label_text = StringProperty("--")

    cfg = ObjectProperty(None)
    cfg_name = StringProperty(None)
    mqtt = ObjectProperty(None)

    COLOR_MAP = {
        "unknown": "reboot",
        "on": "green",
        "off": "red"
    }

    def __init__(self, **kwargs):
        super(Button, self).__init__(**kwargs, text="")

        self.bind(cfg=self._setup)
        self.bind(cfg_name=self._setup)
        self.bind(mqtt=self._setup)

        self._setup(self, None)

    def on_press(self):
        if self.cfg is None or self.mqtt is None or self.cfg_name is None:
            return

        topic_prefix = self.cfg.get(self.cfg_name, "topic")
        self.mqtt.publish(topic_prefix+"/relay/0/command", "toggle")
        self.label_text = ""

    def _setup(self, _instance, _value):
        if self.cfg is None or self.mqtt is None or self.cfg_name is None:
            return

        pos_x = int(self.cfg.get(self.cfg_name, "posX"))
        pos_y = int(self.cfg.get(self.cfg_name, "posY"))
        self.pos = (pos_x, pos_y)

        self.icon_path = self.cfg.get(self.cfg_name, "icon")

        topic = self.cfg.get(self.cfg_name, "topic")

        self.mqtt.subscribe(topic+"/relay/0", self._on_mqtt)
        self.mqtt.subscribe(topic+"/relay/0/power", self._on_mqtt)

    def _on_mqtt(self, _client, _userdata, message):
        if self.cfg is None or self.mqtt is None or self.cfg_name is None:
            return

        topic = message.topic
        payload = message.payload.decode("utf-8")

        topic_prefix = self.cfg.get(self.cfg_name, "topic")
        if self.mqtt.topic_matches_sub(topic_prefix+"/relay/0", topic):
            self.state_color = RMColor.get_rgba(ShellyButton.COLOR_MAP.get(payload, "unknown"))

        if self.mqtt.topic_matches_sub(topic_prefix+"/relay/0/power", topic):
            self.label_text = "{:d} W".format(int(float(payload)))
