import argparse
import datetime
import requests
import os
import traceback

from apiclient import discovery
from google.oauth2 import service_account

import api_key
import slack


def get_sheet_data(id, range):
    scopes = ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/drive.file",
              "https://www.googleapis.com/auth/spreadsheets"]
    secret_file = os.path.join(os.getcwd(), 'client_secret.json')

    credentials = service_account.Credentials.from_service_account_file(secret_file, scopes=scopes)
    service = discovery.build('sheets', 'v4', credentials=credentials)

    result = service.spreadsheets().values().get(spreadsheetId=id, range=range).execute()
    return result.get('values', [])


def set_sheet_data(id, range, data):
    scopes = ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/drive.file",
              "https://www.googleapis.com/auth/spreadsheets"]
    secret_file = os.path.join(os.getcwd(), 'client_secret.json')

    credentials = service_account.Credentials.from_service_account_file(secret_file, scopes=scopes)
    service = discovery.build('sheets', 'v4', credentials=credentials)
    values = {'values': data}
    result = service.spreadsheets().values().update(spreadsheetId=id, range=range, body=values,
                                                    valueInputOption='RAW').execute()


def clear_sheet_data(id, range):
    scopes = ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/drive.file",
              "https://www.googleapis.com/auth/spreadsheets"]
    secret_file = os.path.join(os.getcwd(), 'client_secret.json')

    credentials = service_account.Credentials.from_service_account_file(secret_file, scopes=scopes)
    service = discovery.build('sheets', 'v4', credentials=credentials)
    result = service.spreadsheets().values().clear(spreadsheetId=id, range=range).execute()


entry_point = 'https://api.mobilize.us/v1/'


def get_api_header(org_id):
    return {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + api_key.mobilize_keys[str(org_id)]}


def get_mobilize_attendances(org_id, event_id):
    url = '{}organizations/{}/events/{}/attendances?per_page=100'.format(entry_point, org_id, event_id)
    while True:
        r = requests.get(url, headers=get_api_header(org_id))
        assert r.ok, r.text
        j_data = r.json()
        for attendance in j_data['data']:
            yield attendance
        next_url = j_data['next']
        if next_url is None:
            break
        url = next_url


# Attendances written to https://docs.google.com/spreadsheets/d/1ekYUPOM564p8ahJTAv7lAg1svvyIrXKuc_tpD392vXk/edit#gid=0
output_sheet_id = '1ekYUPOM564p8ahJTAv7lAg1svvyIrXKuc_tpD392vXk'
output_range_spec = '{}!A:I'
input_sheet_id = '1Z5YUnjqKTYnL7v-T6WqA_CTiAwR5Epp9iI8Lz6KmJIg'
input_range_spec = 'Event Inputs!A:F'


def convert_timestamp(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')


# Input headers: Run Status, Last Update, Event ID, Group ID, Group Name, Description
# Second row is empty for global status. '#' means do not update.
def upload_mobilize_attendances(dry_run):
    inputs = get_sheet_data(input_sheet_id, input_range_spec)
    status_row = inputs[1]
    if len(status_row) > 0 and '#' in status_row[0]:
        return
    row_index = 2
    for row in inputs[2:]:
        row_index += 1
        if len(row) == 0 or '#' in row[0]:
            continue
        timestamp = upload_event_attendances(row[3], row[2], dry_run)
        if not dry_run:
            set_sheet_data(input_sheet_id, 'Event Inputs!B{}:B{}'.format(row_index, row_index), [[timestamp]])


def upload_event_attendances(org_id, event_id, dry_run):
    print(org_id, event_id)
    values = [['First name', 'Last name', 'Phone', 'Email',
               'Status', 'Shift', 'Signup date', 'Modified date', 'Attended']]
    for a in get_mobilize_attendances(org_id, event_id):
        values.append([a['person']['given_name'], a['person']['family_name'], a['person']['phone_numbers'][0]['number'],
                       a['person']['email_addresses'][0]['address'], a['status'],
                       convert_timestamp(a['timeslot']['start_date']),
                       convert_timestamp(a['person']['created_date']),
                       convert_timestamp(a['person']['modified_date']), a['attended']])
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if dry_run:
        print(values[1])
        return timestamp
    clear_sheet_data(output_sheet_id, output_range_spec.format(event_id))
    set_sheet_data(output_sheet_id, output_range_spec.format(event_id), values)
    return timestamp


def report_error(message):
    header = "<!channel> *Mobilize Attendees Upload failed*"
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": header}},
              {"type": "section", "text": {"type": "plain_text", "text": message}}]
    slack.post_message('automation', text=header, blocks=blocks)


parser = argparse.ArgumentParser()
parser.add_argument("-y", "--dry_run", action="store_true", help="Read events but do not update the sheet.")
parser.add_argument("-r", "--report", action="store_true", help="Report errors to slack.")
args = parser.parse_args()


def main():
    try:
        upload_mobilize_attendances(args.dry_run)
    except Exception as e:
        err_message = traceback.format_exc()
        if args.report:
            report_error(err_message)
        else:
            print(err_message)


if __name__ == '__main__':
    main()
