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

import yaml
import uuid
import requests
import json
import os
import logging
from datetime import datetime
import time
import socket
import sys
import subprocess

system_version = "1.9.9"
api_version = "0.0.2"


def is_py_3():
    return sys.version_info > (3, 0)


def py_prefix():
    if is_py_3():
        return "python3"
    else:
        return "python"


if is_py_3():
    # Python 3
    import configparser
    import urllib3
    import urllib.parse

    config = configparser.SafeConfigParser()
else:
    # Python 2
    import ConfigParser
    import urllib2

    config = ConfigParser.SafeConfigParser()


def url_quote(thestring):
    if is_py_3():
        return urllib.parse.quote(thestring)
    else:
        return urllib2.quote(thestring)


# ~ Variables
dir_path = os.path.dirname(os.path.realpath(__file__))
settings_location = os.path.join(dir_path, "settings.ini")
temp_files_path = os.path.join(dir_path, "files")
__global_print_job__ = None
__global_printer__ = None
is_serial_connecting = False
octoprint_settings = None
http = None

if not os.path.exists(temp_files_path):
    os.makedirs(temp_files_path)

hasmodified = False
config.read(settings_location)
current_job_completion_var = None


def current_job_completion():
    if current_job_completion_var is None:
        return None
    else:
        return int(current_job_completion_var)


octoprint_plugin_name = "SimplyPrint"
request_url = "https://simplyprint.dk/"
update_url = request_url + "api/do_update.php"

# ~ Debugging & logging
log_locations = os.path.join(dir_path, "logs")

if not os.path.exists(log_locations):
    os.makedirs(log_locations)

debugging = True
logging.basicConfig(level=logging.DEBUG,
                    filename=(log_locations + "/log_" + str(datetime.today().strftime('%Y-%m-%d')) + ".log"))

now = time.time()
for filename in os.listdir(log_locations):
    the_file = os.path.join(log_locations, filename)

    if os.stat(the_file).st_mtime < now - 7 * 86400:
        if os.path.isfile(the_file):
            os.remove(the_file)


def log(comment, log_type="debug"):
    global debugging

    if debugging:
        print("[" + log_type + "] " + comment)

    if log_type == "debug":
        logging.debug(comment)
    if log_type == "info":
        logging.info(comment)
    if log_type == "warning":
        logging.warning(comment)
    if log_type == "error":
        logging.error(comment)
    if log_type == "critical":
        logging.critical(comment)


rpi_id_loc = "/home/pi/simplyprint_rpi_id.txt"


def set_rpi_id(new_id):
    global rpi_id_loc

    with open(rpi_id_loc, "w") as thefile:
        thefile.write(new_id)


def get_rpid():
    global rpi_id_loc

    if os.path.exists(rpi_id_loc):
        f = open(rpi_id_loc, "r")
        if f.mode == 'r':
            contents = f.read()
            return str(contents)
    return ""


def clear_installation_files():
    def try_del(thefile):
        if os.path.exists(thefile):
            os.remove(thefile)

    try:
        try_del("/home/pi/update_script.sh")
        try_del("/home/pi/install_system.sh")
        try_del("/tmp/SimplyPrintUpdater.sh")
        try_del("/tmp/system_updater.sh")
    except Exception as e:
        log("Failed to remove old update / install files... Error; " + str(e))


required_sections = {
    "info": {
        "last_known_version": system_version,
        "just_updated": "False",
        "is_set_up": "False",
        "created": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "printer_id": "0",
        "printer_name": "unset",
        "requests_per_minute": "6",
        "last_connection_attempt": "0",
        "temp_short_setup_id": "",
        "octoprint_down": "False",
        "last_user_settings_sync": "0000-00-00 00:00:00"
    },
    "settings": {
        "display_enabled": "True",
        "display_branding": "True",
        "display_show_status": "True",
        "display_while_printing_type": "0"
    },
    "octoprint": {
        "apikey": "null"
    }
}


