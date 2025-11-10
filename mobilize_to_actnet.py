import argparse
import csv
import datetime
from dateutil import parser
import logging
import re
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
sh.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
logger.addHandler(sh)

skip_list = [648802]


def get_mobilize_contact(event):
    url = '{}/{}'.format(entry_point, event)
    r = requests.get(url, headers=api_header)
    assert r.ok, r.text
    j_data = r.json()
    return j_data['data']['contact']


def get_mobilize_attendances(event):
    # play with sleeps to avoid rate limit issues
    url = '{}/{}/attendances?per_page=100'.format(entry_point, event)
    while True:
        r = requests.get(url, headers=api_header)
        if r.status_code == 429:
            # rate limit
            time.sleep(5)
            continue
        assert r.ok, r
        j_data = r.json()
        for attendance in j_data['data']:
            yield attendance
        next_url = j_data['next']
        if next_url is None:
            break
        url = next_url
        time.sleep(.1)


def get_mobilize_events(start, end):
    event_list = []
    url = '{}?visibility=PRIVATE&visibility=PUBLIC&per_page=100&timeslot_start=gte_{}&timeslot_end=lt_{}'.format(entry_point, start, end)
    while True:
        r = requests.get(url, headers=api_header)
        assert r.ok, r.text
        j_data = r.json()
        for event in j_data['data']:
            browser_url = event['browser_url']
            if browser_url is not None:
                event_list.append(event)
        next_url = j_data['next']
        if next_url is None:
            break
        url = next_url
    return event_list


def get_recency(event_time):
    date_time = datetime.datetime.fromtimestamp(float(event_time))
    date = date_time.strftime("%Y-%m-%d")
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


event_type_map = {'CANVASS': 'Canvass', 'PHONE_BANK': 'PhoneBank', 'TEXT_BANK': 'TextBank',
                  'MEETING': 'Other', 'COMMUNITY': 'Other', 'FUNDRAISER': 'Fundraiser', 'MEET_GREET': 'Other',
                  'HOUSE_PARTY': 'Other', 'VOTER_REG': 'Canvass', 'TRAINING': 'Other',
                  'FRIEND_TO_FRIEND_OUTREACH': 'Other', 'DEBATE_WATCH_PARTY': 'Other', 'ADVOCACY_CALL': 'PhoneBank',
                  'RALLY': 'Rally', 'TOWN_HALL': 'Other', 'OFFICE_OPENING': 'Other', 'BARNSTORM': 'Other',
                  'SOLIDARITY_EVENT': 'Other', 'COMMUNITY_CANVASS': 'Canvass', 'SIGNATURE_GATHERING': 'Canvass',
                  'CARPOOL': 'Canvass', 'WORKSHOP': 'Other', 'PETITION': 'Other', 'AUTOMATED_PHONE_BANK': 'PhoneBank',
                  'LETTER_WRITING': 'Mailing', 'LITERATURE_DROP_OFF': 'Other', 'VISIBILITY_EVENT': 'Other',
                  'SOCIAL_MEDIA_CAMPAIGN': 'Other', 'POSTCARD_WRITING': 'Mailing', 'OTHER': 'Other'}


def get_event_data(event):
    data = {}
    organization_name = event['sponsor']['name']
    if organization_name == 'Swing Blue Alliance':
        contact = get_mobilize_contact(event['id'])
        if contact:
            hosts = [contact['email_address']]
            data['hosts'] = hosts
    tags = [tag['name'] for tag in event['tags']]
    if 'Org: All In For Nc' in tags:
        organization_name = 'All in for NC'
    elif 'Org: Ma Flip Pa' in tags:
        organization_name = 'MAFlipPA'
    elif organization_name == 'Swing Blue Alliance':
        organization_name = 'SBA'
    data['org'] = organization_name[0:20]
    state = the_events_calendar.get_mobilize_state_tags(event['tags'])
    if state is None:
        state = the_events_calendar.infer_state_tags(event['description'])
    if state is None:
        state = the_events_calendar.infer_state_tags(organization_name)
    if state is None or state == 'national':
        data['state'] = 'National'
    else:
        data['state'] = the_events_calendar.states[state][0]
    if data['state'] == 'NH' and (event['title'].lower().find('monthly meeting') >= 0 or
                                  event['description'].lower().find('monthly meeting') >= 0):
        data['type'] = 'Monthly Meeting'
    # Voter reg events are assumed to be phone banks if virtual, else canvass as in the event type map.
    elif event['event_type'] == 'VOTER_REG' and event['is_virtual']:
        data['type'] = 'PhoneBank'
    else:
        data['type'] = event_type_map.get(event['event_type'], 'Other')
    return data


