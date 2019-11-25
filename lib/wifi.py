# -*- coding: UTF-8 -*-
import re
from time import time
from sploitkit import Config, Module, Option, Path


__all__ = ["drone_filter", "re", "time", "Config", "Module", "Option", "Path",
           "ScanMixin", "WifiModule", "WifiAttackModule", "DRONE_REGEX",
           "STATION_REGEX", "TARGET_REGEX", "WPA_HANDSHAKE_REGEX"]


DRONE_REGEX = {
    'C-me':           re.compile(r"C-me[_\-][0-9a-f]{5}"),
    'Flitt':          re.compile(r"Flitt[_\-]\d{6}"),
    'Parrot Bebop':   re.compile(r"Bebop\-[0-9A-F]{6}"),
    'Parrot Bebop 2': re.compile(r"Bebop2\-[0-9A-F]{6}"),
    'DJI Tello':      re.compile(r"TELLO\-[0-9A-F]{6}"),
}
IW_REGEX = re.compile(r"(?m)(?P<name>[a-z][a-z0-9]*)\s+"
                      r"IEEE\s(?P<techno>[a-zA-Z0-9\.])\s+"
                      r"Mode\:\s*(?P<mode>[A-Z][a-z]+)\s+")
STATION_REGEX = re.compile(r"^\s*(?P<bssid>(?:[0-9A-F]{2}\:){5}[0-9A-F]{2})\s+"
                           r"(?P<station>(?:[0-9A-F]{2}\:){5}[0-9A-F]{2})\s+")
TARGET_REGEX = re.compile(r"^\s*(?P<bssid>(?:[0-9A-F]{2}\:){5}[0-9A-F]{2})\s+"
                          r"(?P<power>\-?\d+)\s+"
                          r"(?P<beacons>\d+)\s+"
                          r"(?P<data>\d+)\s+"
                          r"(?P<prate>\d+)\s+"
                          r"(?P<channel>\d+)\s+"
                          r"(?P<mb>\w+)\s+"
                          r"(?P<enc>\w+)\s+"
                          r"(?P<cipher>\w+)\s+"
                          r"(?P<auth>\w+)\s+"
                          r"(?P<essid>[\w\-\.]+)\s*$")
WPA_HANDSHAKE_REGEX = re.compile(r"WPA handshake\:\s+"
                                 r"(?P<bssid>(?:[0-9A-F]{2}\:){5}[0-9A-F]{2})")


def drone_filter(essid):
    for _, regex in DRONE_REGEX.items():
        if regex.match(essid):
            return True
    return False


class ScanMixin(object):
    """ Mixin class for use with Command and Module """
    def run(self, interface, timeout=300):
        self.logger.warning("Press Ctrl+C to interrupt")
        t = self.console.state['TARGETS']
        t.unlock()
        cmd = "sudo airodump-ng {}".format(interface)
        try:
            for line in self.console._jobs.run_iter(cmd, timeout=int(timeout)):
                _ = TARGET_REGEX.search(line)
                if _ is None:
                    continue
                data = {}
                for k in ["essid", "bssid", "channel", "power", "enc", "cipher",
                          "auth"]:
                    v = _.group(k)
                    data[k] = int(v) if v.isdigit() else v
                data['password'] = None
                e = data['essid']
                if self._filter_func(e):
                    if e not in t.keys():
                        self.logger.info("Found {}".format(e))
                    else:
                        data['password'] = t[e].get('password')
                    t[e] = data
        finally:
            t.lock()


class WifiModule(Module):
    """ Module proxy class for WiFi-related modules """
    config = Config({
        Option(
            'INTERFACE',
            "WiFi interface in monitor mode",
            True,
            choices=lambda o: o.config.console.root.mon_interfaces,
        ): None,
    })
    path = "auxiliary/wifi"
    requirements = {'system': ["wireless-tools/iwconfig"]}
    
    def preload(self):
        return self.prerun()
    
    def prerun(self):
        if len(self.console.root.mon_interfaces) == 0:
            self.logger.warning("No interface in monitor mode defined ; please"
                                " use the 'toggle' command")
            return False
        self.config['INTERFACE'] = self.console.root.mon_interfaces[0]


class WifiAttackModule(WifiModule):
    """ Module proxy class for WiFi-related modules handling a target """
    config = Config({
        Option(
            'ESSID',
            "Target AP's ESSID",
            True,
            choices=lambda o: o.config.console.state['TARGETS'].keys()
        ): None,
    })
    
    def preload(self):
        if super(WifiAttackModule, self).preload() is False:
            return False
        _ = self.console.state['TARGETS']
        if len(_) == 0:
            self.logger.warning("No target available yet ; please use the "
                                "'scan' command")
            return False
        self.config['ESSID'] = v = _[list(_.keys())[0]]['essid']
        self.logger.debug("ESSID => {}".format(v))