def update_config_sections():
    global required_sections, hasmodified, config

    for x in required_sections:
        if not config.has_section(x):
            config.add_section(x)
            log("Adding missing config section; " + str(x))
            hasmodified = True

        for x2 in required_sections[x]:
            if not config.has_option(x, x2):
                config.set(x, x2, required_sections[x][x2])
                log("Adding missing config value; " + str(x) + ", " + str(x2))
                hasmodified = True


update_config_sections()


def get_octoprint_api_key():
    global hasmodified, config

    try:
        with open("/home/pi/.octoprint/config.yaml", 'r') as stream:
            try:
                the_config = yaml.safe_load(stream)
                the_key = the_config["api"]["key"]

                log("The OctoPrint API key is; " + the_key)

                if config.get("octoprint", "apikey") != the_key:
                    config.set('octoprint', 'apikey', the_key)
                    hasmodified = True

            except yaml.YAMLError as exc:
                log(exc)
    except:
        log("Failed to ")


def has_internet():
    try:
        # connect to the host -- tells us if the host is actually reachable
        socket.create_connection(("www.google.com", 80))
        return True
    except OSError:
        return False


def ble_service_checkup():
    is_set_up = config.getboolean("info", "is_set_up")
    var = os.popen("ps ax | grep 'simplypi_ble_setup.py' | grep -v grep").read()
    service_running = len(var) != 0
    no_wifi = not has_internet()

    if service_running and is_set_up and not no_wifi:
        # BLE service is running while the system is set up - it should not
        pid = int(os.popen("cat /tmp/simplypi_ble_service_pid").read())
        log("Killing SimplyPrint BLE setup service with ID; " + str(pid))
        try:
            with open(os.devnull, "wb") as devnull:
                subprocess.check_call(["sudo", "kill", "-9", str(pid)], stdout=devnull, stderr=subprocess.STDOUT)
        except:
            # Process doesn't exist (probably)
            pass
    elif (not service_running and not is_set_up) or no_wifi:
        # BLE service NOT running, but it should
        try:
            bluetooth_is_up = os.system('systemctl is-active -quiet bluetooth')

            if str(bluetooth_is_up) != "0":
                log("Running SimplyPrint BLE setup service")
                try:
                    subprocess.Popen(["sudo python3 /home/pi/SimplyPrint/setup_ble/simplypi_ble_setup.py"], shell=True,
                                     stdin=None, stdout=None, stderr=None, close_fds=True)
                except:
                    log("Failed to run BLE setup service")
            else:
                log("The Bluetooth service is not yet up (" + str(
                    bluetooth_is_up) + ") - not starting the BLE setup service yet")
        except:
            log("Failed to check whether the Bluetooth service is up or not")


ble_service_checkup()


def octoprint_apikey():
    if config.has_section("octoprint"):
        return str(config.get("octoprint", "apikey"))
    else:
        return "null"


def get_request(url, no_json=False, is_api_request=False):
    global http

    url = url.replace(" ", "%20")

    hdr = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 ' +
                      'Safari/537.11',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
        'Accept-Encoding': 'none',
        'Accept-Language': 'en-UK,en;q=0.8',
        'Connection': 'keep-alive'
    }

    try:
        if is_py_3():
            if http is None:
                http = urllib3.PoolManager()

            the_request = http.request("GET", url, headers=hdr)
            content = the_request.data
        else:
            req = urllib2.Request(url, headers=hdr)
            the_request = urllib2.urlopen(req)
            content = the_request.read()

        the_request.close()
    except Exception as e:
        log("[ERROR] - Failed to request url; " + str(url) + ". Error is; " + str(e))

        if "403" in str(e) and is_api_request:
            log("API request is forbidden - API key probably no longer valid, getting the new")
            get_octoprint_api_key()
            website_ping_update("&octoprint_api_key=" + octoprint_apikey())

        if "503" in str(e) and is_api_request:
            if not config.getboolean("info", "octoprint_down"):
                down_to_set = "True"
                log("OctoPrint is down (503: Service Unavailable) - waiting to make sure it's really down, "
                    "then restarting")
                website_ping_update("&octoprint_status=Shutdown")
            else:
                down_to_set = "False"
                log("OctoPrint is STILL down - restarting the OctoPrint service")
                os.system("sudo service octoprint restart")

            set_config_key("info", "octoprint_down", down_to_set)
            set_config()

        return False

    if no_json:
        return content
    else:
        try:
            json_content = json.loads(content.decode("utf-8"))
            return json_content
        except:
            log("[ERROR] - Failed to jsonify request; " + str(content.decode("utf-8")))
            return False


