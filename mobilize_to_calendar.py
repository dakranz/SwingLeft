import csv
import datetime
import os
import re
import requests
import sys
import time

from pprint import pprint

entry_point = 'https://api.mobilize.us/v1/'
api_header = {'Content-Type': 'application/json'}

state_categories = {'RI': 'rhode-island-events',
                    'VT': 'vermont-events',
                    'CT': 'connecticut-events',
                    'ME': 'maine-events-2'
                   }

other_states = 'outside-new-england'

# latitude grows south to north
# longitude grows west to east
regions = [{'slug': 'metro-boston-events',
            'north': 42.416126,
            'south': 42.255709,
            'west': -71.271331
            },
           {'slug': 'north-boston-suburbs-events',
            'north': 42.570831,
            'west': -71.271331,
            'south': 42.416126
            },
           {'slug': 'south-boston-suburbs-events',
            'south': 42.125123,
            'west': -71.271331,
            'north': 42.255709
            },
           {'slug': 'west-boston-suburbs-events',
            'west': -71.656497,
            'north': 42.570831,
            'south': 42.125123,
            'east': -71.271331
            },
           {'slug': 'cape-cod-events',
            'north': 41.771848,
            'west': -70.549556
            },
           {'slug': 'central-mass-events',
            'west': -72.512137,
            'east': -71.656497
            },
           {'slug': 'northern-mass',
            'west': -71.656497,
            'south': 42.570831
            },
           {'slug': 'southern-mass-events',
            'west': -71.656497,
            'north': 42.125123,
            'east': -70.549556
            },
           {'slug': 'western-mass-events',
            'east': -72.512137}
           ]


# Matching will be case-sensitive iff a search term has an uppercase char
event_tags = {"vote-by-mail": ["vote by mail", 'VBM', "vote-by-mail"],
              "joe-biden": [" biden", "biden "],
              "voter-suppression": ["supression", "protecti", "watcher"],
              "voter-registration": ["reclaim our vote", "ROV", "registration", "register vote"],
              "gotv": ["get out the vote", "gotv"],
              "state-races": ["Friel", "Shulman", "Knoll", "Rodas", "Branco", "Kassa", "Diaz", "Scott", "Williams",
                              "Iovino", "Zrinski", "Sigman", "Bonfiglio", "Gonzalez", "Jackson", "Pulver",
                              "Plotkin", "Steele", "Slomski"],
              "senate-races": ["Cunningham", "Gideon", "Greenfield", "Hickenlooper", "Kelly", "Hegar", "Harrison",
                               "Mcgrath", "Jones", "Peters", "Bullock"]
              }

activities = {"canvassing": ["canvas"],
              "phone-calls": ["phone"],
              "postcards-letters": ["letter", "postcard", "post card", "pick up", "pick up", "pick-up"],
              "texting": ["texting"],
              "fundraiser": ["fundrai"],
              "training": ["training"],
              "briefing": ["briefing"]
              }

states = {"arizona-events": ["AZ", "Arizona"],
          "colorado-events": ["CO", "Colorado"],
          "florida-events": ["FL", "Florida"],
          "georgia-events": ["GA", "Georgia"],
          "iowa-events": ["IA", "Iowa"],
          "maine-events": ["ME", "Maine"],
          "michigan-events": ["MI", "Michigan"],
          "north-carolina-events": ["NC", "North Carolina"],
          "ohio-events": ["OH", "Ohio"],
          "pennsylvania-events": ["PA", "Pennsylvania"],
          "texas-events": ["TX", "Texas"],
          "wisconsin-events": ["WI", "Wisconsin"]
          }


def add_state_categories(category_list, text):
    state_list = []
    for category, strings in states.items():
        pattern = '.*\\W{}\\W.*'.format(strings[0])
        if re.match(pattern, text) or strings[1] in text:
            state_list.append(category)
    if len(state_list) == 1:
        category_list.append(state_list[0])
    elif len(state_list) >=2:
        print("Multiple states:", state_list)
        category_list.extend(state_list)


def add_activity_categories(category_list, text, title):
    text = text.lower()
    added = False
    for category, strings in activities.items():
        for s in strings:
            if s in text:
                category_list.append(category)
                added = True
                break
    if 'phone-calls' in category_list and 'training' in category_list and 'training' not in title:
        category_list.remove('training')


