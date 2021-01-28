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
from crontab import CronTab
import subprocess
import sys
import os
import shutil

def run_uninstall():
    # Remove cron jobs
    cron = CronTab(user=True)

    for job in cron:
        print(job.comment.lower())
        if "[simplyprint" in job.comment.lower() and "[simplyprint keep]" not in job.comment.lower():
            cron.remove(job)

    cron.write()

    # Stop running SimplyPrint scripts
    webrequest_pid(False)

    # Delete local SimplyPrint folder containing logs and stuff
    shutil.rmtree(dir_path, ignore_errors=True)

    # Delete ourselves using pip
    subprocess.Popen([sys.executable, "-m", "pip", "uninstall", "-y", "SimplyPrintRPiSoftware"])
    print("Cron jobs removed and uninstall started")
