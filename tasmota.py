from kivy.clock import Clock
from time import sleep

import mqtt


class TasmotaOnlineState(object):
    def __init__(self, cb=None):
        self._online = None
        self._cb = cb

    def handle_message(self, message):
        topic = message.topic

        _old = self._online

        if message.payload == b'Online':
            self._online = True
        elif message.payload == b'Offline':
            self._online = False
        else:
            self._online = None
            print("Unknown message for topic {}: {}".format(topic, message.payload))

        if self._online != _old and self._cb is not None:
            self._cb(self)

    def online(self):
        return self._online


class TasmotaPowerState(object):
    def __init__(self, cb=None):
        self._observed = None
        self._expected = None
        self._cb = cb

    def mqtt_pwr(self, pwr):
        _old = self._observed

        self._observed = pwr
        self._expected = pwr

        if _old != pwr and self._cb is not None:
            self._cb(self)

    def user_pwr(self, pwr):
        _old = self._expected

        self._expected = pwr

        if _old != pwr and self._cb is not None:
            self._cb(self)

    def user_toggle(self):
        self.user_pwr(self._expected is not True)

    def expected(self):
        return self._expected

    def observed(self):
        return self._observed

    def observation_match(self):
        return self._observed is not None and self._observed == self._expected

    def handle_message(self, message):
        topic = message.topic

        state = str(message.payload)[2:-1]
        if state == "ON":
            self.mqtt_pwr(True)
        elif state == "OFF":
            self.mqtt_pwr(False)
        else:
            self.mqtt_pwr(None)
            print("Unknown message for topic {}: {}".format(topic, message.payload))


class TasmotaDevice:
    def __init__(self, cfg, section, mqttc, on_state=None):
        self.cfg = cfg
        self.mqtt = mqttc
        self.on_state = on_state

        self.tp = self.cfg.get(section, "type")
        self.topic = self.cfg.get(section, "topic")

        self.online_state = TasmotaOnlineState(cb=self._on_online_state)
        self.pwr_state = TasmotaPowerState(cb=self._on_pwr_state)

        self.mqtt_trigger = Clock.create_trigger(self._mqtt_toggle)

        mqtt.add_topic_callback(self.mqtt, self._get_online_topic(), self._on_online_mqtt)
        mqtt.add_topic_callback(self.mqtt, self._get_pwr_topic(), self._on_pwr_mqtt)

        # query the state
        self.mqtt.publish(self.topic + "/cmnd/Power1", "?", qos=2)

        # if this is active, toggle actions will be ignored
        self.throttled = False

    def toggle(self):
        if not self.throttled:
            self.throttled = True
            Clock.schedule_once(self._unthrottle, 0.5)

            self.pwr_state.user_toggle()
            self.mqtt_trigger()

    def _unthrottle(self, *_largs):
        self.throttled = False

    def get_online_state(self):
        return self.online_state

    def get_pwr_state(self):
        return self.pwr_state

    def _get_online_topic(self):
        return self.topic + "/LWT"

    def _get_pwr_topic(self):
        pwr = "/POWER1" if self.tp == "TASMOTA WS2812" else "/POWER"

        return self.topic + pwr

    def _mqtt_toggle(self, *_largs):
        self.mqtt.publish(self.topic + "/cmnd/Power1", "TOGGLE", qos=2)

        if self.tp == "TASMOTA WS2812":
            sleep(1)
            self.mqtt.publish(self.topic + "/cmnd/Power3", "TOGGLE", qos=2)

    def _on_online_mqtt(self, _client, _userdata, message):
        self.online_state.handle_message(message)

    def _on_pwr_mqtt(self, _client, _userdata, message):
        self.pwr_state.handle_message(message)

    def _on_online_state(self, _state):
        if self.on_state:
            self.on_state(self)

    def _on_pwr_state(self, _state):
        if self.on_state:
            self.on_state(self)
