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
command_file = os.path.dirname(os.path.abspath(__file__)) + "/do_webrequest.py"
startup_command_file = os.path.dirname(os.path.abspath(__file__)) + "/startup.py"
the_command = "sudo python3 " + command_file + "  # " + the_comment
startup_command = "sudo python3 " + startup_command_file + "  # " + the_startup_comment


class CronManager:
    def __init__(self):
        self.cron = CronTab(user=True)

        for job in self.cron:
            if "[simplyprint keep]" in job.comment.lower():
                print("Keep job!")
            else:
                if the_comment.lower() not in job.comment.lower() and the_startup_comment.lower() not in job.comment.lower():
                    print("Remove job!")
                    self.cron.remove(job)

    def add(self, user, command, on_reboot=False):
        global the_comment

        exist_check = self.cron.find_comment(the_comment)
        try:
            if is_py_3():
                job = next(exist_check)
            else:
                job = exist_check.next()

            if len(job) > 0:
                print("Cronjob for SimplyPrint Hub check already exists - not creating")
                return True
        except StopIteration:
            pass

        print("Creating cronjob...")

        cron_job = self.cron.new(command=command, user=user)

        if on_reboot:
            cron_job.every_reboot()
        else:
            cron_job.minute.every(1)

        cron_job.enable()
        self.cron.write()
        # if self.cron.render():
        return True


the_cron = CronManager()
the_cron.add(True, the_command)
the_cron.add(True, startup_command, True)
