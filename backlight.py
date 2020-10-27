from threading import Timer
import sys


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
