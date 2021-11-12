import argparse
import csv
import datetime
from dateutil import parser
import re
from pprint import pprint
import shutil
import time

import action_network

_parser = argparse.ArgumentParser()
_parser.add_argument("-s", "--start", help="Timestamp or datetime for oldest record to process.")
_parser.add_argument("-y", "--dry_run", action="store_true", help="Process but do not upload.")
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


event_type_map = {'CANVASS': 'Canvass', 'PHONE_BANK': 'PhoneBank', 'TEXT_BANK': 'TextBank',
                  'MEETING': 'Other', 'COMMUNITY': 'Other', 'FUNDRAISER': 'Fundraiser', 'MEET_GREET': 'Other',
                  'HOUSE_PARTY': 'Other', 'VOTER_REG': 'PhoneBank', 'TRAINING': 'Other',
                  'FRIEND_TO_FRIEND_OUTREACH': 'Other', 'DEBATE_WATCH_PARTY': 'Other', 'ADVOCACY_CALL': 'PhoneBank',
                  'RALLY': 'Other', 'TOWN_HALL': 'Other', 'OFFICE_OPENING': 'Other', 'BARNSTORM': 'Other',
                  'SOLIDARITY_EVENT': 'Other', 'COMMUNITY_CANVASS': 'Canvass', 'SIGNATURE_GATHERING': 'Canvass',
                  'CARPOOL': 'Canvass', 'WORKSHOP': 'Other', 'PETITION': 'Other', 'AUTOMATED_PHONE_BANK': 'PhoneBank',
                  'LETTER_WRITING': 'Mailing', 'LITERATURE_DROP_OFF': 'Other', 'VISIBILITY_EVENT': 'Other',
                  'SOCIAL_MEDIA_CAMPAIGN': 'Other', 'POSTCARD_WRITING': 'Mailing', 'OTHER': 'Other'}

states = {"FL": ["FL", "Florida"],
          "GA": ["GA", "Georgia"],
          "NH": ["NH", "New Hampshire"],
          "NC": ["NC", "North Carolina"],
          "PA": ["PA", "Pennsylvania"],
          }


def get_state(text):
    for tag, strings in states.items():
        pattern = '.*\\W{}\\W.*'.format(strings[0])
        if re.match(pattern, text) or strings[1] in text:
            return tag
    return 'National'


def get_event_data(co_hosts, description, event_owner_email_address, event_type, organization_name, tags, created_at):
    data = {}
    if organization_name == 'Swing Blue Alliance' and (len(co_hosts) > 0 or len(event_owner_email_address) > 0):
        hosts = co_hosts.split(sep='|') if len(co_hosts) > 0 else []
        if len(event_owner_email_address) > 0:
            hosts.append(event_owner_email_address)
        data['hosts'] = hosts
        data['created_at'] = created_at
    tags = tags.split(sep='|')
    if 'Org: All In For Nc' in tags:
        organization_name = 'All in for NC'
    elif 'Org: Ma Flip Pa' in tags:
        organization_name = 'MAFlipPA'
    elif organization_name == 'Swing Blue Alliance':
        organization_name = 'SBA'
    data['org'] = organization_name[0:20]
    data['type'] = event_type_map.get(event_type, 'Other')
    data['state'] = get_state(description)
    return data


def create_action_network_tag(event_data, start, role):
    # Add | at begin and end
    return '|'.join(['', event_data['org'], role, event_data['type'], event_data['state'], get_recency(start), ''])


def create_event_map(event_path):
    event_map = {}
    with open(event_path, newline='', encoding='utf-8') as ifile:
        reader = csv.reader(ifile)
        iheaders = next(reader)
        eid_index = iheaders.index('id')

        for record in reader:
            if record[eid_index] not in event_map:
                event_map[record[eid_index]] = get_event_data(record[iheaders.index('co_hosts')],
                                                              record[iheaders.index('description')],
                                                              record[iheaders.index('event_owner_email_address')],
                                                              record[iheaders.index('event_type')],
                                                              record[iheaders.index('organization_name')],
                                                              record[iheaders.index('tags')],
                                                              record[iheaders.index('created_at')][0:10])
    return event_map


