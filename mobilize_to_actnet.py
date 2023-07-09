import argparse
import csv
import datetime
from dateutil import parser
import re
import requests
import shutil
import time

import action_network
import api_key
from pprint import pprint

sba_mobilize_org = '1535'
entry_point = 'https://api.mobilize.us/v1/organizations/' + sba_mobilize_org + '/events'
api_header = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + api_key.mobilize_key}

_parser = argparse.ArgumentParser()
_parser.add_argument("-s", "--start", help="Oldest day to process as Year-Month-Day at midnight")
_parser.add_argument("-y", "--dry_run", action="store_true", help="Process but do not upload.")
_parser.add_argument("-e", "--end", help="Newest day to process as Year-Month-Day at midnight.")
_parser.add_argument("-t", "--timestamp", action="store_true",
                    help="Use value in mobilize-action-network-timestamp.txt as oldest day to process, yesterday"
                         "as newest")
_parser.add_argument("--update_timestamp", action="store_true",
                     help="Update mobilize-timestamp.txt to current time.")

args = _parser.parse_args()


def get_mobilize_contact(event):
    url = '{}/{}'.format(entry_point, event)
    r = requests.get(url, headers=api_header)
    assert r.ok, r.text
    j_data = r.json()
    return j_data['data']['contact']


def get_mobilize_attendances(event):
    url = '{}/{}/attendances?per_page=100'.format(entry_point, event)
    while True:
        r = requests.get(url, headers=api_header)
        assert r.ok, r.text
        j_data = r.json()
        for attendance in j_data['data']:
            yield attendance
        next_url = j_data['next']
        if next_url is None:
            break
        url = next_url


def get_mobilize_events(start, end):
    event_list = []
    url = '{}?per_page=100&timeslot_start=gte_{}&timeslot_end=lt_{}'.format(entry_point, start, end)
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
                  'HOUSE_PARTY': 'Other', 'VOTER_REG': 'PhoneBank', 'TRAINING': 'Other',
                  'FRIEND_TO_FRIEND_OUTREACH': 'Other', 'DEBATE_WATCH_PARTY': 'Other', 'ADVOCACY_CALL': 'PhoneBank',
                  'RALLY': 'Rally', 'TOWN_HALL': 'Other', 'OFFICE_OPENING': 'Other', 'BARNSTORM': 'Other',
                  'SOLIDARITY_EVENT': 'Other', 'COMMUNITY_CANVASS': 'Canvass', 'SIGNATURE_GATHERING': 'Canvass',
                  'CARPOOL': 'Canvass', 'WORKSHOP': 'Other', 'PETITION': 'Other', 'AUTOMATED_PHONE_BANK': 'PhoneBank',
                  'LETTER_WRITING': 'Mailing', 'LITERATURE_DROP_OFF': 'Other', 'VISIBILITY_EVENT': 'Other',
                  'SOCIAL_MEDIA_CAMPAIGN': 'Other', 'POSTCARD_WRITING': 'Mailing', 'OTHER': 'Other'}

states = {"FL": ["FL", "Florida"],
          "GA": ["GA", "Georgia"],
          "NH": ["NH", "New Hampshire"],
          "NC": ["NC", "North Carolina"],
          "PA": ["PA", "Pennsylvania"],
          "WI": ["WI", "Wisconsin"],
          "NY": ["NY", "New York"],
          "VA": ["VA", "Virginia"],
          "OH": ["OH", "Ohio"],
          }


def get_state(text):
    for tag, strings in states.items():
        pattern = '.*\\W{}\\W.*'.format(strings[0])
        if re.search(pattern, text) or strings[1] in text:
            return tag
    return 'National'


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
    data['state'] = get_state(event['description'])
    if data['state'] == 'National':
        data['state'] = get_state(organization_name)
    if data['state'] == 'NH' and (event['title'].lower().find('monthly meeting') >= 0 or
                                  event['description'].lower().find('monthly meeting') >= 0):
        data['type'] = 'Monthly Meeting'
    else:
        data['type'] = event_type_map.get(event['event_type'], 'Other')
    return data


def create_action_network_tag(event_data, start, role):
    # Add | at begin and end
    return '|'.join(['', event_data['org'], role, event_data['type'], event_data['state'], get_recency(start), ''])


event_headers = ['description', 'event_owner_email_address', 'event_type', 'organization_name', 'tags',
                 'modified_at', 'name']

attendee_headers = ['First name', 'Last name', 'Email', 'ZIP', 'Mobile number', 'Event ID', 'Timeslot start',
                    'Attendance status', 'Event organization name']