def add_tags(tag_list, text):
    lc_text = text.lower()
    for tag, strings in event_tags.items():
        for s in strings:
            if s in (lc_text if s.islower() else text):
                tag_list.append(tag)
                break


def get_ma_region(latitude, longitude):
    for region in regions:
        if 'west' in region and longitude < region['west']:
            continue
        if 'east' in region and longitude > region['east']:
            continue
        if 'south' in region and latitude < region['south']:
            continue
        if 'north' in region and latitude > region['north']:
            continue
        return region['slug']
    return None


def get_ma_region_by_location(location, city):
    if city == "Falmouth":
        # Falmouth defies a broad rectangular cape region, too far West
        return 'cape-cod-events'
    latitude = float(location['latitude'])
    longitude = float(location['longitude'])
    return get_ma_region(latitude, longitude)


def get_ma_region_by_zip(zip):
    latitude, longitude = get_location_from_zip(zip)
    if latitude is None:
        return None
    return get_ma_region(latitude, longitude)


zip_geo_data = None


def get_location_from_zip(zip):
    global zip_geo_data
    if zip_geo_data is None:
        load_zip_geo_data()
    if zip in zip_geo_data:
        return zip_geo_data[zip]
    return None, None


def load_zip_geo_data():
    global zip_geo_data
    zip_geo_data = {}
    with open('us-zip-code-latitude-and-longitude.csv') as ifile:
        reader = csv.reader(ifile)
        in_headers = next(reader)
        for record in reader:
            zip_geo_data['0' + record[0]] = (float(record[1]), float(record[2]))


def find_index(items, key):
    try:
        return items.index(key)
    except ValueError:
        return -1


def get_tracking_event_type(categories):
    if 'fundraiser' in categories:
        return 'Fundraiser'
    if 'postcards-letters' in categories:
        return 'Postcard'
    if 'phone-calls' in categories:
        return 'Phone Bank'
    if 'texting' in categories:
        return 'Texting'
    if 'training-briefings' in categories:
        return 'Training'
    return ''


def get_tracking_event_subtype(tags):
    if 'vote-by-mail' in tags:
        return 'VBM'
    if 'joe-biden' in tags:
        return 'Biden'
    if 'voter-suppression' in tags:
        return 'ROV'
    if 'voter-protection' in tags:
        return 'VPP'
    return ''


def get_tracking_target_state(categories):
    for slug in categories:
        if slug in states:
            return states[slug][0]
    return ''


def get_tracking_records(event_records):
    headers = ['Status', 'Event Date', 'Host', 'Email', 'Group', 'Event Group', 'Followup', 'Event Type',
               'Event Subtype', 'Target State',  'City/Town', 'State', 'Private', 'RSVP Link',
               '', '', '', '', '', '', '', '', '', '', '', '',
               'Group Override',]
    tracking_records = []
    for record in event_records:
        tracking_record = []
        tracking_record.append('Scheduled')
        tracking_record.append(record[4])
        tracking_record.append('')
        tracking_record.append('')
        tracking_record.append('')
        tracking_record.append('')
        tracking_record.append('')
        categories = record[11].split(',')
        tags = record[12].split(',')
        tracking_record.append(get_tracking_event_type(categories))
        tracking_record.append(get_tracking_event_subtype(tags))
        tracking_record.append(get_tracking_target_state(categories))
        tracking_record.append(record[9])
        tracking_record.append(record[10])
        tracking_record.append('')
        tracking_record.append(record[8])
        for i in range(12):
            tracking_record.append('')
            # O through Z
        tracking_record.append(record[2])
        tracking_records.append(tracking_record)
    return headers, tracking_records


