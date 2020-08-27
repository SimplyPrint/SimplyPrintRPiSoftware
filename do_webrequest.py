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
import time
import subprocess
import sys

start_time = time.time()
times_a_minute = config.getint("info", "requests_per_minute")

demand_list = None
request_settings_next_time = False


def has_demand(demand, check_true=True):
    global demand_list
    if demand in demand_list:
        if demand_list[demand] or not check_true:
            return True
    return False


def do_the_request():
    global times_a_minute, demand_list, request_settings_next_time

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
                    log("Set to 'is set up'!")
                    set_config_key("info", "is_set_up", "True")

                    # Run "startup" script to send IP, WiFi and such
                    try:
                        subprocess.Popen(str("sudo " + py_prefix() + " /home/pi/SimplyPrint/startup.py"))
                    except:
                        log("Failed to start 'startup' script")

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
                            print(octoprint_api_req("printer/command", {"command": value}))
                    except:
                        log("Failed to execute GCODE line(s)")

                # Send OctoPrint api key to server
                if has_demand("send_octoprint_apikey"):
                    website_ping_update("&octoprint_api_key=" + octoprint_apikey())

                # Server is missing details from "startup.py"
                if has_demand("missing_info"):
                    os.system("sudo " + py_prefix() + " /home/pi/SimplyPrint/startup.py")

                # Check setup state
                if not config.getboolean("info", "is_set_up"):
                    # NOT SET UP!
                    if the_json["locked"]:
                        set_display("Locked")
                    else:
                        # log("Printer is not set up.")
                        if has_demand("printer_set_up"):
                            log("Set to 'is set up'!")
                            set_config_key("info", "is_set_up", "True")
                            set_config()
                            set_display("Set up!", True)
                        else:
                            if config.get("info", "temp_short_setup_id") != the_json["printer_set_up_short_id"]:
                                set_config_key("info", "temp_short_setup_id", the_json["printer_set_up_short_id"])
                                set_config()

                            set_display(the_json["printer_set_up_short_id"])

                else:
                    # IS SET UP!
                    try:
                        # Set printer details in config
                        config_set = False
                        if config.get("info", "printer_id") != str(the_json["printer_id"]):
                            config_set = True
                            set_config_key("info", "printer_id", str(the_json["printer_id"]))

                        the_printer_name = str(the_json["printer_name"]).strip()
                        if config.get("info", "printer_name") != the_printer_name:
                            config_set = True
                            log("Updating printer name to; " + str(the_printer_name))
                            set_config_key("info", "printer_name", the_printer_name)

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
                        os.system("sudo shutdown -r now")

                    if has_demand("system_shutdown"):
                        set_display("Shutting down", True)
                        os.system("sudo shutdown -h now")

                    if has_demand("start_octoprint"):
                        os.system("sudo service octoprint start")

                    if has_demand("shutdown_octoprint"):
                        os.system("sudo service octoprint stop")

                    if has_demand("restart_octoprint"):
                        os.system("sudo service octoprint restart")

                    if has_demand("update_octoprint", False):
                        set_display("Updating OctoPrint", True)
                        # /home/pi/oprint/bin/python2 -m pip --disable-pip-version-check install
                        # https://github.com/foosel/OctoPrint/archive/1.4.0.zip --no-cache-dir

                    if has_demand("octoprint_plugin_action", False):
                        # OctoPrint plugin actions!
                        for action in demand_list["octoprint_plugin_action"]:
                            if action["type"] == "install":
                                # Add plugin to "Installed by SimplyPrint" list
                                log("Installing OctoPrint plugin " + action["name"] + "!")

                                with open("sp_installed_plugins.txt", "a") as myfile:
                                    myfile.write(action["name"])

                                # "Notify" plugin of plugins installed through SimplyPrint!
                                sp_plugins = []
                                if os.path.isfile("sp_installed_plugins.txt"):
                                    with open("sp_installed_plugins.txt") as f:
                                        for line in f:
                                            sp_plugins.append(line)

                                # Post the new settings to the plugin
                                octoprint_api_req("settings", {
                                    "plugins": {
                                        octoprint_plugin_name: {
                                            "sp_installed_plugins": sp_plugins,
                                        }
                                    }
                                })

                                os.system(
                                    "yes | sudo /home/pi/oprint/bin/pip install \"" + action["install_url"] + "\"")
                                os.system("sudo service octoprint restart")
                                pass
                            elif action["type"] == "uninstall":
                                os.system(
                                    "yes | sudo /home/pi/oprint/bin/pip uninstall \"" + action["name"].replace(
                                        " ", "-") + "\"")
                                os.system("sudo service octoprint restart")
                            elif action["type"] == "set_settings":
                                # Update OctoPrint settings (plugin or not)
                                octoprint_api_req("settings", action["settings"])

                                if action["restart"]:
                                    os.system("sudo service octoprint restart")
                            pass
                        pass

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

                    if has_demand("take_picture"):
                        log("Should take picture!")

                        picture_err_msg = ""
                        picture_id = demand_list["picture_job_id"]
                        upl_url = request_url + "api/receive_snapshot.php?request_id=" + picture_id

                        if octoprint_settings is not None:
                            try:
                                if octoprint_settings["webcam"]["webcamEnabled"]:
                                    the_url = octoprint_settings["webcam"]["snapshotUrl"]
                                    new_name = str(picture_id) + ".png"

                                    log("Taking picture...")
                                    the_download = download_file(the_url, new_name)
                                    if the_download[0]:
                                        with open(new_name, "rb") as f:
                                            log("Uploading picture...")
                                            r = requests.post(upl_url, files={"the_file": f})
                                            json_return = r.json()

                                            if json_return is not None:
                                                if json_return["status"]:
                                                    log("Picture taken and uploaded successfully!")
                                                else:
                                                    log("Failed to upload picture; " + str(r.content))
                                            else:
                                                log("Request failed; " + str(r.content))

                                        if os.path.isfile(new_name):
                                            os.remove(new_name)
                                            log("Deleted picture locally")

                                    else:
                                        picture_err_msg = "Download of screenshot wasn't successful; " + the_download[1]
                                else:
                                    picture_err_msg = ""
                            except Exception as e:
                                picture_err_msg = "Failed to take picture or upload it; " + str(e)
                        else:
                            picture_err_msg = "Could not get the OctoPrint settings and therefore not the snapshot URL"

                        if picture_err_msg != "":
                            log("[Take picture {" + picture_id + "}] failed; " + picture_err_msg)
                            get_request(upl_url + "&err_msg=" + picture_err_msg, True)

                    if has_demand("update_system"):
                        # Update SimplyPrint system!
                        log("Updating system...")
                        set_display("Updating...", True)

                        download_url = request_url + "software/update_script.sh"
                        the_filename, file_extension = os.path.splitext(download_url)
                        new_filename = str("system_updater") + str(file_extension)
                        new_file_loc = os.path.join("/tmp/", new_filename)

                        try:
                            if os.path.exists(new_file_loc):
                                os.remove(new_file_loc)
                        except Exception as e:
                            msg = "Failed to remove file at; " + new_file_loc + ". Error; " + str(e)
                            log(msg)
                            website_ping_update("&system_update_failed=" + url_quote(msg))
                            return False

                        clear_installation_files()

                        log("Downloading from; " + download_url)
                        log("Downloading to; " + new_file_loc)
                        the_download = download_file(download_url, new_file_loc, True)
                        if the_download[0]:
                            log("Yay got new install file! - installing!")
                            set_display("Installing...", True)
                            try:
                                subprocess.call(["sudo", "bash", "/tmp/system_updater.sh"])
                            except subprocess.CalledProcessError as e:
                                msg = "Failed to open system updater file. Error; " + str(e)
                                log(msg)
                                website_ping_update("&system_update_failed=" + msg)
                                return False

                            website_ping_update("&system_update_started=true")
                            time.sleep(2)
                            sys.exit()
                        else:
                            set_display("Update failed", True)
                            msg = "Couldn't download file... Got; " + str(the_download[1])
                            log(msg)
                            website_ping_update("&system_update_failed=" + msg)
                            return False

                    if has_demand("connect_printer"):
                        check_connect_printer()

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
                            send_job_command("pause", "resume")

                    # START PRINTING (or process file first, but still!)
                    if has_demand("process_file"):
                        # Start a print (job)!

                        return_message = ""
                        file_name = ""

                        if p_state == "Operational":
                            set_display("Preparing...", True)

                            the_download_url = demand_list["print_file"]
                            file_status = process_file_request(the_download_url)
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


print("Starting loop...")

i = 0  # Skip the last one - cron handles the last by doing it again, so cut it off
total_requests = 0
successful_requests = 0
failed_requests = 0
while i < times_a_minute:
    print("Request...")

    if time.time() - start_time < 58:  # Don't continue for more than a minute - a new cron job will take over
        the_request = do_the_request()
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