# Upload records to action network from mobilize shift data. Start and end are as %Y-%m-%d %H:%M:%S
def mobilize_america_to_action_network(start, end, dry_run):
    people = {}
    tags = set()
    event_records = []
    attendee_records = []
    for event in get_mobilize_events(start, end):
        data = get_event_data(event)
        for timeslot in event['timeslots']:
            timeslot_start = timeslot['start_date']
            if start <= timeslot_start < end:
                event_records.append([event['description'], data['hosts'][0] if 'hosts' in data else '',
                                      event['event_type'], event['sponsor']['name'],
                                      '|'.join([tag['name'] for tag in event['tags']]),
                                      timestamp_to_date_time(timeslot_start), event['title']])
        for record in get_mobilize_attendances(event['id']):
            # Record participants
            record_start = record['timeslot']['start_date']
            if record_start < start or record_start >= end:
                continue
            # There is a sponsor field in the attendance record but mobilize for somereason has an extra
            # sponsor key which is none in that record. So use the event's sponsor field.
            if 'CANCELLED' in record['status'] or event['sponsor']['name'] != 'Swing Blue Alliance':
                continue
            new_tag = create_action_network_tag(data, record_start, 'Participant')
            tags.add(new_tag)
            person = record['person']
            email = person['email_addresses'][0]['address']
            people_entry = people.get(email, None)
            if people_entry is not None:
                people_entry['tags'].add(new_tag)
            else:
                zip_code = person['postal_addresses'][0]['postal_code']
                if zip_code and len(zip_code) == 4:
                    zip_code = '0' + zip_code
                people[email] = {'fn': person['given_name'], 'ln': person['family_name'], 'zip': zip_code,
                                 'phone': person['phone_numbers'][0]['number'], 'tags': set([new_tag])}
            attendee_records.append([people[email]['fn'], people[email]['ln'], email, people[email]['zip'],
                                     people[email]['phone'], event['id'], timestamp_to_date_time(record_start),
                                     record['status'], event['sponsor']['name']])
        # Record hosts
        if 'hosts' not in data:
            continue
        # Use modified date to indicate activity by the host
        modified_at = int(event['modified_date'])
        if modified_at <= start or modified_at > end:
            continue
        for email in data['hosts']:
            new_tag = create_action_network_tag(data, modified_at, 'Organizer')
            tags.add(new_tag)
            people_entry = people.get(email, None)
            if people_entry is not None:
                people_entry['tags'].add(new_tag)
            else:
                people[email] = {'tags': set([new_tag])}

    people_data = []
    records = []
    for email, data in people.items():
        add_tags = [tag for tag in data['tags']]
        add_tags.append('Misc: SBA Newsletter Subscriber')
        if len(data) == 1:
            records.append([email, ','.join(add_tags), "", "", "", ""])
            person_data = {"email_addresses": [{"address": email}]}
        else:
            records.append([email, ','.join(add_tags), data['fn'], data['ln'], data['phone'], data['zip']])
            person_data = {"email_addresses": [{"address": email}]}
            if not all([data['fn'], data['ln'], data['zip'], data['phone']]):
                print(email, data)
            if data['ln']:
                person_data["family_name"] = data['ln']
            if data['fn']:
                person_data["given_name"] = data['fn']
            if data['zip']:
                person_data["postal_addresses"] = [{"postal_code": data['zip']}]
            if data['phone']:
                person_data["phone_numbers"] = [{"number": data['phone']}]
        people_data.append({"person": person_data, "add_tags": add_tags})
    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H;%M;%S")
    out_name = '{}-action-network-upload.csv'.format(current_date)
    with open('{}.mobilize-event-export.csv'.format(current_date), mode='w', newline='', encoding='utf-8') as ofile:
        writer = csv.writer(ofile)
        writer.writerow(event_headers)
        writer.writerows(event_records)
    with open('{}.mobilize-shift-export.csv'.format(current_date), mode='w', newline='', encoding='utf-8') as ofile:
        writer = csv.writer(ofile)
        writer.writerow(attendee_headers)
        writer.writerows(attendee_records)
    with open(out_name, mode='w', newline='', encoding='utf-8') as ofile:
        writer = csv.writer(ofile)
        writer.writerow(['Email', 'Tags', 'First Name', 'Last Name', 'Phone', 'Zipcode'])
        writer.writerows(records)
    print(out_name)
    new_tags = tags.difference(set(action_network.get_tags()))

    # people_data = people_data[0:10]
    # new_tags = set()
    # for person in people_data:
    #     for tag in person['add_tags']:
    #         new_tags.add(tag)
    #
    for tag_name in new_tags:
        print(tag_name)
        if not dry_run:
            action_network.add_tag(tag_name)
            time.sleep(.2)
    for person in people_data:
        print(person['person']['email_addresses'][0]['address'])
        if not dry_run:
            action_network.add_person(person)
            time.sleep(.2)


def date_to_timestamp(s):
    return int(parser.parse(s).timestamp())


def timestamp_to_date_time(timestamp):
    return datetime.datetime.fromtimestamp(float(timestamp)).strftime("%Y-%m-%d %H:%M:%S")


def main():
    if not (args.timestamp or args.start and args.end):
        print('Must specify -t or --start and --end')
        exit(1)
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    if args.timestamp:
        with open('mobilize-to-action-network-timestamp.txt') as f:
            try:
                start = date_to_timestamp(f.read().strip())
                end = date_to_timestamp(today)
            except FileNotFoundError:
                print('No timestamp file')
                exit(1)
    else:
        start = date_to_timestamp(args.start)
        end = date_to_timestamp(args.end)
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
