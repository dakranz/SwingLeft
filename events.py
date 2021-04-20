import datetime
import json
import requests
import urllib.parse

import api_key

use_saved_data = False

calendar_api_base_url = 'https://' + api_key.wordpress_host_name + '/wp-json/tribe/events/v1/'
calendar_headers = {'User-Agent': 'Foo bar'}

skip_list = {}


def filter_event(event):
    city = ''
    state = ''
    zipcode = ''
    sponsor = event['sponsor']['slug']
    if event['location'] is not None:
        city = event['location']['locality']
        state = event['location']['region']
        zipcode = event['location']['postal_code']
        if zipcode >= '02800':
            return None
    if not (city or zipcode or sponsor in ['swingleftboston', 'togetherfor2020', 'swingleftnorthshore',
                                           'indivisiblenorthampton', 'indivisiblegreaterandover',
                                           'indivisibleacton-area']):
        return None
    title = event['title']
    if title in skip_list and event['id'] == skip_list[title]:
        return None
    return {'city': city, 'state': state, 'zipcode': zipcode, 'sponsor': sponsor}


def get_mobilize_events():
    if use_saved_data:
        return load_mobilize_events()
    events = []
    url = 'https://api.mobilize.us/v1/organizations/1535/events?per_page=100&timeslot_start=gt_now'
    while True:
        print(url)
        r = requests.get(url)
        j_data = r.json()
        for event in j_data['data']:
            if event['browser_url'] is not None and filter_event(event):
                events.append(event)
        next_url = j_data['next']
        if next_url is None:
            break
        url = next_url
    return events


def get_calendar_events():
    if use_saved_data:
        return load_calendar_events()
    events = []
    now = urllib.parse.quote(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    url = calendar_api_base_url + 'events?per_page=50&start_date=' + now
    while True:
        print(url)
        r = requests.get(url, headers=calendar_headers)
        j_data = r.json()
        events.extend(j_data['events'])
        if 'next_rest_url' not in j_data:
            break
        url = j_data['next_rest_url']
    return events


calendar_metadata_names = {'categories': '?per_page=50&hide_empty=0',
                           'tags': '?per_page=50&hide_empty=0',
                           'venues': '?per_page=50',
                           'organizers': '?per_page=50'}


def get_calendar_metadata():
    if use_saved_data:
        return load_calendar_metadata()
    metadata = {}
    for kind in calendar_metadata_names:
        url = calendar_api_base_url + kind + calendar_metadata_names[kind]
        data = []
        while True:
            print(url)
            r = requests.get(url, headers=calendar_headers)
            assert r.ok
            j_data = r.json()
            data.extend(j_data[kind])
            if 'next_rest_url' not in j_data:
                break
            url = j_data['next_rest_url']
        metadata[kind] = data
    return metadata


def dump_calendar_metadata():
    metadata = get_calendar_metadata()
    for kind, data in metadata.items():
        with open('calendar-' + kind + '.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)


def load_calendar_metadata():
    metadata = {}
    for kind in calendar_metadata_names:
        with open('calendar-' + kind + '.json', encoding='utf-8') as f:
            metadata[kind] = json.load(f)
    return metadata


def dump_events():
    m_events = get_mobilize_events()
    c_events = get_calendar_events()
    with open('mobilize-events.json', 'w', encoding='utf-8') as f:
        json.dump(m_events, f, ensure_ascii=False, indent=4)
    with open('calendar-events.json', 'w', encoding='utf-8') as f:
        json.dump(c_events, f, ensure_ascii=False, indent=4)


def load_calendar_events():
    with open('calendar-events.json', encoding='utf-8') as f:
        return json.load(f)


def load_mobilize_events():
    with open('mobilize-events.json', encoding='utf-8') as f:
        return json.load(f)


def get_event_id(url):
    data = url.split(sep='/')
    if data[-1] == '':
        return data[-2]
    else:
        return data[-1]


def get_event_map():
    event_map = {}
    for event in get_calendar_events():
        mobilize_url = event.get('website', '')
        if 'www.mobilize.us' not in mobilize_url:
            continue
        event_id = get_event_id(mobilize_url)
        if event_id in event_map:
            event_map[event_id].append(event)
        else:
            event_map[event_id] = [event]
    return event_map


def dump_all():
    dump_calendar_metadata()
    dump_events()


if __name__ == "__main__":
    dump_all()