def create_action_network_tag(event_data, start, role):
    # Add _ at begin and end
    return '_'.join(['', event_data['org'], role, event_data['type'], event_data['state'], get_recency(start), ''])


event_headers = ['description', 'event_owner_email_address', 'event_type', 'organization_name', 'tags',
                 'start', 'url', 'name']

attendee_headers = ['First name', 'Last name', 'Email', 'ZIP', 'Mobile number', 'Event ID', 'Timeslot start',
                    'Attendance status', 'Event organization name']


def add_action_network_tags_and_fields(people_entry, event):
    # Add any Action Network tags from the event which start with '#AN:'
    for tag in event['tags']:
        tag_name = tag['name']
        if tag_name.startswith('#an:'):
            people_entry['tags'].add(tag_name[4:])
        elif tag_name.startswith('#anf:'):
            (key, value) = tag_name[5:].split('=')
            people_entry['fields'][key] = value


def add_to_events_field(current_events, new):
    if current_events.count('/') >= 50:
        current_events = current_events[0:current_events.rfind('/')]
    return '/' + new + current_events


# Upload records to action network from mobilize shift data. Start and end are as %Y-%m-%d %H:%M:%S
def mobilize_america_to_action_network(start, end, dry_run):
    people = {}
    tags = set()
    event_records = []
    attendee_records = []
    for event in get_mobilize_events(start, end):
        if event['id'] in skip_list:
            logger.info('Skipping: %s', event['id'])
            continue
        data = get_event_data(event)
        for timeslot in event['timeslots']:
            timeslot_start = timeslot['start_date']
            if start <= timeslot_start < end:
                event_records.append([event['description'], data['hosts'][0] if 'hosts' in data else '',
                                      event['event_type'], event['sponsor']['name'],
                                      '_'.join([tag['name'] for tag in event['tags']]),
                                      timestamp_to_date_time(timeslot_start), event['browser_url'], event['title']])
        for record in get_mobilize_attendances(event['id']):
            # Record participants
            record_start = record['timeslot']['start_date']
            if record_start < start or record_start >= end:
                continue
            # There is a sponsor field in the attendance record but mobilize for somereason has an extra
            # sponsor key which is none in that record. So use the event's sponsor field.
            if record['status'] is None or 'CANCELLED' in record['status'] or event['sponsor']['name'] != 'Swing Blue Alliance':
                continue
            new_tag = create_action_network_tag(data, record_start, 'Participant')
            tags.add(new_tag)
            person = record['person']
            if len(person['email_addresses']) == 0:
                continue
            email = person['email_addresses'][0]['address']
            people_entry = people.get(email, None)
            if people_entry is not None:
                people_entry['tags'].add(new_tag)
                if 'fn' not in people_entry:
                    # First instance of this person was from host record that only contains email
                    people_entry['fn'] = person['given_name']
                    people_entry['ln'] = person['family_name']
                    zip_code = person['postal_addresses'][0]['postal_code']
                    if zip_code and len(zip_code) == 4:
                        zip_code = '0' + zip_code
                    people_entry['zip'] = zip_code
                    people_entry['phone'] = person['phone_numbers'][0]['number']
            else:
                zip_code = person['postal_addresses'][0]['postal_code']
                if zip_code and len(zip_code) == 4:
                    zip_code = '0' + zip_code
                people[email] = {'fn': person['given_name'], 'ln': person['family_name'], 'zip': zip_code,
                                 'phone': person['phone_numbers'][0]['number'], 'tags': set([new_tag]),
                                 'events': [], 'events_hosted': set(), 'fields': {}, 'last_event': (0, 0)}
            people_entry = people[email]
            add_action_network_tags_and_fields(people_entry, event)
            people_entry['events'].append((event['id'], record_start))
            timestamp = people_entry['last_event'][1]
            if start > timestamp:
                people_entry['last_event'] = (event['id'], start)
            attendee_records.append([people[email]['fn'], people[email]['ln'], email, people[email]['zip'],
                                     people[email]['phone'], event['id'], timestamp_to_date_time(record_start),
                                     record['status'], event['sponsor']['name']])
        # Record hosts
        if 'hosts' not in data:
            continue
        # Use modified date to indicate activity by the host
        modified_at = int(event['modified_date'])
        # if modified_at <= start or modified_at > end:
        #     continue
        for email in data['hosts']:
            new_tag = create_action_network_tag(data, modified_at, 'Organizer')
            tags.add(new_tag)
            people_entry = people.get(email, None)
            if people_entry is not None:
                people_entry['tags'].add(new_tag)
            else:
                people[email] = {'tags': set([new_tag]), 'events': [], 'events_hosted': set(), 'fields': {},
                                 'last_event': (0, 0)}
            people[email]['events_hosted'].add(str(event['id']))

    people_data = []
    records = []
    for email, data in people.items():
        add_tags = [tag for tag in data['tags']]
        for tag in add_tags:
            if '_Mailing_' in tag:
                add_tags.append('Interest: Postcard/Letter')
                break
        lookup_data = action_network.get_person(email)
        time.sleep(.25)
        previous_events = ""
        previous_events_hosted = ""
        if lookup_data and 'custom_fields' in lookup_data:
            previous_events = lookup_data['custom_fields'].get('Events_Attended', "")
            previous_events_hosted = lookup_data['custom_fields'].get('Events_Hosted', "")
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
        custom_fields["Events_Attended"] = previous_events
        custom_fields["Events_Hosted"] = previous_events_hosted
        if 'fn' not in data:
            # host only
            records.append([email, ','.join(add_tags), "", "", "", "", custom_fields])
            person_data = {"email_addresses": [{"address": email}], "custom_fields": custom_fields}
        else:
            records.append([email, ','.join(add_tags), data['fn'], data['ln'], data['phone'], data['zip'],
                            custom_fields])
            person_data = {"email_addresses": [{"address": email}], "custom_fields": custom_fields}
            # if not all([data['fn'], data['ln'], data['zip'], data['phone']]):
            #     logger.info('%s %s', email, data)
            if data['ln']:
                person_data["family_name"] = data['ln']
            if data['fn']:
                person_data["given_name"] = data['fn']
            if data['zip']:
                person_data["postal_addresses"] = [{"postal_code": data['zip']}]
            if data['phone']:
                person_data["phone_numbers"] = [{"number": data['phone']}]
        people_data.append({"person": person_data, "add_tags": add_tags})
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
        writer.writerow(['Email', 'Tags', 'First Name', 'Last Name', 'Phone', 'Zipcode', 'Custom Fields'])
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