def post_request(url, postobj, no_json=False, custom_header=None):
    # import requests

    if custom_header is None:
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": octoprint_apikey(),
        }
    else:
        headers = custom_header

    try:
        x = requests.post(url, data=json.dumps(postobj), headers=headers, verify=False)
        if no_json:
            return x
        else:
            if is_py_3():
                content = x.json()
            else:
                content = json.loads(x.text)

            return content
    except:
        return False


def octoprint_api_req(api_file, post_data=None, no_json=False, custom_header=None):
    global config
    the_url = "http://localhost/api/" + api_file + "?apikey=" + octoprint_apikey()

    if post_data is None:
        content = get_request(the_url, no_json, True)
    else:
        content = post_request(the_url, post_data, no_json, custom_header)

    if content is not False:
        return content
    else:
        return None


def send_job_command(command, action=None):
    post_data = {"command": command}
    if action is not None:
        post_data["action"] = action

    response = octoprint_api_req("job", post_data, True)
    if response is not None:
        if response.status_code == 204:
            return True
    log("Failed to execute job command; " + command)
    return False


def connect_printer(disconnect=False):
    if disconnect:
        command = "disconnect"
    else:
        command = "connect"

    post_data = {"command": command, "autoconnect": True}
    response = octoprint_api_req("connection", post_data, True)

    if response is True:
        log("Printer " + command + "ed")
    else:
        log("Failed to " + command + " printer")


def reset_api_cache():
    global __global_printer__, __global_print_job__
    __global_printer__ = None
    __global_print_job__ = None


def get_print_job(reset=False):
    global __global_print_job__

    if __global_print_job__ is None or reset:
        __global_print_job__ = octoprint_api_req("job")

    return __global_print_job__


def get_printer(reset=False):
    global __global_printer__

    if __global_printer__ is None or reset:
        __global_printer__ = octoprint_api_req("printer")

    return __global_printer__


def get_printer_state():
    global __global_printer__, __global_print_job__

    if __global_printer__ is not None and __global_print_job__ is None:
        if get_printer() is not None:
            if "state" in get_printer():
                if "text" in get_printer()["state"]:
                    return get_printer()["state"]["text"]
                else:
                    return get_printer()["state"]
    else:
        if get_print_job() is not None:
            if "state" in get_print_job():
                return get_print_job()["state"]

    return None


def check_connect_printer():
    global is_serial_connecting

    # On lots of errors; timeout - try again in a minute or so to give the Serial port a rest
    if get_printer_state() is not None:
        if get_printer_state() not in ["Operational", "Connecting", "Printing", "Paused", "Cancelling", "Pausing",
                                       "Resuming" "Detecting serial port", "Opening serial port", "Printing from SD",
                                       "Detecting baudrate"] \
                and not is_serial_connecting:
            # if get_printer_state()[0:5] != "Error":

            # One minute has to have passed - don't spam the serial port
            last_request = config.getint("info", "last_connection_attempt")
            try:
                if int(time.time()) > (int(last_request) + 60):
                    set_config_key("info", "last_connection_attempt", str(int(time.time())))

                    log(" - Trying to connect to printer... (state is " + get_printer_state() + " so it's OK)")
                    the_try = get_printer()
                    if the_try is None:
                        is_serial_connecting = False
                        connect_printer()
            except:
                # Most likely failed to parse the string to int - probably "None"
                pass


