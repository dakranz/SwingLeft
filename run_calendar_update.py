import datetime
import logging
import os
import shutil
import subprocess

logging.basicConfig(level=logging.INFO, handlers=[logging.FileHandler("run.log", "w"), logging.StreamHandler()])


def subprocess_run(command):
    return subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)


def do_calendar_update(kind, log_dir):
    # command = ["python", kind + "_event_feed.py", "-t"]
    command = ["python", kind + "_event_feed.py", "--hours", "24"]
    logging.info('Running: %s', ' '.join(command))
    result = subprocess_run(command)
    with open('{}/{}-feed.log'.format(log_dir, kind), 'w') as out:
        out.write(result.stderr)
    if result.returncode != 0:
        logging.error('Running %s feed failed', kind)
        return
    csv_file = result.stdout.strip()
    if len(csv_file) == 0:
        return
    if kind == 'slack':
        shutil.copy('slack-events.json', log_dir)
    shutil.copy(csv_file, log_dir)
    # command = ["python", "update_calendar.py", csv_file]
    command = ["python", "update_calendar.py", "-c", "-y", csv_file]
    logging.info('Running %s', ' '.join(command))
    result = subprocess_run(command)
    with open('{}/{}-update.log'.format(log_dir, kind), 'w') as out:
        out.write(result.stderr)
    if result.returncode != 0:
        logging.error('Running %s update failed', kind)


def run_calendar_update():
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H;%M;%S")
    logging.info("Log dir: %s", current_time)
    os.mkdir(current_time)
    try:
        do_calendar_update('slack', current_time)
        do_calendar_update('mobilize', current_time)
    except Exception as e:
        print(e)
    shutil.copy('run.log', current_time)


if __name__ == '__main__':
    run_calendar_update()

