import argparse
import csv
import datetime
from dateutil import parser
import logging
import random
import requests
import shutil
import time

import action_network
import api_key
import the_events_calendar

sba_mobilize_org = '1535'
entry_point = 'https://api.mobilize.us/v1/organizations/' + sba_mobilize_org + '/events'
api_header = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + api_key.mobilize_key}

_parser = argparse.ArgumentParser()
_parser.add_argument("-s", "--start", help="Oldest day (inclusive) to process as Year-Month-Day at midnight")
_parser.add_argument("-y", "--dry_run", action="store_true", help="Process but do not upload.")
_parser.add_argument("-e", "--end", help="Newest day (exclusive) to process as Year-Month-Day at midnight.")
_parser.add_argument("-t", "--timestamp", action="store_true",
                     help="Use value in mobilize-action-network-timestamp.txt as oldest day to process, yesterday"
                          "as newest")
_parser.add_argument("--update_timestamp", action="store_true",
                     help="Update mobilize-timestamp.txt to current time.")
_parser.add_argument("-d", "--debug", action="store_true",
                     help="Log debug info.")


args = _parser.parse_args()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG if args.debug else logging.INFO)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter('%(levelname)s - %(asctime)s - %(message)s'))
logger.addHandler(sh)


def get_event_data(co_hosts, event_owner_email_address, organization_name):
    data = {}
    hosts = []
    if organization_name == 'Swing Blue Alliance' and (len(co_hosts) > 0 or len(event_owner_email_address) > 0):
        hosts = co_hosts.split(sep='|') if len(co_hosts) > 0 else []
        if len(event_owner_email_address) > 0:
            hosts.append(event_owner_email_address)
    data['hosts'] = hosts
    data['attendees'] = []
    return data


def create_event_map():
    event_map = {}
    with open('one_off_event_export.csv', newline='', encoding='utf-8') as ifile:
        reader = csv.reader(ifile)
        iheaders = next(reader)
        eid_index = iheaders.index('id')

        for record in reader:
            if record[eid_index] not in event_map:
                event_map[record[eid_index]] = get_event_data(record[iheaders.index('co_hosts')],
                                                              record[iheaders.index('event_owner_email_address')],
                                                              record[iheaders.index('organization_name')])
    with open('one_off_shift_export.csv', newline='', encoding='utf-8') as ifile:
        reader = csv.reader(ifile)
        iheaders = next(reader)
        email_index = iheaders.index('Email')
        eid_index = iheaders.index('Event ID')
        start_index = iheaders.index('Timeslot start')
        status_index = iheaders.index('Attendance status')
        org_index = iheaders.index('Event organization name')

        for record in reader:
            if record[status_index] == 'CANCELLED' or record[org_index] != 'Swing Blue Alliance':
                continue
            eid = record[eid_index]
            if eid not in event_map:
                print("%s not in map", eid)
                continue
            event_map[eid]['attendees'].append({'start_date': date_to_timestamp(record[start_index]),
                                                'email': record[email_index]})

    return event_map


event_headers = ['id', 'hosts']

attendee_headers = ['Email', 'Event ID', 'Timeslot start']


def add_to_events_field(current_events, new):
    if current_events.count('/') >= 50:
        current_events = current_events[0:current_events.rfind('/')]
    return '/' + new + current_events


def combine(existing, previous):
    existing_count = existing.count('/')
    previous_count = previous.count('/')
    total = previous_count + existing_count
    combined = existing + previous
    if total <= 50:
        return combined
    start = combined.find('/')
    while start >= 0 and total > 1:
        # Start searching from the character after the current match
        start = combined.find('/', start + 1)
        total -= 1
    return combined[0:start]