# Upload records to action network from mobilize shift data. Start and end are as %Y-%m-%d %H:%M:%S
def mobilize_america_to_action_network(shift_path, event_path, start, end, dry_run):
    event_map = create_event_map(event_path)
    people = {}
    tags = set()
    with open(shift_path, newline='', encoding='utf-8') as ifile:
        reader = csv.reader(ifile)
        iheaders = next(reader)
        fn_index = iheaders.index('first name')
        ln_index = iheaders.index('last name')
        email_index = iheaders.index('email')
        zip_index = iheaders.index('zip')
        phone_index = iheaders.index('phone')
        eid_index = iheaders.index('event id')
        start_index = iheaders.index('start')

        # Record participants
        for record in reader:
            record_start = record[start_index][0:10]
            if record_start < start or record_start >= end:
                continue
            if record[eid_index] not in event_map:
                continue
            new_tag = create_action_network_tag(event_map[record[eid_index]], record_start, 'Participant')
            tags.add(new_tag)
            email = record[email_index]
            people_entry = people.get(email, None)
            if people_entry is not None:
                people_entry['tags'].add(new_tag)
            else:
                zip_code = record[zip_index]
                if len(zip_code) == 4:
                    zip_code = '0' + zip_code
                people[email] = {'fn': record[fn_index], 'ln': record[ln_index], 'zip': zip_code,
                                 'phone': record[phone_index], 'tags': set([new_tag])}
        # Record hosts
        for _, data in event_map.items():
            if 'hosts' not in data:
                continue
            created_at = data['created_at']
            if created_at <= start or created_at > end:
                continue
            for email in data['hosts']:
                new_tag = create_action_network_tag(data, created_at, 'Organizer')
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
            person_data = {"family_name": data['ln'], "given_name": data['fn'], "email_addresses": [{"address": email}],
                           "postal_addresses": [{"postal_code": data['zip']}],
                           "phone_numbers": [{"number": data['phone']}]
                          }
        people_data.append({"person": person_data, "add_tags": add_tags})
    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H;%M;%S")
    out_name = '{}-action-network-upload.csv'.format(current_date)
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


def string_to_date_string(s):
    try:
        date_time = datetime.datetime.fromtimestamp(float(s))
    except ValueError:
        date_time = parser.parse(s)
    return date_time.strftime("%Y-%m-%d")


def main():
    if not (args.timestamp or args.start and args.end):
        print('Must specify -t or --start and --end')
        exit(1)
    if args.timestamp:
        with open('mobilize-to-action-network-timestamp.txt') as f:
            try:
                start = string_to_date_string(f.read().strip())
                end = args.shift_export[0:10]
            except FileNotFoundError:
                print('No timestamp file')
                exit(1)
    else:
        start = string_to_date_string(args.start)
        end = string_to_date_string(args.end)
    mobilize_america_to_action_network(args.shift_export, args.event_export, start, end, args.dry_run)
    if args.dry_run:
        return
    if args.timestamp or args.update_timestamp:
        try:
            shutil.copy('mobilize-to-action-network-timestamp.txt', 'mobilize-to-action-network-timestamp-last.txt')
        except FileNotFoundError:
            pass
        with open('mobilize-to-action-network-timestamp.txt', 'w') as f:
            f.write(args.shift_export[0:10])


# entry_point = 'https://api.mobilize.us/v1/'
# api_header = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + api_key.mobilize_key}
#
#
# def get_mobilize_attendances(event):
#     url = '{}organizations/1535/events/{}/attendances?per_page=100'.format(entry_point, event)
#     while True:
#         print(url)
#         r = requests.get(url, headers=api_header)
#         assert r.ok, r.text
#         j_data = r.json()
#         for attendance in j_data['data']:
#             yield attendance
#         next_url = j_data['next']
#         if next_url is None:
#             break
#         url = next_url


if __name__ == '__main__':
    main()