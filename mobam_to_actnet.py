import argparse
import csv
import datetime
from dateutil import parser
import shutil

import action_network

_parser = argparse.ArgumentParser()
_parser.add_argument("-s", "--start", help="Timestamp or datetime for oldest record to process.")
_parser.add_argument("-e", "--end", help="Timestamp or datetime for newest record to process.")
_parser.add_argument("-t", "--timestamp", action="store_true",
                    help="Use value in mobilize-action-network-timestamp.txt as oldest event to process, current time "
                         "as newest")
_parser.add_argument("shift_export",
                    help="Shift export csv file from mobilize.")
_parser.add_argument("event_export",
                    help="Event export csv file from mobilize.")
_parser.add_argument("-u", "--update_timestamp", action="store_true",
                    help="Update mobilize-action-network-timestamp.txt to current time.")
args = _parser.parse_args()


def create_event_map(event_path):
    event_map = {}
    with open(event_path, newline='', encoding='utf-8') as ifile:
        reader = csv.reader(ifile)
        iheaders = next(reader)
        tags_index = iheaders.index('tags')
        eid_index = iheaders.index('id')

        for record in reader:
            if record[eid_index] not in event_map:
                event_map[record[eid_index]] = {'tags': set(record[tags_index].split(sep='|'))}
    return event_map


# Upload records to action network from mobilize shift data. Start and end are as %Y-%m-%d %H:%M:%S
def mobilize_america_to_action_network(shift_path, event_path, start, end):
    event_map = create_event_map(event_path)
    people = {}
    with open(shift_path, newline='', encoding='utf-8') as ifile:
        records = []
        reader = csv.reader(ifile)
        iheaders = next(reader)
        fn_index = iheaders.index('first name')
        ln_index = iheaders.index('last name')
        email_index = iheaders.index('email')
        zip_index = iheaders.index('zip')
        phone_index = iheaders.index('phone')
        eid_index = iheaders.index('event id')
        start_index = iheaders.index('start')

        for record in reader:
            if record[start_index] <= start or record[start_index] > end:
                continue
            print(record[start_index])
            new_tags = set(event_map[record[eid_index]]['tags'])
            email = record[email_index]
            people_entry = people.get(email, None)
            if people_entry is not None:
                people_entry['tags'].update(new_tags)
            else:
                zip_code = record[zip_index]
                if len(zip_code) == 4:
                    zip_code = '0' + zip_code
                people[email] = {'fn': record[fn_index], 'ln': record[ln_index], 'zip': zip_code,
                                 'phone': record[phone_index], 'tags': new_tags}
    for email, data in people.items():
        print(email, data['fn'], data['ln'], data['phone'], data['zip'], data['tags'])
        person = {"person": {"family_name": data['ln'],
                             "given_name": data['fn'],
                             "email_addresses": [{"address": email}],
                             "custom_fields": {"Phone": data['phone']}
                             },
                  "add_tags": [tag for tag in data['tags']]
                  }


def string_to_date_string(s):
    try:
        date_time = datetime.datetime.fromtimestamp(float(s))
    except ValueError:
        date_time = parser.parse(s)
    return date_time.strftime("%Y-%m-%d %H:%M:%S")


def main():
    if not (args.timestamp or args.start and args.end):
        print('Must specify -t or --start and --end')
        exit(1)
    now = datetime.datetime.now().timestamp()
    if args.timestamp:
        with open('mobilize-action-network-timestamp.txt') as f:
            try:
                start = string_to_date_string(f.read().strip())
                end = string_to_date_string(now)
            except FileNotFoundError:
                print('No timestamp file')
                exit(1)
    else:
        start = string_to_date_string(args.start)
        end = string_to_date_string(args.end)
    mobilize_america_to_action_network(args.shift_export, args.event_export, start, end)
    if args.timestamp or args.update_timestamp:
        shutil.copy('mobilize-action-network-timestamp.txt', 'mobilize-action-network-timestamp-last.txt')
        with open('mobilize-action-network-timestamp.txt', 'w') as f:
            f.write(str(now))


if __name__ == '__main__':
    main()