def website_ping_update(extra_parameters=None):
    global hasmodified, current_job_completion_var, api_version

    base_url = update_url + "?id=" + get_rpid() + "&api_version=" + api_version

    if extra_parameters is not None:
        base_url += extra_parameters

    printer_info = get_printer()
    p_state = get_printer_state()

    if printer_info is None:
        # Check if OctoPrint is set up
        try:
            check = octoprint_api_req("printer/command", {}, True)
            if check.text == "OctoPrint isn't setup yet":
                log("OctoPrint is not set up - letting server know")
                base_url += "&octoprint_not_set_up"
        except:
            pass

    is_in_setup = not config.getboolean("info", "is_set_up")
    '''if not is_in_setup:
        if p_state != "Offline" and p_state != "Disconnecting" and p_state != "Cancelling" and p_state != "Connecting":
            printer_info = octoprint_api_req("printer", None)'''

    if p_state is None:
        p_state = "unknown"

    if is_in_setup:
        # Make sure printer is connected when it's expecting setup
        check_connect_printer()

        the_url = base_url + "&new=true&printer_tmp_state=" + p_state
        # log("Requesting; " + str(the_url))
        return get_request(the_url, True)
    else:
        # "Offline" often comes with a long string complaining about serial... We don't want that
        if len(p_state) >= 7:
            if p_state[0:7] == "Offline":
                p_state = "Offline"

        to_set = {}

        if printer_info is not None:
            if "temperature" in printer_info:
                if "bed" in printer_info["temperature"]:
                    to_set["bed_temp"] = round(printer_info["temperature"]["bed"]["actual"])
                    to_set["target_bed_temp"] = round(printer_info["temperature"]["bed"]["target"])

                if "tool0" in printer_info["temperature"]:
                    to_set["tool_temp"] = round(printer_info["temperature"]["tool0"]["actual"])
                    to_set["target_tool_temp"] = round(printer_info["temperature"]["tool0"]["target"])

            if p_state == "Printing" or p_state == "Cancelling" or p_state == "Pausing" or p_state == "Paused":
                print_job = get_print_job()
                if print_job is not None:
                    if "progress" in print_job:
                        if "completion" in print_job["progress"]:
                            if print_job["progress"]["completion"] is not None:
                                to_set["completion"] = round(float(print_job["progress"]["completion"]))
                                current_job_completion_var = int(to_set["completion"])

                    to_set["estimated_finish"] = print_job["progress"]["printTimeLeft"]

                    if print_job["job"]["filament"] is not None:
                        to_set["filament_usage"] = print_job["job"]["filament"]["tool0"]["volume"]

                    to_set["initial_estimate"] = print_job["job"]["estimatedPrintTime"]

        base_url += "&custom_sys_version=" + str(system_version)

        if config.getboolean("info", "just_updated"):
            config.set("info", "just_updated", "False")
            log("Just updated to new system version!")
            hasmodified = True
            base_url += "&system_updated=yes"
            set_config()

            # Run "startup" script to send IP, WiFi and such
            try:
                subprocess.Popen(str("sudo " + py_prefix() + " /home/pi/SimplyPrint/startup.py").split())
            except:
                log("Failed to open 'startup' script")

            # Clean up!
            clear_installation_files()

        the_url = base_url + "&pstatus=" + p_state + "&extra=" + url_quote(json.dumps(to_set))

        return get_request(the_url, True)


# Upload, slice & file processing
def download_file(url, new_name, free_space_check=None):
    try:
        r = requests.get(url, allow_redirects=True, verify=False)
    except:
        return [False, "Failed to request url; " + url]

    # TODO; FIX!!!
    '''if free_space_check is not None:
        file_size = r.headers["Content-Length"]
        if file_size < free_space_check:
            msg = "File is too big - not enough space (filesize; " + str(file_size) + " out of " + str(
                free_space_check) + ")"
            log(" - [ERROR] " + msg)
            return [False, msg]
        else:
            log(" - File size of file to download is; " + str(file_size))'''

    if r.status_code == 200:
        try:
            open(new_name, 'wb').write(r.content)
            return [True, ""]
        except:
            return [False, "Failed to create file locally"]
    else:
        return [False, "Status code from download URL is not 200. Status code is; " + str(r.status_code)]


