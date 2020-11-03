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
from crontab import CronTab
import os

the_comment = "[SimplyPrint v" + system_version + "]"
the_startup_comment = "[SimplyPrint v" + system_version + " (startup file)]"
the_startup_comment_2 = "[SimplyPrint v" + system_version + " (startup requests)]"
the_oc_update_comment = "[SimplyPrint v" + system_version + " (OctoPrint update checker)]"

command_file = os.path.dirname(os.path.abspath(__file__)) + "/do_webrequest.py"
startup_command_file = os.path.dirname(os.path.abspath(__file__)) + "/startup.py"
startup_command_file_2 = os.path.dirname(os.path.abspath(__file__)) + "/initial_webrequests.py"
octoprint_update_file = os.path.dirname(os.path.abspath(__file__)) + "/octoprint_update_check.py"
the_command = "sudo python3 " + command_file + "  # " + the_comment
startup_command = "sudo python3 " + startup_command_file + "  # " + the_startup_comment
startup_command_2 = "sudo python3 " + startup_command_file_2 + "  # " + the_startup_comment_2
octoprint_update_check = "sudo python3 " + octoprint_update_file + "  # " + the_oc_update_comment


class CronManager:
    def __init__(self):
        self.cron = CronTab(user=True)

        for job in self.cron:
            commentlowr = job.comment.lower()
            if "[simplyprint" in commentlowr:
                if commentlowr not in [the_comment.lower(), the_startup_comment.lower(), the_oc_update_comment.lower()]:
                    print("Remove job!")
                    self.cron.remove(job)

    def add(self, user, command, comment, on_reboot=False, once_a_day=False):
        exist_check = self.cron.find_comment(comment)
        try:
            if is_py_3():
                job = next(exist_check)
            else:
                job = exist_check.next()

            if len(job) > 0:
                print("Cronjob for SimplyPrint check already exists - not creating")
                return True
        except StopIteration:
            pass

        print("Creating cronjob...")

        cron_job = self.cron.new(command=command, user=user)

        if on_reboot:
            cron_job.every_reboot()
        else:
            if not once_a_day:
                cron_job.minute.every(1)
            else:
                cron_job.hour.on(0)
                cron_job.minute.on(0)

        cron_job.enable()
        self.cron.write()
        return True


the_cron = CronManager()
the_cron.add(True, the_command, the_comment)
the_cron.add(True, startup_command, the_startup_comment, True)
the_cron.add(True, startup_command_2, the_startup_comment_2, True)
the_cron.add(True, octoprint_update_check, the_oc_update_comment, False, True)
