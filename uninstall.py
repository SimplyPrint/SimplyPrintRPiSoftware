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

tmp_uninstall_script = "/tmp/uninstall_simplprint.sh"

# TODO; kill all running SimplyPrint scripts

if os.path.exists(tmp_uninstall_script):
    os.remove(tmp_uninstall_script)

f = open(tmp_uninstall_script, "a")
f.write("sleep 1\n")
f.write("cd /\n")
f.write("sudo rm -f /home/pi/simplyprint_rpi_id.txt\n")
f.write("sudo rm -f /tmp/SimplyPrintUpdater.sh\n")
f.write("sudo rm -f /tmp/simplypi_ble_service_pid\n")
f.write("yes | sudo /home/pi/oprint/bin/pip uninstall SimplyPrint\n")
f.write("sudo rm -rf /home/pi/SimplyPrint\n")
f.write("sudo service octoprint restart\n")
f.write("printf \"SimplyPrint uninstalled - we're sad to see you go! :(\"\n")
f.write("rm -- \"$0\"\n")
f.write("exit 0\n")
f.close()

subprocess.Popen(["sudo", "bash", tmp_uninstall_script])
print("Cron jobs removed and uninstall script started")
