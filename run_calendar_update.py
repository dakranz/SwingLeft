import api_key
import datetime
import dropbox
import io
import logging
import os
import shutil
import slack
import subprocess

success = 0
warnings = 1
errors = 2


def upload_folder(local_path):
    logging.info('Uploading %s', local_path)
    dbx = dropbox.dropbox_client.Dropbox(api_key.dropbox_key)
    folder = '/' + local_path
    dbx.files_create_folder_v2(folder)
    for path in os.scandir(local_path):
        with open(path.path, 'rb') as f:
            dbx.files_upload(f.read(), folder + '/' + path.name, mode=dropbox.files.WriteMode('overwrite'), mute=True)
    return dbx.sharing_create_shared_link_with_settings(folder).url


def upload_file(filename):
    logging.info('Uploading %s', filename)
    dbx = dropbox.dropbox_client.Dropbox(api_key.dropbox_key)
    with open(filename, 'rb') as f:
        dbx.files_upload(f.read(), '/' + filename, mode=dropbox.files.WriteMode('overwrite'), mute=True)


def download_file(filename):
    logging.info('Downloading %s', filename)
    dbx = dropbox.dropbox_client.Dropbox(api_key.dropbox_key)
    dbx.files_download_to_file(filename, '/' + filename)


# *Failure*: <link|time>
# log contents

def report_results(status, channel, current_time, log_url, log):
    header = "*Calendar upload status: {}* <{}|{}>".format(status, log_url, current_time)
    blocks = [{"type": "section",
               "text": {"type": "mrkdwn",
                        "text": header}
               }
              ]
    if log is not None:
        blocks.append({"type": "section", "text": {"type": "plain_text", "text": log}})
    slack.post_message(channel, text=header, blocks=blocks)


def subprocess_run(command):
    return subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)


def do_calendar_update(kind, log_dir):
    status = success
    # command = ["python", kind + "_event_feed.py", "-t"]
    command = ["python", kind + "_event_feed.py", "--hours", "2"]
    logging.info('Running: %s', ' '.join(command))
    result = subprocess_run(command)
    log = result.stderr
    with open('{}/{}-feed.log'.format(log_dir, kind), 'w') as out:
        out.write(log)
    if result.returncode != 0 or 'ERROR - ' in log:
        logging.error('Running %s feed failed', kind)
        return errors
    if 'WARNING - ' in log:
        status = warnings
    csv_file = result.stdout.strip()
    if len(csv_file) == 0:
        return status
    if kind == 'slack':
        shutil.move('slack-events.json', log_dir)
    # command = ["python", "update_calendar.py", csv_file]
    command = ["python", "update_calendar.py", "-c", "-y", csv_file]
    logging.info('Running %s', ' '.join(command))
    result = subprocess_run(command)
    shutil.move(csv_file, log_dir)
    log = result.stderr
    with open('{}/{}-update.log'.format(log_dir, kind), 'w') as out:
        out.write(log)
    if result.returncode != 0 or 'ERROR - ' in log:
        logging.error('Running %s update failed', kind)
        return errors
    if 'WARNING - ' in log:
        status = warnings
    return status


def run_calendar_update():
    buf = io.StringIO()
    logging.basicConfig(level=logging.INFO, handlers=[logging.FileHandler("run.log", "w"),
                                                      logging.StreamHandler(buf),
                                                      logging.StreamHandler()])
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H;%M;%S")
    logging.info("Log dir: %s", current_time)
    os.mkdir(current_time)
    slack_status = mobilize_status = errors
    try:
        logging.info("Downloading timestamps")
        download_file('mobilize-timestamp.txt')
        download_file('slack-timestamp.txt')
        slack_status = do_calendar_update('slack', current_time)
        if slack_status == errors:
            logging.error('Slack update failed')
        mobilize_status = do_calendar_update('mobilize', current_time)
        if mobilize_status == errors:
            logging.error('Mobilize update failed')
        if slack_status != errors and mobilize_status != errors:
            logging.info("Uploading timestamps")
            upload_file('mobilize-timestamp.txt')
            upload_file('slack-timestamp.txt')
    except Exception as e:
        logging.error('%s', e)
    shutil.copy('run.log', current_time)
    logging.info('uploading logs')
    log_url = ""
    channel = 'automation-test'
    try:
        log_url = upload_folder(current_time)
    except Exception as e:
        logging.error('Log upload failed: %s', e)
        report_results('Uploading logs failed', channel, current_time, log_url, buf.getvalue())
        return
    if slack_status == errors or mobilize_status == errors:
        report_results('Failed', channel, current_time, log_url, buf.getvalue())
    elif slack_status == warnings or mobilize_status == warnings:
        report_results('Warnings', channel, current_time, log_url, buf.getvalue())
    else:
        report_results('Succeeded', channel, current_time, log_url, None)


if __name__ == '__main__':
    run_calendar_update()
