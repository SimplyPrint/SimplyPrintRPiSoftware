# coding=utf-8
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

__import__('__init__')
from __init__ import *
import subprocess
import socket
import requests
import time
import sys
import os

the_ip = ""
the_ssid = ""
the_hostname = ""
pi_model = ""
octoprint_version = ""
octoprint_api_version = ""
python_version = ""


# Get WiFi SSID
def get_wifi():
    global the_ssid

    ssid = False

    try:
        ssid = subprocess.check_output("iwgetid -r", shell=True)
    except:
        pass

    if not ssid:
        # Try alternative solution - not as good
        try:
            the_scanoutput = subprocess.check_output(["iwlist", "wlan0", "scan"])
            for the_line in the_scanoutput.splitlines():
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
            p = subprocess.Popen("bash get_ip.sh".split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = p.communicate()

            the_ip = out
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


'''
camera_support = "0"
# Not relevant for OctoPrint
camera_check = subprocess.check_output(["vcgencmd", "get_camera"])

if camera_check.find("supported=1") != -1:
    camera_support = "1"

if camera_check.find("detected=1") != -1:
    has_camera = "1"
'''


def set_octoprint_settings():
    global hasmodified

    if octoprint_settings is not None:
        try:
            if octoprint_settings["webcam"]["webcamEnabled"]:
                the_url = octoprint_settings["webcam"]["snapshotUrl"]
                request_check = requests.get(the_url, allow_redirects=True, verify=False)

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
    pi_model = subprocess.check_output(["cat", "/proc/device-tree/model"]).lstrip()
except:
    pass

if pi_model == "":
    # Try it the "old" way
    scanoutput = subprocess.check_output(["cat", "/proc/cpuinfo"])

    for line in scanoutput.splitlines():
        if line.startswith("Model"):
            pi_model = line.split(':')[1].lstrip()
            break

# Often times not connected to the internet yet - give it a little time
# time.sleep(15)

# Send update to server
has_notified_server = False
while not has_notified_server:
    get_wifi()
    get_ip()
    get_octoprint_details()
    set_octoprint_settings()

    the_url = ("&startup=true"
               "&device_ip=" + (url_quote(str(the_ip).rstrip("\n\r").lstrip())) +
               "&pi_model=" + (url_quote(str(pi_model.decode("utf-8")).rstrip("\n\r").lstrip())) +
               "&wifi_ssid=" + (url_quote(str(the_ssid).rstrip("\n\r").lstrip())) +
               "&hostname=" + (url_quote(str(the_hostname).rstrip("\n\r").lstrip())) +
               "&has_camera=" + (url_quote(str(has_camera))) +
               "&octoprint_version=" + (url_quote(str(octoprint_version))) +
               "&octoprint_api_version=" + (url_quote(str(octoprint_api_version))) +
               "&python_version=" + (url_quote(str(python_version))))

    request = website_ping_update(the_url)

    if request:
        has_notified_server = True
        log("STARTUP - request successful!")
        break
    else:
        log("STARTUP - failed startup request. Trying again in 10 seconds.")
        time.sleep(10)
