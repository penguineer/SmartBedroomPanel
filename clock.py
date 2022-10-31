from datetime import datetime

from kivy.lang import Builder
from kivy.uix.relativelayout import RelativeLayout
from kivy.properties import ListProperty, StringProperty, NumericProperty, ObjectProperty
from kivy.clock import Clock

from color import RMColor

Builder.load_string('''
<ClockWidget>:
    size: (300, 260)
    size_hint: (None, None)
    orientation: 'horizontal'
    spacing: self.size[0] * 0.01  

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
    base_color = ListProperty(RMColor.get_rgba("yellow"))
    clk_image_src_0 = StringProperty("")
    clk_image_src_1 = StringProperty("")
    clk_image_src_2 = StringProperty("")
    clk_image_src_3 = StringProperty("")
    alarm = StringProperty(None, allownone=True)
    alarm_color = ListProperty(RMColor.get_rgba("reboot"))
    alarm_digit_alpha = NumericProperty(0)
    alarm_image_src_0 = StringProperty("")
    alarm_image_src_1 = StringProperty("")
    alarm_image_src_2 = StringProperty("")
    alarm_image_src_3 = StringProperty("")
    current_date = StringProperty("    -  -  ")
    basepath = StringProperty("")
    touch_cb = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs):
        super(ClockWidget, self).__init__(**kwargs)

        Clock.schedule_interval(lambda dt: self.set_clock(), 1)

    def set_alarm(self, alarm):
        """Alarm in the form of 'HH:MM'"""
        self.alarm = alarm

    def set_clock(self):
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

    def on_basepath(self, _instance, _value):
        self.set_clock()
