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

from datetime import datetime
import argparse
import threading


def run_initial_webrequest():
    dateTimeObj = datetime.now()
    timestampStr = dateTimeObj.strftime("%S")
    if int(timestampStr) < 54:
        print("Running initial web requests")
        from .webrequest import run_requests
        run_requests()
    else:
        print("No need for initial requests - starting any second now")


def run_script(name):
    if name == "install":
        from .crontab_manager import create_cron_jobs
        create_cron_jobs()
        run_initial_webrequest()
    elif name == "startup":
        from .startup import run_startup
        # Startup can hang for a bit, so run as a thread to avoid issues there
        startup_thread = threading.Thread(target=run_startup)
        startup_thread.start()
        webrequest_thread = threading.Thread(target=run_initial_webrequest)
        webrequest_thread.start()
    elif name == "web_request":
        from .webrequest import run_requests
        run_requests()
    elif name == "image_stream":
        from .image_stream import run_stream
        run_stream()
    elif name == "octoprint_update_check":
        from .octoprint_update_check import run_check
        run_check()
    elif name == "uninstall":
        from .uninstall import run_uninstall
        run_uninstall()
    else:
        print("Script not found! Please check and try again.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SimplyPrint Raspberry Pi Helper")
    parser.add_argument("script",
                        default=None,
                        help="The script you want to call: "
                             "install, startup, web_request, image_stream, octoprint_update_check, uninstall")
    args = parser.parse_args()
    run_script(args.script)
