# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

#
#  SimplyPrint
#  Copyright (C) 2020  SimplyPrint ApS
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
from __future__ import absolute_import, division, unicode_literals

import subprocess
import socket
import requests
import time
import sys
import io

from .base import *


the_ip = ""
the_ssid = ""
the_hostname = ""
pi_model = ""
octoprint_version = ""
octoprint_api_version = ""
python_version = ""
has_camera = "0"


# Get WiFi SSID
def get_wifi():
    global the_ssid

    ssid = False

    try:
        process = subprocess.Popen(["iwgetid", "-r"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        ssid = stdout.decode("utf-8", errors="replace")
    except:
        pass

    if not ssid:
        # Try alternative solution - not as good
        try:
            process = subprocess.Popen(["iwlist", "wlan0", "scan"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            for the_line in stdout.decode("utf-8").splitlines():
                the_line = the_line.lstrip()
                if the_line.startswith("ESSID"):
                    the_ssid = the_line.split('"')[1]
                    break
        except:
            log("STARTUP - Failed to get WiFi")


# Get local IP
def get_ip():
    global the_ip

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        the_ip = s.getsockname()[0]
    except:
        the_ip = ""

    if not the_ip or the_ip is None or the_ip == "127.0.1.1":
        try:
            get_ip_script_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "get_ip.sh")
            p = subprocess.Popen(["bash", get_ip_script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = p.communicate()

            the_ip = out.decode("utf-8", errors="replace")
        except:
            log("STARTUP - Failed to get device IP")

    the_ip = the_ip.replace("\n", "")


def get_octoprint_details():
    global octoprint_version, octoprint_api_version

    oc_version_info = octoprint_api_req("version")
    if oc_version_info is not None:
        if oc_version_info is not False:
            octoprint_version = oc_version_info["server"]
            octoprint_api_version = oc_version_info["api"]


def set_octoprint_settings():
    global hasmodified, has_camera, octoprint_settings

    if octoprint_settings is not None:
        try:
            if octoprint_settings["webcam"]["webcamEnabled"]:
                the_url = octoprint_settings["webcam"]["snapshotUrl"]
                request_check = requests.get(the_url, allow_redirects=True, verify=False, timeout=5)

                if request_check.status_code == 200:
                    has_camera = "1"
            else:
                # OctoPrint "Enable webcam support" checkbox is unticked - check it
                log("STARTUP - OctoPrint didn't have webcam support ticked - enabling it")
                hasmodified = True
                set_config()
        except:
            # Failed - camera not available
            pass


def run_startup():
    global the_ssid
    global the_hostname
    global pi_model
    global octoprint_settings
    global python_version

    # Get hostname
    try:
        the_hostname = socket.gethostname()
    except:
        log("STARTUP - Failed to get hostname")

    # Get python version
    try:
        python_version = str(sys.version_info[0]) + "." + str(sys.version_info[1]) + "." + str(sys.version_info[2])
    except:
        log("STARTUP - Failed to get Python version")

    # Get camera support
    has_camera = "0"

    # Get Raspberry board info
    try:
        with io.open("/proc/device-tree/model", "rt", encoding="utf-8") as file:
            pi_model = file.readline().strip(" \t\r\n\0")
    except:
        pi_model = None
        pass

    if pi_model == "":
        # Try it the "old" way
        with io.open("/proc/cpuinfo", "rt", encoding="utf-8") as file:
            cpuinfo = file.readline().strip(" \t\r\n\0")

        for line in cpuinfo.splitlines():
            if line.startswith("Model"):
                pi_model = line.split(':')[1].lstrip()
                break

    # Often times not connected to the internet yet - give it a little time
    # time.sleep(15)

    octoprint_is_up = False
    while not octoprint_is_up:
        if octoprint_settings is not None:
            print("OctoPrint is up!")
            octoprint_is_up = True
        else:
            # Let's wait and try again
            print("OctoPrint is down - waiting until it's up to send startup request")
            time.sleep(5)
            octoprint_settings = octoprint_api_req("settings")

    # Send update to server
    has_notified_server = False
    while not has_notified_server:
        get_wifi()
        get_ip()
        get_octoprint_details()
        set_octoprint_settings()

        the_url = ("&startup=true"
                   "&device_ip=" + (url_quote(the_ip.encode("utf-8").rstrip("\n\r").lstrip())) +
                   "&pi_model=" + (url_quote(pi_model.encode("utf-8").rstrip("\n\r").lstrip())) +
                   "&wifi_ssid=" + (url_quote(the_ssid.encode("utf-8").rstrip("\n\r").lstrip())) +
                   "&hostname=" + (url_quote(the_hostname.encode("utf-8").rstrip("\n\r").lstrip())) +
                   "&has_camera=" + (url_quote(str(has_camera))) +
                   "&octoprint_version=" + (url_quote(str(octoprint_version))) +
                   "&octoprint_api_version=" + (url_quote(str(octoprint_api_version))) +
                   "&python_version=" + (url_quote(str(python_version))))

        request = website_ping_update(the_url)

        if request:
            log("STARTUP - request successful!")
            has_notified_server = True
        else:
            log("STARTUP - failed startup request. Trying again in 10 seconds.")
            time.sleep(10)
