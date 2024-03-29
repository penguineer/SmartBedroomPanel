"""Display data about the room environment"""

from kivy.lang import Builder
from kivy.properties import StringProperty, ListProperty, ObjectProperty
from kivy.uix.relativelayout import RelativeLayout

from color import RMColor

Builder.load_string('''
# Define your background color Template
<BackgroundColor@Widget>
    background_color: 1, 1, 1, 1
    canvas.before:
        Color:
            rgba: root.background_color
        Rectangle:
            size: self.size
            pos: self.pos
# Now you can simply Mix the `BackgroundColor` class with almost
# any other widget... to give it a background.
<BackgroundLabel@Label+BackgroundColor>
    background_color: 0, 0, 0, 0
    # Default the background color for this label
    # to r 0, g 0, b 0, a 0
    
<EnvironmentWidget>:
    size: (340, 100)
    size_hint: (None, None)

    canvas:
        # Border rect
        Color:
            rgba: root.base_color
        Line:
            rounded_rectangle: (2, 2, self.size[0]-4, self.size[1]-4, 20)
            width: 2 

    BoxLayout:
        orientation: 'vertical'
        size: (240, 240)
        padding: 10
        spacing: 10

        BoxLayout:
            orientation: 'horizontal'
            spacing: 10
            size_hint: (1, 1)
            
            Image:
                source: 'resources/temperature.png'
                color: root.temperature_label_color
                size_hint: (None, 0.8)
                size: (64, 64)            
    
            Label:
                text: '--' if root.temperature is None else root.temperature 
                color: root.temperature_value_color
                font_size: 40
                font_name: 'resources/FiraMono-Regular.ttf'    
    
            Label:
                text: '°C' 
                color: root.temperature_value_color
                font_size: 24
                halign: 'center'
                valign: 'top'
                size: (48, 48)
                text_size: self.size
                size_hint: (None, 1)
    
            Label:
                size_hint: (0.2, None)
    
            Image:
                source: 'resources/humidity.png'
                color: root.humidity_label_color
                size_hint: (None, 0.8)
                size: (64, 64)            
    
            Label:
                text: '--' if root.humidity is None else root.humidity 
                color: root.humidity_value_color
                font_size: 40
                font_name: 'resources/FiraMono-Regular.ttf'    
    
            Label:
                text: '%' 
                color: root.humidity_value_color
                font_size: 24
                halign: 'center'
                valign: 'top'
                size: (48, 48)
                text_size: self.size
                size_hint: (None, 1)
            
        BoxLayout:
            orientation: 'horizontal'
            size_hint: (1, 0.2)
            spacing: 2
            
            Label:
                size_hint: (0.2, 1)
            
            BackgroundLabel:
                background_color: root.quality_color_1

            BackgroundLabel:
                background_color: root.quality_color_2

            BackgroundLabel:
                background_color: root.quality_color_3

            BackgroundLabel:
                background_color: root.quality_color_4

            BackgroundLabel:
                background_color: root.quality_color_5

            Label:
                size_hint: (0.2, 1)

''')


class EnvironmentWidget(RelativeLayout):
    base_color = ListProperty(RMColor.get_rgba("base"))
    temperature_value_color = ListProperty()
    temperature_label_color = ListProperty()
    humidity_value_color = ListProperty()
    humidity_label_color = ListProperty()
    quality_color_1 = ListProperty(RMColor.get_rgba("reboot"))
    quality_color_2 = ListProperty(RMColor.get_rgba("reboot"))
    quality_color_3 = ListProperty(RMColor.get_rgba("reboot"))
    quality_color_4 = ListProperty(RMColor.get_rgba("reboot"))
    quality_color_5 = ListProperty(RMColor.get_rgba("reboot"))

    VALUE_COLOR = "fresh"
    LABEL_COLOR = "base"
    QUALITY_COLOR = ["green", "green", "yellow", "yellow", "red"]

    temperature = StringProperty("--")
    humidity = StringProperty("--")

    cfg = ObjectProperty(None)
    mqtt = ObjectProperty(None)

    def __init__(self, **kwargs):
        self._set_temperature(None)
        self._set_humidity(None)
        super(EnvironmentWidget, self).__init__(**kwargs)

    def on_cfg(self, _instance, _value):
        self.on_mqtt(_instance, _value)

    def on_mqtt(self, _instance, _value):
        if not self.cfg or not self.mqtt:
            return

        self.mqtt.subscribe(self.cfg.get('Environment', "temperature"),
                            self._on_temperature_update)
        self.mqtt.subscribe(self.cfg.get('Environment', "humidity"),
                            self._on_humidity_update)
        self.mqtt.subscribe(self.cfg.get('Environment', "air_quality"),
                            self._on_air_quality_update)

    def _on_temperature_update(self, _client, _userdata, message):
        payload = message.payload.decode("utf-8")
        self._set_temperature(payload)

    def _on_humidity_update(self, _client, _userdata, message):
        payload = message.payload.decode("utf-8")
        self._set_humidity(payload)

    def _on_air_quality_update(self, _client, _userdata, message):
        payload = message.payload.decode("utf-8")
        self._set_air_quality(payload)

    def _set_temperature(self, temperature):
        if temperature is None:
            self.temperature = "--"
            self.temperature_value_color = RMColor.get_rgba("reboot")
            self.temperature_label_color = RMColor.get_rgba("reboot")
        else:
            t = round(float(temperature))
            self.temperature = "{:02d}".format(t)
            self.temperature_value_color = RMColor.get_rgba(EnvironmentWidget.VALUE_COLOR)
            self.temperature_label_color = RMColor.get_rgba(EnvironmentWidget.LABEL_COLOR)

    def _set_humidity(self, humidity):
        if humidity is None:
            self.humidity = "--"
            self.humidity_value_color = RMColor.get_rgba("reboot")
            self.humidity_label_color = RMColor.get_rgba("reboot")
        else:
            h = round(float(humidity))
            self.humidity = "{:02d}".format(h)
            self.humidity_value_color = RMColor.get_rgba(EnvironmentWidget.VALUE_COLOR)
            self.humidity_label_color = RMColor.get_rgba(EnvironmentWidget.LABEL_COLOR)

    def _set_air_quality(self, air_quality):
        q = float(air_quality)
        off = RMColor.get_rgba("off")
        self.quality_color_1 = off if q < 1 else RMColor.get_rgba(EnvironmentWidget.QUALITY_COLOR[0])
        self.quality_color_2 = off if q < 2 else RMColor.get_rgba(EnvironmentWidget.QUALITY_COLOR[1])
        self.quality_color_3 = off if q < 3 else RMColor.get_rgba(EnvironmentWidget.QUALITY_COLOR[2])
        self.quality_color_4 = off if q < 4 else RMColor.get_rgba(EnvironmentWidget.QUALITY_COLOR[3])
        self.quality_color_5 = off if q < 5 else RMColor.get_rgba(EnvironmentWidget.QUALITY_COLOR[4])