def mobilize_to_calendar(path):
    records = []
    out_headers = ['Event Name',
                   'Event Description',
                   'Event Organizers',
                   'Event Venue Name',
                   'Event Start Date',
                   'Event Start Time',
                   'Event End Date',
                   'Event End Time',
                   'Event Website',
                   'City',
                   'State',
                   'Event Category',
                   'Event Tags',
                   'Event Featured Image'
                   ]
    with open(path, newline='', encoding='utf-8') as ifile:
        reader = csv.reader(ifile)
        in_headers = next(reader)
        mobilize_url_index = in_headers.index('URL')
        count_index = find_index(in_headers, 'N')
        new_times_index = find_index(in_headers, 'New Times')
        for record in reader:
            # Skip daily events
            if count_index >= 0 and (record[count_index][-1] == 'D' or record[count_index][0] not in ['N', 'R']):
                continue
            event_url = record[mobilize_url_index]
            data = get_mobilize_data(event_url.split(sep='/')[-2])
            if not data:
                continue
            event_organizers = data['sponsor']['name']
            if 'Maine' in event_organizers:
                continue
            print(data['title'])
            event_description = data['description'] + '\n\n<b><a target=_blank href=' \
                                + event_url + '>PLEASE SIGN UP HERE FOR THE EVENT</a></b>'
            location = data['location']
            if location is not None:
                city = location['locality']
                state = location['region']
                zip_code = location['postal_code']
            else:
                city = ""
                state = ""
                zip_code = ""
            # if city_index >= 0:
            #     assert city == record[city_index]
            # if state_index >= 0:
            #     assert state == record[state_index]
            # if zip_index >= 0:
            #     s_zip_code = record[zip_index]
            #     if len(s_zip_code) == 4:
            #         s_zip_code = '0' + s_zip_code
            #     assert zip_code == s_zip_code
            categories = []
            tags = []
            region = None
            if state in state_categories:
                region = state_categories[state]
            elif state == 'MA' and 'location' in data['location']:
                region = get_ma_region_by_location(data['location']['location'], city)
            elif state == 'MA':
                region = get_ma_region_by_zip(zip_code)
            if region is not None:
                categories.append(region)
            text = data['title'] + ' ' + data['description']
            add_state_categories(categories, text)
            add_activity_categories(categories, text, data['title'])
            add_tags(tags, text)
            if 'postcards-letters' in categories:
                if city and state:
                    event_name = '{}, {} - {}'.format(city.upper(), state, data['title'])
                    event_venue_name = '{}, {}'.format(city, state)
                else:
                    event_name = data['title']
                    event_venue_name = ''
            else:
                event_name = 'ONLINE - ' + data['title']
                event_venue_name = 'Online/Anywhere'
                categories.append('location-online-anywhere')
            now = int(datetime.datetime.now().timestamp())
            new_times = None
            if new_times_index >= 0:
                new_times = record[new_times_index].split(',')
            for time_slot in data['timeslots']:
                if time_slot['start_date'] < now or time_slot['is_full']:
                    continue
                if new_times and (str(time_slot['start_date']) not in new_times):
                    continue
                start = datetime.datetime.fromtimestamp(time_slot['start_date'])
                end = datetime.datetime.fromtimestamp(time_slot['end_date'])
                event_start_date = start.strftime("%Y-%m-%d")
                event_start_time = start.strftime("%H:%M:00")
                event_end_date = end.strftime("%Y-%m-%d")
                event_end_time = end.strftime("%H:%M:00")
                records.append([event_name, event_description, event_organizers, event_venue_name, event_start_date,
                                event_start_time, event_end_date, event_end_time, event_url, city, state,
                                ','.join(categories), ','.join(tags), data.get('featured_image_url', '')])

    out_name = os.path.splitext(path)[0] + '-cal-import.csv'
    with open(out_name, mode='w', newline='', encoding='utf-8') as ofile:
        writer = csv.writer(ofile)
        writer.writerow(out_headers)
        writer.writerows(records)
    out_name = os.path.splitext(path)[0] + '-tracking.csv'
    with open(out_name, mode='w', newline='', encoding='utf-8') as ofile:
        out_headers, records = get_tracking_records(records)
        writer = csv.writer(ofile)
        writer.writerow(out_headers)
        writer.writerows(records)


def get_mobilize_data(id):
    time.sleep(.5)
    url = entry_point + 'events/' + id
    r = requests.get(url, headers=api_header)
    if r.status_code != 200:
        print('Failed:' + url)
        return None
    event = r.json()
    return event['data']


mobilize_to_calendar(sys.argv[1])

