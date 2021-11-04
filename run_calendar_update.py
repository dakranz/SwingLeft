import api_key
import argparse
import datetime
import dropbox
import io
import logging
import os
import re
import shutil
import slack
import subprocess
import time

logger = logging.getLogger(__name__)
success = 0
warnings = 1
errors = 2

_parser = argparse.ArgumentParser()
_parser.add_argument("-c", "--calendar", required=True,
                    help="Name of calendar to update")
_parser.add_argument("-u", "--upload", action="store_true",
                    help="Upload local timestamp files to dropbox and exit")
_parser.add_argument("-d", "--download", action="store_true",
                    help="Download dropbox timestamp files and exit")
_parser.add_argument("-l", "--local", action="store_true",
                    help="Use local timestamp files and do not upload log files to drobbox or send slack messages.")
_parser.add_argument("-y", "--dry_run", action="store_true",
                    help="Do not actually post/update calendar events but log requests.")
args = _parser.parse_args()

dt_re = r'\d\d\d\d-\d\d-\d\d \d\d;\d\d;\d\d'


def dt_to_pathname(dt):
    return dt.strftime("%Y-%m-%d %H;%M;%S")


def delete_old_logs():
    a_week_ago = dt_to_pathname(datetime.datetime.now() - datetime.timedelta(weeks=1))
    dbx = dropbox.dropbox_client.Dropbox(api_key.dropbox_key)
    for entry in dbx.files_list_folder('').entries:
        if re.match(dt_re, entry.name) and (entry.name < a_week_ago):
            logger.info('Deleting %s', entry.name)
            dbx.files_delete('/' + entry.name)


def upload_folder(local_path):
    logger.info('Uploading %s', local_path)
    dbx = dropbox.dropbox_client.Dropbox(api_key.dropbox_key)
    folder = '/' + local_path
    dbx.files_create_folder_v2(folder)
    for path in os.scandir(local_path):
        with open(path.path, 'rb') as f:
            dbx.files_upload(f.read(), folder + '/' + path.name, mode=dropbox.files.WriteMode('overwrite'), mute=True)
    return dbx.sharing_create_shared_link_with_settings(folder).url


def do_dropbox_op(func, filename):
    i = 1
    while True:
        try:
            func(filename)
        except IOError as e:
            logger.info(e)
            if i > 3:
                raise e
            time.sleep(2 ** i)
            i += 1
        else:
            return


def _upload_file(filename):
    logger.info('Uploading %s', filename)
    dbx = dropbox.dropbox_client.Dropbox(api_key.dropbox_key)
    with open(filename, 'rb') as f:
        dbx.files_upload(f.read(), '/' + filename, mode=dropbox.files.WriteMode('overwrite'), mute=True)


def upload_file(filename):
    do_dropbox_op(_upload_file, filename)


def _download_file(filename):
    logger.info('Downloading %s', filename)
    dbx = dropbox.dropbox_client.Dropbox(api_key.dropbox_key)
    dbx.files_download_to_file(filename, '/' + filename)


def download_file(filename):
    do_dropbox_op(_download_file, filename)

# *Failure*: <link|time>
# log contents


def report_results(status, channel, current_time, log_url, log):
    header = "*Calendar upload status: {}* <{}|{}>".format(status, log_url, current_time)
    if status != "Succeeded":
        header = '<!channel> ' + header
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


def do_calendar_update(kind, log_dir, calendar, dry_run):
    status = success
    command = ["python", kind + "_event_feed.py", "-t", "-c", calendar]
    # command = ["python", kind + "_event_feed.py", "--hours", "24", "-c", calendar]
    logger.info('Running: %s', ' '.join(command))
    result = subprocess_run(command)
    log = result.stderr
    print(log)
    with open('{}/{}-feed.log'.format(log_dir, kind), 'w') as out:
        out.write(log)
    if result.returncode != 0 or 'ERROR - ' in log:
        logger.error('Running %s feed failed', kind)
        return errors
    if 'WARNING - ' in log:
        status = warnings
    csv_file = result.stdout.strip()
    if len(csv_file) == 0:
        return status
    if kind == 'slack':
        shutil.move('slack-events.json', log_dir)
    if dry_run:
        command = ["python", "update_calendar.py", "-y", csv_file]
    else:
        command = ["python", "update_calendar.py", csv_file]
    logger.info('Running %s', ' '.join(command))
    result = subprocess_run(command)
    shutil.move(csv_file, log_dir)
    log = result.stderr
    print(log)
    with open('{}/{}-update.log'.format(log_dir, kind), 'w') as out:
        out.write(log)
    if result.returncode != 0 or 'ERROR - ' in log:
        logger.error('Running %s update failed', kind)
        return errors
    if 'WARNING - ' in log:
        status = warnings
    return status


def download_timestamps(calendar):
    download_file(calendar + '-mobilize-timestamp.txt')
    download_file(calendar + '-slack-timestamp.txt')


def upload_timestamps(calendar):
    upload_file(calendar + '-mobilize-timestamp.txt')
    upload_file(calendar + '-slack-timestamp.txt')


def run_calendar_update(calendar, is_local, dry_run):
    global logger
    buf = io.StringIO()
    logger = logging.getLogger(__name__)
    file_handler = logging.FileHandler("run.log", "w")
    logger.setLevel(logging.INFO)
    for handler in [file_handler, logging.StreamHandler(buf), logging.StreamHandler()]:
        logger.addHandler(handler)
    folder_name = dt_to_pathname(datetime.datetime.now())
    logger.info("Log dir: %s", folder_name)
    os.mkdir(folder_name)
    slack_status = mobilize_status = errors
    try:
        if not is_local:
            download_timestamps(calendar)
        slack_status = do_calendar_update('slack', folder_name, calendar, dry_run)
        if slack_status == errors:
            logger.error('Slack update failed')
        mobilize_status = do_calendar_update('mobilize', folder_name, calendar, dry_run)
        if mobilize_status == errors:
            logger.error('Mobilize update failed')
        if not is_local and slack_status != errors and mobilize_status != errors and not dry_run:
            upload_timestamps(calendar)
    except Exception as e:
        logger.error('%s', e)
    shutil.copy('run.log', folder_name)
    if not is_local:
        log_url = ""
        channel = 'automation'
        try:
            delete_old_logs()
            log_url = upload_folder(folder_name)
        except Exception as e:
            logger.error('Log upload failed: %s', e)
            report_results('Uploading logs failed', channel, folder_name, log_url, buf.getvalue())
            return
        if slack_status == errors or mobilize_status == errors:
            report_results('Failed', channel, folder_name, log_url, buf.getvalue())
        elif slack_status == warnings or mobilize_status == warnings:
            report_results('Warnings', channel, folder_name, log_url, buf.getvalue())
        else:
            report_results('Succeeded', channel, folder_name, log_url, None)
    file_handler.close()
    os.remove('run.log')


if __name__ == '__main__':
    if args.upload:
        upload_timestamps(args.calendar)
    elif args.download:
        download_timestamps(args.calendar)
    elif args.dry_run and not args.local:
        print("Dry run option only available with -l.")
        exit(1)
    else:
        run_calendar_update(args.calendar, args.local, args.dry_run)