def date_to_timestamp(s):
    return int(parser.parse(s).timestamp())


def timestamp_to_date_time(timestamp):
    return datetime.datetime.fromtimestamp(float(timestamp)).strftime("%Y-%m-%d %H:%M:%S")


def timestamp_to_date(timestamp):
    return datetime.datetime.fromtimestamp(float(timestamp)).strftime("%Y-%m-%d")


def main():
    if not (args.timestamp or args.start and args.end):
        logger.error('Must specify -t or --start and --end')
        exit(1)
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    if args.timestamp:
        with open('mobilize-to-action-network-timestamp.txt') as f:
            try:
                start = date_to_timestamp(f.read().strip())
                end = date_to_timestamp(today)
            except FileNotFoundError:
                logger.error('No timestamp file')
                exit(1)
    else:
        start = date_to_timestamp(args.start)
        end = date_to_timestamp(args.end)
    logger.info("Start: %s End: %s", timestamp_to_date(start), timestamp_to_date(end))
    mobilize_america_to_action_network(start, end, args.dry_run)
    if args.dry_run:
        return
    if args.timestamp or args.update_timestamp:
        try:
            shutil.copy('mobilize-to-action-network-timestamp.txt', 'mobilize-to-action-network-timestamp-last.txt')
        except FileNotFoundError:
            pass
        with open('mobilize-to-action-network-timestamp.txt', 'w') as f:
            f.write(today)


main()
