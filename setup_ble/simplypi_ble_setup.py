#!/usr/bin/python3
"""
SimplyPrint
Copyright (C) 2020  SimplyPrint ApS

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import dbus
import os
import socket
import configparser
from advertisement import Advertisement
from service import Application, Service, Characteristic, Descriptor
import json

GATT_CHRC_IFACE = "org.bluez.GattCharacteristic1"
NOTIFY_TIMEOUT = 5000

pid = str(os.getpid())
f = open('/tmp/simplypi_ble_service_pid', 'w')
f.write(pid)
f.close()


class SimplyPiAdvertisement(Advertisement):
    def __init__(self, index):
        Advertisement.__init__(self, index, "peripheral")
        self.add_local_name(socket.gethostname())
        self.include_tx_power = True


class SimplyPiService(Service):
    SimplyPi_SVC_UUID = "a0b8d104-afb4-11ea-b3de-0242ac130004"

    def __init__(self, index):
        Service.__init__(self, index, self.SimplyPi_SVC_UUID, True)
        self.add_characteristic(PrinterIDCharacteristic(self))
        self.add_characteristic(NetworkCharacteristic(self))
        self.add_characteristic(HasNetworkCharacteristic(self))


class PrinterIDCharacteristic(Characteristic):
    PRINTERID_CHARACTERISTIC_UUID = "b0b8d104-afb4-11ea-b3de-0242ac130004"

    def __init__(self, service):
        self.notifying = False

        Characteristic.__init__(self, self.PRINTERID_CHARACTERISTIC_UUID, ["notify", "read"], service)
        # self.add_descriptor(PrinterIDDescriptor(self))

    def ReadValue(self, options):
        print('Getting printer ID')
        # /home/pi/SimplyPrint/settings.ini

        value = []

        config = configparser.ConfigParser()
        config.read('/home/pi/SimplyPrint/settings.ini')

        if config.getboolean("info", "is_set_up"):
            temp_str = 'Printer has been set up'
        else:
            temp_str = config['info']['temp_short_setup_id']

        for x in temp_str:
            value.append(dbus.Byte(x.encode()))

        return value


class NetworkCharacteristic(Characteristic):
    NETWORK_CHARACTERISTIC_UUID = "c0b8d104-afb4-11ea-b3de-0242ac130004"
    ssid = 'empty'
    thepass = ''
    content = ''

    def __init__(self, service):
        Characteristic.__init__(
            self, self.NETWORK_CHARACTERISTIC_UUID,
            ["read", "write"], service)
        # self.add_descriptor(NetworkDescriptor(self))

    def WriteValue(self, value, options):
        print("value: %s" % ''.join([str(v) for v in value]))
        jsonstring = json.loads(''.join([str(v) for v in value]))

        if "ssid" in jsonstring and "pass" in jsonstring:
            self.ssid = jsonstring["ssid"]
            self.thepass = jsonstring["pass"]
            print('ssid: ' + self.ssid + ' password: ' + self.thepass)
            with open('../../../../etc/wpa_supplicant/wpa_supplicant.conf', 'r') as myFile:
                self.content = myFile.read()
            with open('../../../../etc/wpa_supplicant/wpa_supplicant.conf', 'w') as myFile:
                temp_str = '# WPA/WPA2 secured /n network={ /n   ssid="' + self.ssid + '" /n   psk="' + self.thepass + '" /n } /n'
                newContent = temp_str + self.content
                myFile.write(newContent)
            os.system("sudo reboot")

    def ReadValue(self, options):
        print('Reading value')
        value = []

        try:
            socket.setdefaulttimeout(3)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
            temp_bool = 'true'
        except socket.error as ex:
            print(ex)
            temp_bool = 'false'

        for x in temp_bool:
            value.append(dbus.Byte(x.encode()))

        return value

    def internet(host="8.8.8.8", port=53, timeout=3):
        """
        Host: 8.8.8.8 (google-public-dns-a.google.com)
        OpenPort: 53/tcp
        Service: domain (DNS/TCP)
        """
        try:
            socket.setdefaulttimeout(timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
            return True
        except socket.error as ex:
            print(ex)

        return False


class HasNetworkCharacteristic(Characteristic):
    HasNetwork_CHARACTERISTIC_UUID = "d0b8d104-afb4-11ea-b3de-0242ac130004"
    temp_bool = 'none'

    def __init__(self, service):
        self.notifying = False

        Characteristic.__init__(
            self, self.HasNetwork_CHARACTERISTIC_UUID,
            ["read"], service)

        # self.add_descriptor(HasNetworkDescriptor(self))

    def internet(host="8.8.8.8", port=53, timeout=3):
        """
        Host: 8.8.8.8 (google-public-dns-a.google.com)
        OpenPort: 53/tcp
        Service: domain (DNS/TCP)
        """
        try:
            socket.setdefaulttimeout(timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
            return True
        except socket.error as ex:
            print(ex)

        return False

    def ReadValue(self, options):
        print('Reading value')
        value = []

        try:
            socket.setdefaulttimeout(3)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
            self.temp_bool = '1'
        except socket.error as ex:
            print(ex)
            self.temp_bool = '0'

        for x in self.temp_bool:
            value.append(dbus.Byte(x.encode()))

        return value


app = Application()
app.add_service(SimplyPiService(0))
app.register()

adv = SimplyPiAdvertisement(0)
adv.register()

try:
    app.run()
except KeyboardInterrupt:
    app.quit()
