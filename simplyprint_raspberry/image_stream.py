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

import os
import signal
import time
import io

from .base import get_post_image

dir_path = os.path.join(os.path.expanduser("~"), "simplyprint")


def run_stream():
    # Make sure only one instance is running
    stream_pid_file = os.path.join(dir_path, "stream_pid.txt")
    if os.path.exists(stream_pid_file):
        with io.open(stream_pid_file, "rt", encoding="utf-8") as f:
            s = f.read()
            try:
                os.kill(int(s), signal.SIGSTOP)
            except:
                pass

    with io.open(stream_pid_file, "wt", encoding="utf-8") as file:
        file.write(str(os.getpid()))

    fails = 0
    do_livestream = True
    every = 1
    avg = 0.2
    last_5_avg = []
    first_5 = True

    print("Start streaming to server")

    while do_livestream:
        success = False
        start_time = time.time()
        the_req = get_post_image(None, False)
        if the_req != False and the_req is not None:
            if "livestream" in the_req and the_req["livestream"] is not None:
                if not the_req["livestream"]["active"]:
                    print("Server stopped requesting for livestream")
                    do_livestream = False
                    success = True
                elif the_req["status"]:
                    success = True

                every = the_req["livestream"]["every"]

        if not success:
            fails += 1

            if fails >= 10:
                do_livestream = False
                # Tell server the livestream has failed to start

        req_time = time.time() - start_time

        if do_livestream:
            # sleep until we request again!
            if len(last_5_avg) == 5:
                # time to find the latest average request time!
                avg = sum(last_5_avg) / len(last_5_avg)
                last_5_avg = [req_time]
                first_5 = False
            else:
                last_5_avg.append(req_time)
                if first_5:
                    avg = sum(last_5_avg) / len(last_5_avg)

            sleep_for = every - avg
            if sleep_for <= 0:
                # just in case
                sleep_for = 0.8

            print("Sleeping for " + str(sleep_for) + "s before taking next picture")
            time.sleep(sleep_for)
            print("\n")

    try:
        # Try to delete no matter what - 'os' might not have picked up that the file exists
        os.remove(stream_pid_file)
        pass
    except:
        pass

    print("Ended stream")
