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

from datetime import datetime
import os

dateTimeObj = datetime.now()
timestampStr = dateTimeObj.strftime("%S")
if int(timestampStr) < 54:
    print("Running initial web requests")
    p = "sudo python3 /home/pi/SimplyPrint/do_webrequest.py"
    os.system(p)
else:
    print("No need for initial requests - starting any second now")