# Upload records to action network from mobilize shift data. Start and end are as %Y-%m-%d %H:%M:%S
def mobilize_america_to_action_network(updated, dry_run):
    people = {}
    event_records = []
    attendee_records = []
    i = 1
    for event_id, data in create_event_map().items():
        # if i > 5:
        #     break
        # i += 1
        event_records.append([event_id, ' '.join(data['hosts'])])
        for record in data['attendees']:
            # Record participants
            start = record['start_date']
            email = record['email']
            people_entry = people.get(email, None)
            if people_entry is None:
                people[email] = {'events': [], 'events_hosted': set(), 'fields': {}, 'last_event': (0, 0)}
            people_entry = people[email]
            people_entry['events'].append((event_id, start))
            timestamp = people_entry['last_event'][1]
            if start > timestamp:
                people_entry['last_event'] = (event_id, start)
            attendee_records.append([email, event_id, timestamp_to_date_time(start)])
        # Record hosts
        for email in data['hosts']:
            people_entry = people.get(email, None)
            if people_entry is None:
                people[email] = {'events': [], 'events_hosted': set(), 'fields': {},
                                 'last_event': (0, 0)}
            people[email]['events_hosted'].add(str(event_id))

    people_data = []
    records = []
    for email, data in people.items():
        previous_events = ""
        previous_events_hosted = ""
        new_events = data['events']
        new_events.sort(key=lambda x: x[1])
        for e in new_events:
            previous_events = add_to_events_field(previous_events, "{} {}".format(e[0], timestamp_to_date(e[1])))
        for e in data['events_hosted']:
            if e in previous_events_hosted:
                continue
            previous_events_hosted = add_to_events_field(previous_events_hosted, e)
        custom_fields = data['fields']
        last_event = data['last_event'][0]
        if last_event != 0:
            custom_fields["last_event"] = last_event
            custom_fields["last_event_date"] = timestamp_to_date_with_slash(data['last_event'][1])
        custom_fields["Events_Attended"] = previous_events
        custom_fields["Events_Hosted"] = previous_events_hosted
        lookup_data = action_network.get_person(email)
        if lookup_data is None:
            continue
        current_fields = lookup_data.get('custom_fields', None)
        if current_fields is not None:
            if 'last_event' in current_fields and 'last_event' in custom_fields:
                custom_fields.pop('last_event')
            if 'last_event_date' in current_fields and 'last_event_date' in custom_fields:
                custom_fields.pop('last_event_date')
            existing_events = current_fields.get('Events_Attended', None)
            if existing_events is not None:
                custom_fields['Events_Attended'] = combine(existing_events, previous_events)
            existing_events_hosted = current_fields.get('Events_Hosted', None)
            if existing_events_hosted is not None:
                custom_fields['Events_Hosted'] = combine(existing_events_hosted, previous_events_hosted)

        time.sleep(.1)
        records.append([email, custom_fields])
        person_data = {"email_addresses": [{"address": email}], "custom_fields": custom_fields}
        people_data.append({"person": person_data})
    with open('mobilize-event-export.csv', mode='w', newline='', encoding='utf-8') as ofile:
        writer = csv.writer(ofile)
        writer.writerow(event_headers)
        writer.writerows(event_records)
    with open('mobilize-shift-export.csv', mode='w', newline='', encoding='utf-8') as ofile:
        writer = csv.writer(ofile)
        writer.writerow(attendee_headers)
        writer.writerows(attendee_records)
    with open('mobilize-action-network-upload.csv', mode='w', newline='', encoding='utf-8') as ofile:
        writer = csv.writer(ofile)
        writer.writerow(['Email', 'Custom Fields'])
        writer.writerows(records)

    if not dry_run:
        logger.info('Writing live data to Action Network')
    for person in people_data:
        email = person['person']['email_addresses'][0]['address']
        print(email)
        updated.append(email)
        if not dry_run:
            action_network.add_person(person)
            time.sleep(.5)


def date_to_timestamp(s):
    return int(parser.parse(s).timestamp())


def timestamp_to_date_time(timestamp):
    return datetime.datetime.fromtimestamp(float(timestamp)).strftime("%Y-%m-%d %H:%M:%S")


def timestamp_to_date(timestamp):
    return datetime.datetime.fromtimestamp(float(timestamp)).strftime("%Y-%m-%d")


def timestamp_to_date_with_slash(timestamp):
    return datetime.datetime.fromtimestamp(float(timestamp)).strftime("%Y/%m/%d")


def main():
    updated = []
    try:
        mobilize_america_to_action_network(updated, args.dry_run)
        print('Done!')
    except Exception as e:
        print(e)
    with open('updated_emails.txt', 'a') as f:
        f.writelines(updated)


main()
