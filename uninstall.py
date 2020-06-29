from crontab import CronTab
import os
import subprocess

# Remove cron jobs
cron = CronTab(user=True)

for job in cron:
    print(job.comment.lower())
    if "[simplyprint" in job.comment.lower() and "[simplyprint keep]" not in job.comment.lower():
        cron.remove(job)

cron.write()

tmp_uninstall_script = "/tmp/uninstall_simplyprint.sh"

if os.path.exists(tmp_uninstall_script):
    os.remove(tmp_uninstall_script)

if os.path.exists("/home/pi/simplyprint_rpi_id.txt"):
    os.remove("/home/pi/simplyprint_rpi_id.txt")

if os.path.exists("/tmp/SimplyPrintUpdater.sh"):
    os.remove("/tmp/SimplyPrintUpdater.sh")

if os.path.exists("/tmp/simplypi_ble_service_pid"):
    os.remove("/tmp/simplypi_ble_service_pid")

f = open(tmp_uninstall_script, "a")
f.write("sleep 1\n")
f.write(
    "sudo /home/pi/oprint/bin/python2 -m pip --disable-pip-version-check install SimplyPrint-OctoPrint-Plugin.zip 2>&1\n")
f.write(
    "sudo /home/pi/oprint/bin/python3 -m pip3 --disable-pip-version-check install SimplyPrint-OctoPrint-Plugin.zip 2>&1\n")
f.write("sudo rm -rf /home/pi/SimplyPrint 2>&1\n")
f.write("rm -- \"$0\"\n")
f.close()

subprocess.Popen(["sudo", "bash", tmp_uninstall_script])