def upload_file(file_to_upload, dest_filename):
    custom_headers = {
        "X-Api-Key": octoprint_apikey(),
    }

    the_status = True

    fle = {'file': open(file_to_upload, 'rb')}
    url = 'http://localhost/api/files/{}'.format('local')
    payload = {'select': 'true', 'print': 'false'}
    response = requests.post(url, files=fle, data=payload, headers=custom_headers, verify=False)

    return [the_status, response]


def process_file_request(download_url):
    the_filename, file_extension = os.path.splitext(download_url)
    new_filename = "sp_" + str(uuid.uuid1()) + ".gcode"
    new_file_dest = os.path.join(temp_files_path, new_filename)
    free_space = octoprint_api_req("files/local")["free"]

    if free_space is None:
        log("Failed to get free space when processing file")
        return

    return_msg = ""

    log("[DOWNLOADING AND UPLOADING]")
    log(" - New filename is; " + new_filename)
    log(" - Free space; " + str(free_space))

    log(" - deleting old files...")
    # Delete all old OctoPrint files
    the_headers = {
        "Content-Type": "application/json",
        "X-Api-Key": octoprint_apikey(),
    }

    the_files_req = octoprint_api_req("files")
    if the_files_req is not None:
        for value in the_files_req["files"]:
            if str(value["display"][:3]) == "sp_":
                requests.delete(value["refs"]["resource"], headers=the_headers, verify=False)

    log(" - old files deleted")

    the_download = download_file(download_url, new_file_dest, free_space)
    if the_download[0]:
        log(" - Successfully downloaded file to; " + new_file_dest)

        # Uploading through the OctoPrint API helps metadata be created correctly, and events be fired
        the_upload = upload_file(new_file_dest, new_filename)

        log(" - File upload finished")

        if the_upload[0]:
            if the_upload[1].status_code == 201:  # "Created" HTTP response code
                log(" - Successfully uploaded file - removing local version.")

                os.remove(new_file_dest)

                if return_msg == "":
                    return [True, "", new_filename]
            else:
                return_msg = "Failed to upload file. Error message; " + str(the_upload[1].content)
        else:
            return_msg = "Failed to upload file - exception"
    else:
        return_msg = the_download[1]

    log(" - [ERROR] " + return_msg)
    return [False, return_msg, new_filename]


if config.has_section("info"):
    last_known_version = config.get("info", "last_known_version")
    if last_known_version != system_version:
        log("Custom system has been updated - last known version was; " + last_known_version +
            ", updated to " + system_version)
        config.set("info", "last_known_version", system_version)
        config.set("info", "just_updated", "True")
        hasmodified = True

octoprint_settings = octoprint_api_req("settings")


