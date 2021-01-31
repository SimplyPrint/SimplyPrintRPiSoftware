# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

#
# SimplyPrint
# Copyright (C) 2020-2021  SimplyPrint ApS
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from .base import *
import time
import subprocess
import sys
from datetime import datetime

start_time = time.time()
times_a_minute = config.getint("info", "requests_per_minute")

demand_list = None
request_settings_next_time = False

plugin_settings_awaiting = []
last_awaiting_plugin_set = None
has_checked_safemode = False
has_checked_power_controller = False
has_checked_filament_sensor = False
has_checked_webcam_options = False
has_checked_firmware_info = False


def check_has_update():
    global times_a_minute, demand_list, request_settings_next_time, last_request_response_code, dir_path, last_awaiting_plugin_set

    if has_demand("update_system"):
        # Update SimplyPrint system!
        log("Updating system...")
        set_display("Updating...", True)

        # Clean up old cron jobs
        try:
            from crontab import CronTab

            cron = CronTab(user=True)

            for job in cron:
                print(job.comment.lower())
                if "[simplyprint" in job.comment.lower() and "[simplyprint keep]" not in job.comment.lower():
                    cron.remove(job)

            cron.write()
        except:
            log("Failed to clean up cron jobs")

        try:
            process = subprocess.Popen(
                [sys.executable,
                 "-m",
                 "pip",
                 "install",
                 "--upgrade",
                 "--no-cache-dir",
                 "SimplyPrintRPiSoftware"
                 ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            # This will wait for install to finish
            _stdout, _stderr = process.communicate()
        except Exception as e:
            msg = "Failed to install update to SimplyPrintRPiSoftware. Error; {}".format(repr(e))
            log(msg)
            website_ping_update("&system_update_failed=" + msg)
            return False

        # Install new cron jobs
        _process = subprocess.Popen(
            [sys.executable,
             "-m",
             "simplyprint_raspberry",
             "install",
             ],
        )

        # Didn't exit - means update has started; tell system and then exit
        website_ping_update("&system_update_started=true")
        time.sleep(2)
        sys.exit(0)


def process_pending_settings():
    global last_awaiting_plugin_set, plugin_settings_awaiting

    if len(plugin_settings_awaiting) > 0 and isinstance(last_awaiting_plugin_set,
                                                        float) and time.time() > last_awaiting_plugin_set + 10:
        # There are plugin settings awaiting being set!
        for set_setting in plugin_settings_awaiting:
            check = octoprint_api_req("settings", set_setting, True, None, True)
            if check == 200:
                log("Waited and set the settings for a plugin!")
                plugin_settings_awaiting.remove(set_setting)
            else:
                log("Failed to set settings... " + str(check))


def has_demand(demand, check_true=True):
    global demand_list
    if demand in demand_list:
        if demand_list[demand] or not check_true:
            return True
    return False


def do_the_request(num):
    global times_a_minute, demand_list, request_settings_next_time, has_checked_safemode, last_awaiting_plugin_set
    global has_checked_power_controller, has_checked_filament_sensor, last_request_response_code, dir_path
    global octoprint_settings, has_checked_webcam_options, has_checked_firmware_info

    reset_api_cache()
    rpi_id = get_rpid()
    extra = ""

    if not rpi_id:
        # RPI id is empty - get new one from server
        the_web_response = website_ping_update("&request_rpid")
    else:
        if request_settings_next_time:
            extra = "&request_settings"
            request_settings_next_time = False

        if config.getboolean("info", "is_set_up"):
            if num == 0:
                extra += "&first"

            # Check if should request POWER CONTROLLER
            if config.getboolean("settings", "has_power_controller") and not has_checked_power_controller:
                has_checked_power_controller = True
                request = octoprint_api_req("plugin/simplypowercontroller", {"command": "getPSUState"})
                if request is not None:
                    state = "off"
                    if request["isPSUOn"]:
                        state = "on"

                    extra += "&power_controller=" + state

            # Check if should request FILAMENT SENSOR
            if config.getboolean("settings", "has_filament_sensor") and not has_checked_filament_sensor:
                has_checked_filament_sensor = True
                request = octoprint_api_req("plugin/simplyfilamentsensor", {"command": "getState"})
                if request is not None:
                    state = "runout"
                    if request["has_filament"]:
                        state = "loaded"

                    extra += "&filament_sensor=" + state

            # Sync webcam settings with server
            if not has_checked_webcam_options:
                has_checked_webcam_options = True
                if octoprint_settings is not None and "webcam" in octoprint_settings:
                    s_cam = octoprint_settings["webcam"]
                    if "flipH" in s_cam and "flipV" in s_cam and "rotate90" in s_cam:
                        change = False
                        if s_cam["flipH"] != config.getboolean("webcam", "flipH"):
                            change = True
                        elif s_cam["flipV"] != config.getboolean("webcam", "flipV"):
                            change = True
                        elif s_cam["rotate90"] != config.getboolean("webcam", "rotate90"):
                            change = True

                        if change:
                            # Webcam settings in OctoPrint is different from SimplyPrint ones
                            extra += "&webcam_options=" + url_quote(json.dumps({
                                "flipH": s_cam["flipH"],
                                "flipV": s_cam["flipV"],
                                "rotate90": s_cam["rotate90"],
                            }))

        # Actual web request
        the_web_response = website_ping_update("&recv_commands" + extra)

    if the_web_response is not False and the_web_response is not None:
        the_json = False

        try:
            the_json = json.loads(the_web_response.decode("utf-8"))
        except Exception as e:
            log("Failed to parse JSON; " + str(e))

        if not isinstance(the_json, bool) and the_json is not None:
            if not rpi_id:
                # (had) empty RPI id - save new from server
                log("Got RPI id from server")
                if "generated_rpi_id" in the_json:
                    if the_json["generated_rpi_id"]:
                        set_rpi_id(the_json["generated_rpi_id"])
                        return True
                log("Failed to set RPI id from server...")

            if not config.getboolean("info", "is_set_up"):
                # RPI thinks it's not set up, but server does - sync
                if the_json["printer_set_up"]:
                    log("Set to 'is set up'! (2)")
                    set_config_key("info", "is_set_up", "True")
                    set_config_key("info", "temp_short_setup_id", "")

                    # Run "startup" script to send IP, WiFi and such
                    sub_start_script("startup")

                    set_config()
                    return True
            elif not the_json["printer_set_up"]:
                if config.getboolean("info", "is_set_up"):
                    # RPI thinks it's set up, but server doesn't - sync
                    log("Printer is not set up anymore")
                    set_config_key("info", "is_set_up", "False")
                    set_config()
                    return True

            if the_json["status"]:
                p_state = get_printer_state()

                demand_list = the_json["printer_demands"]
                the_settings = the_json["settings"]

                if str(the_settings["times_per_minute"]) != str(times_a_minute):
                    times_a_minute = int(the_settings["times_per_minute"])

                    set_config_key("info", "requests_per_minute", str(times_a_minute))
                    set_config()

                if (has_demand("identify_printer") or has_demand("do_gcode")) and has_demand("gcode_code"):
                    try:
                        for value in demand_list["gcode_code"]:
                            print(octoprint_api_req("printer/command", {"command": value}, True, None, True))
                    except:
                        log("Failed to execute GCODE line(s)")

                # Send OctoPrint api key to server
                if has_demand("send_octoprint_apikey"):
                    website_ping_update("&octoprint_api_key=" + octoprint_apikey())

                # Server is missing details from "startup.py"
                if has_demand("missing_info"):
                    sub_start_script("startup")

                # Check setup state
                if not config.getboolean("info", "is_set_up"):
                    # NOT SET UP!
                    if the_json["locked"]:
                        set_display("Locked")
                    else:
                        # log("Printer is not set up.")
                        if has_demand("printer_set_up"):
                            # Printer has now been set up! Out of setup mode we go
                            log("Set to 'is set up'! (1)")
                            set_config_key("info", "is_set_up", "True")
                            set_config_key("info", "temp_short_setup_id", "")
                            set_config_key("info", "safemode_check_next", "0")
                            set_config()
                            set_display("Set up!", True)
                        else:
                            # Still not set up
                            if config.get("info", "temp_short_setup_id") != the_json["printer_set_up_short_id"]:
                                set_config_key("info", "temp_short_setup_id", the_json["printer_set_up_short_id"])
                                set_config()

                            # Check for safe mode (OctoPrint sometimes starts in safe mode on first boot...)
                            if not has_checked_safemode:
                                has_checked_safemode = True
                                try:
                                    # Don't crash for this...
                                    safemode_check = octoprint_api_req("plugin/pluginmanager")
                                    if safemode_check is not None:
                                        for plugin in safemode_check["plugins"]:
                                            if plugin["safe_mode_victim"]:
                                                # Don't end up in a restart loop...
                                                safe_checks = config.getint("info", "safemode_check_next")
                                                if safe_checks == 0:
                                                    # OctoPrint is in safe mode! Restart!
                                                    log(
                                                        "OctoPrint was in safe mode - probably not on purpose, restarting")
                                                    set_config_key("info", "safemode_check_next", "1")
                                                    set_config()
                                                    os.system("sudo service octoprint restart")
                                                else:
                                                    # Has forced it out of safe mode once, but it's back :/
                                                    log("OctoPrint is STILL in safe mode!")

                                                    if safe_checks >= 10:
                                                        # Has been in safe mode for 10 minutes - try getting it out again!
                                                        log("Has been 10 minutes, trying to get OP out of safe mode")
                                                        set_config_key("info", "safemode_check_next", "0")
                                                        os.system("sudo service octoprint restart")
                                                    else:
                                                        log("Still in safe mode...")
                                                        new_checks = safe_checks + 1
                                                        set_config_key("info", "safemode_check_next", str(new_checks))

                                                    set_config()
                                                break
                                except:
                                    log("Failed to handle safe mode")

                            # If there's a newer version of SimplyPrint; download it right away
                            if check_has_update() == False:
                                return False

                            # Check for missing firmware info (and the important; warnings)
                            if has_demand("missing_firmware_info"):
                                if not has_checked_firmware_info:
                                    has_checked_firmware_info = True
                                    # Disconnect and wait for firmware data
                                    connect_printer(True)
                                else:
                                    connect_printer()

                            set_display(the_json["printer_set_up_short_id"])

                else:
                    # IS SET UP!
                    try:
                        # Set printer details in config
                        config_set = False
                        if config.get("info", "printer_id") != str(the_json["printer_id"]):
                            config_set = True
                            set_config_key("info", "printer_id", str(the_json["printer_id"]))

                        if IS_PY3:
                            the_printer_name = str(the_json["printer_name"]).strip()
                        else:
                            the_printer_name = the_json["printer_name"].encode("utf-8").strip()

                        old_name = config.get("info", "printer_name")
                        if old_name != the_printer_name:
                            config_set = True
                            log("Updating printer name to; " + the_printer_name + " (old was " + old_name + ")")
                            set_config_key("info", "printer_name", the_printer_name.replace("%", "%%"))

                        if config_set:
                            set_config()
                    except Exception as e:
                        log("Failed to update printer name & id in config; " + str(e))

                    if has_demand("printer_settings"):
                        settings_array = demand_list["printer_settings"]
                        if "display" in settings_array:
                            # Display M117 enabled?
                            if "enabled" in settings_array["display"]:
                                is_enabled = "False"
                                if settings_array["display"]["enabled"]:
                                    is_enabled = "True"
                                set_config_key("settings", "display_enabled", is_enabled)

                            # Display branding?
                            if "branding" in settings_array["display"]:
                                is_enabled = "False"
                                if settings_array["display"]["branding"]:
                                    is_enabled = "True"
                                set_config_key("settings", "display_branding", is_enabled)

                            # Display type when printing?
                            if "while_printing_type" in settings_array["display"]:
                                set_config_key("settings", "display_while_printing_type",
                                               str(settings_array["display"]["while_printing_type"]))

                            # Show display status?
                            if "show_status" in settings_array["display"]:
                                is_enabled = "False"
                                if settings_array["display"]["show_status"]:
                                    is_enabled = "True"
                                set_config_key("settings", "display_show_status", is_enabled)

                            # Has power controller?
                            if "has_power_controller" in settings_array:
                                is_enabled = "False"
                                if settings_array["has_power_controller"]:
                                    is_enabled = "True"

                                set_config_key("settings", "has_power_controller", is_enabled)

                            # Has power controller?
                            if "has_filament_sensor" in settings_array:
                                is_enabled = "False"
                                if settings_array["has_filament_sensor"]:
                                    is_enabled = "True"

                                set_config_key("settings", "has_filament_sensor", is_enabled)

                        set_config_key("info", "last_user_settings_sync", settings_array["updated_datetime"])
                        set_config()

                    # Check whether to get settings
                    if the_json["settings_updated"] > config.get("info", "last_user_settings_sync"):
                        request_settings_next_time = True

                    # Is printing
                    if p_state == "Printing":
                        if config.getint("settings", "display_while_printing_type") != 2:
                            if current_job_completion() is not None:
                                set_display("Printing " + str(current_job_completion()) + "%", True)
                            else:
                                set_display("Printing...", True)
                    elif p_state == "Operational" and config.getboolean("settings", "display_show_status"):
                        # Is operational
                        set_display("Ready")
                    elif p_state == "Paused" and config.getboolean("settings", "display_show_status"):
                        # Is paused
                        set_display("Paused", True)

                    if has_demand("system_reboot"):
                        set_display("Rebooting...", True)
                        os.system("shutdown -r now")
                        return True

                    if has_demand("system_shutdown"):
                        set_display("Shutting down", True)
                        os.system("shutdown -h now")
                        return True

                    if has_demand("start_octoprint"):
                        os.system("service octoprint start")

                    if has_demand("shutdown_octoprint"):
                        os.system("service octoprint stop")

                    if has_demand("restart_octoprint"):
                        os.system("sudo service octoprint restart")

                    if has_demand("update_octoprint", False):
                        set_display("Updating OctoPrint", True)
                        # /home/pi/oprint/bin/python2 -m pip --disable-pip-version-check install
                        # https://github.com/foosel/OctoPrint/archive/1.4.0.zip --no-cache-dir
                        # CP: TODO? use https://get.octoprint.org/latest instead of hard coded version
                        # Change it to this:
                        # sys.executable + " -m pip install https://get.octoprint.org/latest"
                        # Which on most systems will result in `/home/pi/oprint/bin/python -m pip install ...`
                        # Useful for if you want to go platform-agnostic :)

                    if has_demand("psu_on") or has_demand("psu_keepalive"):
                        # Turn power controller ON
                        octoprint_api_req("plugin/simplypowercontroller", {"command": "turnPSUOn"}, True)

                    if has_demand("psu_off"):
                        # Turn power controller OFF
                        octoprint_api_req("plugin/simplypowercontroller", {"command": "turnPSUOff"}, True)

                    # Has updated webcam settings
                    if has_demand("webcam_settings_updated", False):
                        log("Got webcam settings update")

                        new_s_cam = {
                            "flipH": "False",
                            "flipV": "False",
                            "rotate90": "False",
                        }

                        try:
                            cam_settings = json.loads(demand_list["webcam_settings_updated"])
                            if "flipH" in cam_settings:
                                if cam_settings["flipH"]:
                                    new_s_cam["flipH"] = "True"
                            if "flipV" in cam_settings:
                                if cam_settings["flipV"]:
                                    new_s_cam["flipV"] = "True"
                            if "rotate90" in cam_settings:
                                if cam_settings["rotate90"]:
                                    new_s_cam["rotate90"] = "True"

                            set_config_key("webcam", "flipH", new_s_cam["flipH"])
                            set_config_key("webcam", "flipV", new_s_cam["flipV"])
                            set_config_key("webcam", "rotate90", new_s_cam["rotate90"])
                            set_config()

                            if "sync" in cam_settings:
                                # Sync these settings with OctoPrint
                                to_post = {
                                    "flipH": False,
                                    "flipV": False,
                                    "rotate90": False,
                                }

                                # This hurts... Thanks Python...
                                if new_s_cam["flipH"] == "True":
                                    to_post["flipH"] = True

                                if new_s_cam["flipV"] == "True":
                                    to_post["flipV"] = True

                                if new_s_cam["rotate90"] == "True":
                                    to_post["rotate90"] = True

                                check = octoprint_api_req("settings", {"webcam": to_post}, True, None, True)
                                if check:
                                    log("Synced webcam settings!")
                                else:
                                    log("Failed to sync webcam settings...")
                        except:
                            log("Failed to update or parse new webcam settings")

                    # Plugin actions - install, uninstall, set settings etc.
                    if has_demand("octoprint_plugin_action", False):
                        installed_plugins = []
                        plugins_txt = os.path.join(dir_path, "sp_installed_plugins.txt")

                        do_restart_octoprint = False

                        # OctoPrint plugin actions!
                        for action in demand_list["octoprint_plugin_action"]:
                            if action["type"] == "install":
                                # Add plugin to "Installed by SimplyPrint" list
                                log("Installing OctoPrint plugin " + action["name"] + "!")
                                installed_plugins.append(action["key"])

                                with io.open(plugins_txt, "a") as myfile:
                                    myfile.write(action["name"] + "\n")

                                # "Notify" plugin of plugins installed through SimplyPrint!
                                sp_plugins = []
                                if os.path.isfile(plugins_txt):
                                    with io.open(plugins_txt) as f:
                                        for line in f:
                                            if len(line) and (line.strip() not in sp_plugins):
                                                sp_plugins.append(line.strip())

                                # Post the new settings to the plugin
                                octoprint_api_req("settings", {
                                    "plugins": {
                                        octoprint_plugin_name: {
                                            "sp_installed_plugins": sp_plugins,
                                        }
                                    }
                                })

                                # Install through pip, and restart OctoPrint
                                print(str(action))

                                pipname = action["pip_name"]

                                command_uninstall = [sys.executable, "-m", "pip", "uninstall", "-y", pipname]
                                process = subprocess.Popen(command_uninstall, stdout=subprocess.PIPE,
                                                           stderr=subprocess.PIPE)
                                stdout, stderr = process.communicate()
                                log("Uninstall command, stdout" + str(stdout.decode("utf-8", errors="replace")))
                                log("Uninstall command, stderr" + str(stderr.decode("utf-8", errors="replace")))

                                command_install = [sys.executable, "-m", "pip", "install", str(action["install_url"])]
                                process2 = subprocess.Popen(command_install, stdout=subprocess.PIPE,
                                                            stderr=subprocess.PIPE)
                                stdout, stderr = process2.communicate()
                                log("Uninstall command, stdout" + str(stdout.decode("utf-8", errors="replace")))
                                log("Uninstall command, stderr" + str(stderr.decode("utf-8", errors="replace")))

                                do_restart_octoprint = True
                            elif action["type"] == "uninstall":
                                sp_plugins = []

                                if os.path.isfile(plugins_txt):
                                    # Get current plugins
                                    log("Uninstalling OctoPrint plugin; " + action["name"])

                                    with io.open(plugins_txt, "r") as f:
                                        for line in f:
                                            stripped_line = line.strip()
                                            if len(line) and stripped_line != action["name"].strip():
                                                if stripped_line not in sp_plugins:
                                                    sp_plugins.append(line.strip())

                                    # Post to the plugin
                                    octoprint_api_req("settings", {
                                        "plugins": {
                                            octoprint_plugin_name: {
                                                "sp_installed_plugins": sp_plugins,
                                            }
                                        }
                                    })

                                    # Set new list not containing the about-to-be-deleted one
                                    with io.open(plugins_txt, "w") as f:
                                        for line in sp_plugins:
                                            f.write(line + "\n")

                                os.system(
                                    "yes | " + sys.executable + " -m pip uninstall \"" + action["pip_name"].replace(
                                        " ", "-") + "\"")
                                do_restart_octoprint = True
                            elif action["type"] == "set_settings":
                                # Update OctoPrint settings (plugin or not)
                                print(installed_plugins)
                                if "plugin_key" in action and action["plugin_key"] in installed_plugins:
                                    # Wait till plugin has actually been installed!
                                    log("Gonna wait until plugin is properly installed to set the settings!")
                                    plugin_settings_awaiting.append(action["settings"])
                                    last_awaiting_plugin_set = time.time()
                                else:
                                    log("Setting some settings right away!")

                                    check = octoprint_api_req("settings", action["settings"], True, None, True)
                                    if check == 200:
                                        log("Settings saved")
                                    else:
                                        log("Failed to set settings right away... Status; " + str(check))
                                        plugin_settings_awaiting.append(action["settings"])
                                        last_awaiting_plugin_set = time.time()

                                if "restart" in action and action["restart"]:
                                    do_restart_octoprint = True

                        # End plugin action loop
                        if do_restart_octoprint:
                            os.system("sudo service octoprint restart")

                        website_ping_update("&plugin_actions_executed")
                    else:
                        # No plugins to install or settings to set
                        process_pending_settings()

                    # Update printer profile
                    if has_demand("set_printer_profile", False):
                        data = {"profile": demand_list["set_printer_profile"]}

                        if octoprint_api_req("printerprofiles/sp_printer", None, True, None, True) == 404:
                            # Printer profile doesn't exist - create it
                            data["profile"]["id"] = "sp_printer"
                            the_return = octoprint_api_req("printerprofiles", data, True, None, True)
                        else:
                            # Printer profile exists - update
                            the_return = octoprint_api_req("printerprofiles/sp_printer", data, True, None, True, True)

                        if the_return == 200:
                            website_ping_update("&type_settings_fetched")
                        else:
                            log("Failed to update printer type settings :/")
                            log(str(the_return))

                    # Sync GCODE profiles (send backups)
                    if has_demand("get_gcode_script_backups"):
                        if not config.getboolean("info", "gcode_scripts_backed_up"):
                            # Check if user has GCODE scripts in OctoPrint that should be backed up
                            current_resume_gcode = ""
                            current_pause_gcode = ""
                            current_cancel_gcode = ""

                            default_cancel_gcode = ";disable motorsM84;disable all heaters{% snippet 'disable_hotends' %}{% snippet 'disable_bed' %};disable fanM106 S0"

                            if "scripts" in octoprint_settings and "gcode" in octoprint_settings["scripts"]:
                                if "afterPrintCancelled" in octoprint_settings["scripts"]["gcode"]:
                                    current_cancel_gcode = octoprint_settings["scripts"]["gcode"]["afterPrintCancelled"]

                                    if current_cancel_gcode.replace(" ", "").replace("\n", "") == default_cancel_gcode:
                                        # Cancel GCODE is the stock - just pretend it's empty
                                        current_cancel_gcode = ""

                                if "beforePrintResumed" in octoprint_settings["scripts"]["gcode"]:
                                    current_resume_gcode = octoprint_settings["scripts"]["gcode"]["beforePrintResumed"]

                                if "afterPrintPaused" in octoprint_settings["scripts"]["gcode"]:
                                    current_pause_gcode = octoprint_settings["scripts"]["gcode"]["afterPrintPaused"]

                            if current_cancel_gcode or current_resume_gcode or current_pause_gcode:
                                # One or all of the GCODE scripts we want to overwrite have values - sync with server!
                                log("Synced local GCODE scripts to SP")
                                website_ping_update("&gcode_scripts_backed_up=" + url_quote(json.dumps({
                                    "cancel_gcode": current_cancel_gcode,
                                    "pause_gcode": current_pause_gcode,
                                    "resume_gcode": current_resume_gcode,
                                })))
                            else:
                                # No backups needed - user has not set anything
                                log("No backups needed - no user modified GCODE scripts")
                                website_ping_update("&no_gcode_script_backup_needed")

                            set_config_key("info", "gcode_scripts_backed_up", "True")
                            set_config()

                    # Sync GCODE profiles (GET scripts!)
                    if has_demand("has_gcode_changes", False):
                        # print(demand_list["has_gcode_changes"])
                        lst = demand_list["has_gcode_changes"]

                        if "cancel" in lst and "pause" in lst and "resume" in lst:
                            try:
                                the_data = {
                                    "scripts": {
                                        "gcode": {
                                            "afterPrintCancelled": "\n".join(
                                                demand_list["has_gcode_changes"]["cancel"]),
                                            "afterPrintPaused": "\n".join(demand_list["has_gcode_changes"]["pause"]),
                                            "beforePrintResumed": "\n".join(demand_list["has_gcode_changes"]["resume"]),
                                        }
                                    }
                                }
                            except:
                                the_data = None

                            if the_data is not None:
                                print(demand_list)

                                the_return = octoprint_api_req("settings", the_data, True, None, True)

                                if the_return == 200:
                                    log("Synced GCODE scripts with server")
                                    website_ping_update("&gcode_scripts_fetched")
                                else:
                                    log("Failed to update OctoPrint settings with new GCODE scripts...")

                    # Take picture - camera stuff
                    if has_demand("take_picture"):
                        get_post_image(demand_list["picture_job_id"])

                    if has_demand("livestream"):
                        print("\n\nStart livestream!\n\n")
                        sub_start_script("image_stream")

                    # Check for updates
                    if check_has_update() == False:
                        return False

                    # Check if should connect to printer
                    if has_demand("connect_printer"):
                        check_connect_printer()

                    # Check if it should disconnect printer
                    if has_demand("disconnect_printer") and p_state != "Offline":
                        connect_printer(True)

                    # Logs
                    if has_demand("send_custom_log"):
                        pass

                    if has_demand("send_octoprint_log"):
                        pass

                    if has_demand("send_octoprint_serial_log"):
                        pass

                    # Print operations
                    if has_demand("stop_print"):
                        set_display("Cancelling...", True)
                        send_job_command("cancel")

                    if has_demand("pause_print"):
                        if p_state != "Paused":
                            set_display("Pausing...", True)
                            send_job_command("pause", "pause")
                    else:
                        if p_state == "Paused":
                            print("STARTING PRINT JOB AGAIN!!!!!")
                            send_job_command("pause", "resume")

                    # START PRINTING (or process file first, but still!)
                    if has_demand("process_file"):
                        # Start a print (job)!
                        return_message = ""
                        file_name = ""

                        if p_state == "Operational":
                            set_display("Preparing...", True)

                            the_download_url = demand_list["print_file"]
                            if has_demand("file_name", False):
                                new_name = demand_list["file_name"]
                            else:
                                new_name = None

                            file_status = process_file_request(the_download_url, new_name)
                            file_name = file_status[2]
                            if not file_status[0]:
                                return_message = file_status[1]
                        else:
                            return_message = "Printer is not ready to print (state is not operational)"

                        if return_message == "":
                            website_ping_update("&file_downloaded=true&filename=" + str(file_name))
                        else:
                            website_ping_update("&file_downloaded=false&not_ready=" + return_message)

                    # Actually start print
                    if has_demand("start_print"):
                        set_display("Starting print", True)
                        octoprint_api_req("job", {"command": "start"})

                return True
            else:
                log("Request not succesful. Message; " + str(the_json["message"]))
        else:
            log("Failed to request website; " + str(the_web_response))
    else:
        # Web request failed
        pass

    return False


def run_requests():
    webrequest_pid()
    print("Starting loop...")

    i = 0  # Skip the last one - cron handles the last by doing it again, so cut it off
    total_requests = 0
    successful_requests = 0
    failed_requests = 0

    dateTimeObj = datetime.now()
    timestampStr = dateTimeObj.strftime("%S")
    seconds_to_run = 60 - int(timestampStr)

    if seconds_to_run > 58:
        seconds_to_run = 58

    print("Gonna run for " + str(seconds_to_run) + "s")
    print(str(times_a_minute) + " times a minute")

    while i < times_a_minute:
        print("Request...")

        if time.time() - start_time < seconds_to_run:  # Don't continue for more than a minute - a new cron job will take over
            the_request = do_the_request(i)
            total_requests += 1

            if the_request:
                successful_requests += 1
            else:
                failed_requests += 1

            if times_a_minute > 1 and times_a_minute - 1 != i:
                time.sleep(60 / times_a_minute)
            i += 1
        else:
            break

    if successful_requests == total_requests:
        log("All requests successful! (" + str(total_requests) + ")")
    else:
        check_connect_printer()

        log(str(failed_requests) + " requests failed, " + str(successful_requests) + " succeeded")
        if has_internet():
            set_display("Requests failed", True)
        else:
            set_display("No internet", True)

    if len(plugin_settings_awaiting) > 0:
        log("Requests are done, but a plugin has been installed which awaits a settings change! Waitin for that")
        while len(plugin_settings_awaiting) > 0:
            print("Trying again...")
            process_pending_settings()
            time.sleep(1)

        log("Settings set!")
