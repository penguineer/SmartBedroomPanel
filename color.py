from kivy.graphics import Color


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


class StateColor:
    def __init__(self, cfg, section,
                 default_on="green", default_off="red", default_neutral="grey"):
        self.cfg = cfg

        self.color_on = self.cfg.get(section, "color_on", fallback=default_on)
        self.color_off = self.cfg.get(section, "color_off", fallback=default_off)
        self.color_neutral = self.cfg.get(section, "color_neutral", fallback=default_neutral)

    def get(self, state):
        _pwr_state = state.get_pwr_state()
        if not _pwr_state.observation_match():
            col = RMColor.get_rgba(self.color_neutral)
        else:
            col = RMColor.get_rgba(self.color_on if _pwr_state.observed() else self.color_off)

        return col
