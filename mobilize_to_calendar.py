import csv
import datetime
import os
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


event_tags = {"vote-by-mail": ["vote by mail", 'VBM', "vote-by-mail"],
              "joe-biden": [" biden", "biden "],
              "voter-suppression": ["supression"],
              "voter-protection": ["protectin"]
              }

activities = {"canvassing": ["canvas"],
              "phone-calls": ["phone"],
              "postcards-letters": ["letter", "postcard", "post card", "pick up", "pick up", "pick-up"],
              "texting": ["texting"],
              "fundraiser": ["fundrai"],
              "training-briefings": ["training", "briefing"]
              }

states = {"arizona-events": ["AZ", "Arizona"],
          "colorado-events": ["CO", "Colorado"],
          "florida-events": ["FL", "Florida"],
          "georgia-events": ["GA", "Georgia"],
          "iowa-events": ["IA", "Iowa"],
          "maine-events": ["ME", "Maine"],
          "michigan-events": ["MI", "Michigan"],
          "north-caroline-events": ["NC", "North Carolina"],
          "ohio-events": ["OH", "Ohio"],
          "pennsylvania-events": ["PA", "Pennsylvania"],
          "texas-events": ["TX", "Texas"],
          "wisconsin-events": ["WI", "Wisconsin"]
          }


def add_state_categories(category_list, text):
    state_list = []
    for category, strings in states.items():
        for s in strings:
            if s in text:
                state_list.append(category)
                break
    if len(state_list) == 1:
        category_list.append(state_list[0])
    elif len(state_list) >=2:
        print("Multiple states:", state_list)


def add_activity_categories(category_list, text):
    text = text.lower()
    added = False
    for category, strings in activities.items():
        for s in strings:
            if s in text:
                category_list.append(category)
                added = True
                break
    if not added or 'phone-calls' in category_list and 'training-briefings' not in category_list:
        category_list.append('training-briefings')


def add_tags(tag_list, text):
    text = text.lower()
    for tag, strings in event_tags.items():
        for s in strings:
            if s in text:
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


def get_ma_region_by_location(location):
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
                   'Event Tags'
                   ]
    with open(path, newline='', encoding='utf-8') as ifile:
        reader = csv.reader(ifile)
        in_headers = next(reader)
        mobilize_url_index = in_headers.index('URL')
        city_index = find_index(in_headers, 'City')
        state_index = find_index(in_headers, 'State Code')
        zip_index = find_index(in_headers, 'Zip')
        visibility_index = find_index(in_headers, 'Visibility')
        for record in reader:
            if visibility_index >= 0 and record[visibility_index] == 'private':
                continue
            event_url = record[mobilize_url_index]
            data = get_mobilize_data(event_url.split(sep='/')[-2])
            if not data:
                continue
            event_organizers = data['sponsor']['name']
            if 'Maine' in event_organizers:
                continue
            print(data['title'])
            event_website = event_url.replace('/swingleft/', '/swingleftboston/')
            event_description = data['description'] + '\n\n<b><a href=' \
                                + event_website + '>PLEASE SIGN UP HERE FOR THE EVENT</a></b>'
            location = data['location']
            city = location['locality']
            state = location['region']
            zip_code = location['postal_code']
            if city_index >= 0:
                assert city == record[city_index]
            if state_index >= 0:
                assert state == record[state_index]
            if zip_index >= 0:
                s_zip_code = record[zip_index]
                if len(s_zip_code) == 4:
                    s_zip_code = '0' + s_zip_code
                assert zip_code == s_zip_code
            categories = []
            tags = []
            region = None
            if state in state_categories:
                region = state_categories[state]
            elif state == 'MA' and 'location' in data['location']:
                region = get_ma_region_by_location(data['location']['location'])
            elif state == 'MA':
                region = get_ma_region_by_zip(zip_code)
            if region is not None:
                categories.append(region)
            add_state_categories(categories, data['description'])
            add_activity_categories(categories, data['description'])
            add_tags(tags, data['description'])
            if 'postcards-letters' in categories:
                event_name = '{}, {} - {}'.format(city.upper(), state, data['title'])
                event_venue_name = '{}, {}'.format(city, state)
            else:
                event_name = 'ONLINE - ' + data['title']
                event_venue_name = 'Online/Anywhere'
                categories.append('location-online-anywhere')
            for time_slot in data['timeslots']:
                start = datetime.datetime.fromtimestamp(int(time_slot['start_date']))
                end = datetime.datetime.fromtimestamp(int(time_slot['end_date']))
                event_start_date = start.strftime("%Y-%m-%d")
                event_start_time = start.strftime("%H:%M:00")
                event_end_date = end.strftime("%Y-%m-%d")
                event_end_time = end.strftime("%H:%M:00")
                records.append([event_name, event_description, event_organizers, event_venue_name, event_start_date,
                                event_start_time, event_end_date, event_end_time, event_website, city, state,
                                ','.join(categories), ','.join(tags)])

    out_name = os.path.splitext(path)[0] + '-cal-import.csv'
    with open(out_name, mode='w', newline='', encoding='utf-8') as ofile:
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