# Check octoprint plugin settings data (if nothing else is modified)
def sync_settings_with_plugin():
    global octoprint_settings, hasmodified

    if octoprint_settings is not None:
        if octoprint_settings != False:
            if "plugins" in octoprint_settings:
                if octoprint_plugin_name in octoprint_settings["plugins"]:
                    the_data = octoprint_settings["plugins"][octoprint_plugin_name]
                    the_check = str(config.get("info", "is_set_up"))

                    if str(the_data["is_set_up"]) != the_check:
                        log("Plugin setting 'is_set_up' is not the same as local config."
                            "\nLocal; " + str(config.get("info", "is_set_up")) + ", plugin; " +
                            str(the_data["is_set_up"]))

                        hasmodified = True

                    the_check = str(update_url + "?id=" + get_rpid())
                    if str(the_data["request_url"]) != the_check:
                        log("Plugin setting 'request_url' is not the same as local config"
                            "\nLocal; " + str(the_check) + ", plugin; " + str(the_data["request_url"]))

                        hasmodified = True

                    the_check = str(get_rpid())
                    if str(the_data["rpi_id"]) != the_check:
                        log("Plugin setting 'rpi_id' is not the same as local config"
                            "\nLocal; " + the_check + ", plugin; " + the_data["rpi_id"])

                        hasmodified = True

                    the_check = str(config.get("info", "printer_id"))
                    if str(the_data["printer_id"]) != the_check:
                        log("Plugin setting 'printer_id' is not the same as local config"
                            "\nLocal; " + the_check + ", plugin; " + str(the_data["printer_id"]))

                        hasmodified = True

                    the_check = str(config.get("info", "printer_name"))
                    printer_name = str(the_data["printer_name"]).strip()

                    if printer_name != the_check:
                        log("Plugin setting 'printer_name' is not the same as local config"
                            "\nLocal; " + str(the_check) + ", plugin; " + str(printer_name))

                        hasmodified = True

                    the_check = str(config.get("info", "temp_short_setup_id"))
                    printer_name = the_data["temp_short_setup_id"].strip()

                    if printer_name != the_check:
                        log("Plugin setting 'temp_short_setup_id' is not the same as local config"
                            "\nLocal; " + str(the_check) + ", plugin; " + str(printer_name))

                        hasmodified = True

                    the_check = system_version
                    if str(the_data["simplyprint_version"]) != the_check:
                        log("Plugin setting 'printer_id' is not the same as local config"
                            "\nLocal; " + str(the_check) + ", plugin; " + str(the_data["simplyprint_version"]))

                        hasmodified = True
                else:
                    log("OctoPrint plugin is not installed (or just disabled)", "error")
            else:
                log("Cannot get OctoPrint plugins", "error")
        else:
            log("Can't connect to OctoPrint API", "error")
    else:
        log("Can't connect to OctoPrint API", "error")


if not hasmodified:
    sync_settings_with_plugin()


def set_config_key(section, key, value):
    global hasmodified

    config.set(section, key, value)
    log("Modified config key; " + section + ", " + key)
    hasmodified = True


# Config stuff
def set_config():
    global settings_location, config, hasmodified, octoprint_plugin_name, system_version

    if config.get("octoprint", "apikey") == "null":
        log("OctoPrint API key is null, getting it from the config...")
        get_octoprint_api_key()

    if hasmodified:
        log("Settings were modified. Updating settings.ini file...")

        with open(settings_location, "w") as configfile:
            config.write(configfile)

        if str(config.get("info", "is_set_up")) == "True":
            is_set_up = True
        else:
            is_set_up = False

        printer_id = 0
        if config.get("info", "printer_id") is not None:
            try:
                printer_id = int(config.get("info", "printer_id"))
            except:
                pass

        # "Sync" data with the OctoPrint plugin - this is the way these scripts and the plugin communicate
        post_data = {
            "webcam": {
                "webcamEnabled": True,
                "timelapseEnabled": True,
                "watermark": False
            },
            "plugins": {
                octoprint_plugin_name: {
                    "is_set_up": is_set_up,
                    "request_url": update_url + "?id=" + get_rpid(),
                    "rpi_id": str(get_rpid()),
                    "printer_id": printer_id,
                    "printer_name": str(config.get("info", "printer_name")),
                    "simplyprint_version": str(system_version),
                    "sp_local_installed": True,
                    "temp_short_setup_id": str(config.get("info", "temp_short_setup_id"))
                }
            }
        }
        octoprint_api_req("settings", post_data)


set_config()
last_branding = None


def set_display(text, short_branding=False):
    global last_branding

    prefix = ""
    if config.getboolean("settings", "display_branding") or not config.getboolean("info", "is_set_up"):
        if short_branding:
            prefix = "[SP]"
        else:
            prefix = "[SimplyPrint]"

    if str(text) != last_branding and (
            config.getboolean("settings", "display_enabled") or not config.getboolean("info", "is_set_up")):
        last_branding = str(text)

        octoprint_api_req("printer/command", {"command": "M117 " + prefix + " " + str(text)})
