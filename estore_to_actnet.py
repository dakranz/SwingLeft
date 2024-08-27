import argparse
import csv
import datetime
from dateutil import parser
import logging
import re
from pprint import pprint
import shutil
import time

import action_network
import google_sheets
import the_events_calendar

_parser = argparse.ArgumentParser()
_parser.add_argument("-s", "--start", help="Oldest record to process.")
_parser.add_argument("-y", "--dry_run", action="store_true", help="Process but do not upload.")
_parser.add_argument("-e", "--end", help="Newest record to process.")
_parser.add_argument("-t", "--timestamp", action="store_true",
                    help="Use value in estore-action-network-timestamp.txt as oldest event to process, current time "
                         "as newest")
_parser.add_argument("-d", "--debug", action="store_true",
                     help="Log debug info.")


args = _parser.parse_args()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG if args.debug else logging.INFO)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
logger.addHandler(sh)


def get_recency(date):
    l = date.split(sep='-')
    year = l[0]
    month = l[1]
    if month >= '10':
        return year + 'Q4'
    if month >= '07':
        return year + 'Q3'
    if month >= '04':
        return year + 'Q2'
    return year + 'Q1'


def create_action_network_tag(event_data, start, role):
    # Add _ at begin and end
    return '_'.join(['', event_data['org'], role, event_data['type'], event_data['state'], get_recency(start), ''])


def get_data(headers, sheet_data):
    name_index = headers.index('Name')
    email_index = headers.index('Email')
    address_index = headers.index('Address')
    phone_index = headers.index('Phone')
    date_index = headers.index('Time')
    products_index = headers.index('Products')
    data = []
    for row in sheet_data:
        name = row[name_index].strip()
        email = row[email_index].strip()
        address = row[address_index].strip()
        # Google sheets leaves off a blank entry at the end of a range. Phone is the last item and is optional.
        if phone_index < len(row):
            phone = row[phone_index].strip()
        else:
            phone = ''
        date = row[date_index].strip()
        if not (name and email and date):
            logger.warning('Warning: bad row %s', row)
            continue
        datum = {}
        datum['date'] = string_to_date_string(date)
        datum['email'] = email
        datum['org'] = 'SBA'
        datum['type'] = 'Mailing'
        state = the_events_calendar.infer_state_tags(row[products_index])
        if state is None or state == 'national':
            datum['state'] = 'National'
        else:
            datum['state'] = the_events_calendar.states[state][0]
        if address:
            zipcode = address.split()[-1]
            if '-' in zipcode:
                zipcode = zipcode[0:5]
        else:
            zipcode = ''
        datum['zip'] = zipcode
        datum['phone'] = phone
        ln_start = name.rfind(' ')
        datum['ln'] = name[ln_start + 1:]
        datum['fn'] = name[0:ln_start]
        # This user is ordering for many people with the same email
        if datum['email'] == 'elizabeth.reingold@gmail.com' and (datum['fn'] != 'Elizabeth' or datum['ln'] != 'Reingold'):
            continue
        data.append(datum)
    return data


# estore date comes from https://docs.google.com/spreadsheets/d/1a7cPSN1AcHaYidhNCiaDmJRWqFKLZdKP56PrefOBIhg/edit#gid=0
estore_sheet_id = '1a7cPSN1AcHaYidhNCiaDmJRWqFKLZdKP56PrefOBIhg'
estore_range = 'Live Order Update from the E-Store!A{}:J{}'


# Upload records to action network from estore data. Start and end are as %Y-%m-%d %H:%M:%S
def estore_to_action_network(start_record, end_record, dry_run):
    people = {}
    tags = set()
    headers = google_sheets.get_sheet_data(estore_sheet_id, estore_range.format(1, 1))[0]
    rows = google_sheets.get_sheet_data(estore_sheet_id, estore_range.format(start_record, end_record))
    data = get_data(headers, rows)

    # Record participants
    for record in data:
        date = record['date']
        new_tag = create_action_network_tag(record, date, 'Organizer')
        tags.add(new_tag)
        email = record['email']
        people_entry = people.get(email, None)
        if people_entry is not None:
            people_entry['tags'].add(new_tag)
        else:
            zip_code = record['zip']
            people[email] = {'fn': record['fn'], 'ln': record['ln'], 'zip': zip_code,
                             'phone': record['phone'], 'tags': set([new_tag])}
    people_data = []
    records = []
    for email, data in people.items():
        add_tags = [tag for tag in data['tags']]
        add_tags.append('Misc: SBA Newsletter Subscriber')
        records.append([email, ','.join(add_tags), data['fn'], data['ln'], data['phone'], data['zip']])
        person_data = {"family_name": data['ln'], "given_name": data['fn'], "email_addresses": [{"address": email}]}
        if data['zip']:
            person_data["postal_addresses"] = [{"postal_code": data['zip']}]
        if data['phone']:
            person_data["phone_numbers"] = [{"number": data['phone']}]
        people_data.append({"person": person_data, "add_tags": add_tags})
    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H;%M;%S")
    out_name = '{}-action-network-upload.csv'.format(current_date)
    with open('estore-action-network-upload.csv', mode='w', newline='', encoding='utf-8') as ofile:
        writer = csv.writer(ofile)
        writer.writerow(['Email', 'Tags', 'First Name', 'Last Name', 'Phone', 'Zipcode'])
        writer.writerows(records)

    # people_data = people_data[0:10]
    # new_tags = set()
    # for person in people_data:
    #     for tag in person['add_tags']:
    #         new_tags.add(tag)
    #
    if not dry_run:
        logger.info('Writing live data to Action Network')
    for tag_name in tags:
        logger.info(tag_name)
        if not dry_run:
            action_network.add_tag(tag_name)
            time.sleep(1)
    for person in people_data:
        logger.info(person['person']['email_addresses'][0]['address'])
        if not dry_run:
            action_network.add_person(person)
            time.sleep(1)
    return len(rows)


def string_to_date_string(s):
    try:
        date_time = datetime.datetime.fromtimestamp(float(s))
    except ValueError:
        date_time = parser.parse(s)
    return date_time.strftime("%Y-%m-%d")


def main():
    if not (args.timestamp or args.start and args.end):
        logger.error('Must specify -t or --start and --end')
        exit(1)
    if args.timestamp:
        with open('estore-to-action-network-recordstamp.txt') as f:
            try:
                start = int(f.read().strip()) + 1
                end = ""
            except FileNotFoundError:
                logger.error('No recordstamp file')
                exit(1)
    else:
        start = int(args.start)
        end = int(args.end)
    logger.info("Start record: %s", start)
    last_record = estore_to_action_network(start, end, args.dry_run) + start - 1
    if args.dry_run:
        return
    if args.timestamp:
        try:
            shutil.copy('estore-to-action-network-recordstamp.txt', 'estore-to-action-network-recordstamp-last.txt')
        except FileNotFoundError:
            pass
        with open('estore-to-action-network-recordstamp.txt', 'w') as f:
            f.write(str(last_record))


if __name__ == '__main__':
    main()