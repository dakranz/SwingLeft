import datetime
import json
import logging
import re
import requests
import sys
import urllib.parse

import api_key
import the_events_calendar

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
logger.addHandler(sh)

use_saved_data = False

GRUBER_URLINTEXT_PAT = re.compile(r'(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:\'".,<>?\xab\xbb\u201c\u201d\u2018\u2019]))')


def get_urls(text):
    return [matches[0] for matches in GRUBER_URLINTEXT_PAT.findall(text) if matches[0] != 'http://news-magic.org/']


def get_mobilize_urls(text):
    matches = GRUBER_URLINTEXT_PAT.findall(text)
    return [match[0] for match in matches if 'mobilize.us/' in match[0] and '/event/' in match[0]]


def calendar_api_base_url():
    return 'https://' + the_events_calendar.wordpress_host_name + '/wp-json/tribe/events/v1/'


skip_list = {}

inside_orgs = ['swingbluealliance', 'indivisiblegreaterandover', 'indivisiblenorthampton', 'swingleftnorthshore',
               'jpprogressives', 'swingleftri', 'sisterdistrictmari', 'somerville2022', 'indivisiblelab']

#api_header = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + api_key.mobilize_key}
api_header = {'Content-Type': 'application/json'}


def prefix(path):
    return the_events_calendar.calendar_name + '-' + path


def mobilize_org():
    name = the_events_calendar.calendar_name
    assert name == 'sba' or name == 'news-magic'
    if name == 'sba':
        return '1535'
    return '33342'


def get_mobilize_event(url):
    event_id = get_event_id(url)
    url = 'https://api.mobilize.us/v1/events/' + event_id
    r = requests.get(url, headers=api_header)
    assert r.ok, r.text
    event = r.json()['data']
    browser_url = event['browser_url']
    return event


def get_mobilize_events(since):
    event_list = []
    if since is None:
        update = ''
    else:
        update = '&updated_since={}'.format(since)
    url = 'https://api.mobilize.us/v1/organizations/{}/events?per_page=100{}&timeslot_start=gt_now'.format(
                                                                                    mobilize_org(),
                                                                                    update)
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


def get_all_mobilize_events():
    if use_saved_data:
        return load_mobilize_events()
    events = []
    url = 'https://api.mobilize.us/v1/organizations/' + mobilize_org() + '/events?per_page=100&timeslot_start=gt_now'
    while True:
        logger.info(url)
        r = requests.get(url, headers=api_header)
        assert r.ok, r.text
        j_data = r.json()
        for event in j_data['data']:
            if event['browser_url'] is not None:
                # print(event['browser_url'], event['sponsor']['name'], "##", event['title'])
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
    url = calendar_api_base_url() + 'events?status=publish&per_page=50&start_date=' + now
    count = None
    while True:
        logger.info(url)
        r = requests.get(url, headers=the_events_calendar.auth_header())
        assert r.ok, r.text
        j_data = r.json()
        if count is None:
            count = j_data['total']
            logger.info(count)
        events.extend(j_data['events'])
        if 'next_rest_url' not in j_data:
            break
        url = j_data['next_rest_url']
    return events


def delete_calendar_event(event_id):
    url = '{}events/{}'.format(calendar_api_base_url(), event_id)
    logger.info("Deleting: " + url)
    r = requests.delete(url, headers=the_events_calendar.auth_header())
    assert r.ok, r.text


calendar_metadata_names = {'categories': '?per_page=50&status=publish&hide_empty=0',
                           'tags': '?per_page=50&status=publish&hide_empty=0',
                           'venues': '?per_page=50&status=publish',
                           'organizers': '?per_page=50&status=publish'}


def get_calendar_metadata(kinds=('categories', 'tags', 'venues', 'organizers')):
    if use_saved_data:
        return load_calendar_metadata()
    metadata = {}
    for kind in calendar_metadata_names:
        if kind not in kinds:
            continue
        url = calendar_api_base_url() + kind + calendar_metadata_names[kind]
        data = []
        count = None
        while True:
            logger.info(url)
            r = requests.get(url, headers=the_events_calendar.auth_header())
            assert r.ok, r.text
            j_data = r.json()
            if count is None:
                count = j_data['total']
                logger.info(count)
            data.extend(j_data[kind])
            if 'next_rest_url' not in j_data:
                break
            url = j_data['next_rest_url']
        metadata[kind] = data
    return metadata


def dump_calendar_metadata():
    metadata = get_calendar_metadata()
    for kind, data in metadata.items():
        with open(prefix('calendar-' + kind + '.json'), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)


def load_calendar_metadata():
    metadata = {}
    for kind in calendar_metadata_names:
        with open(prefix('calendar-' + kind + '.json'), encoding='utf-8') as f:
            metadata[kind] = json.load(f)
    return metadata


def dump_events():
    m_events = get_all_mobilize_events()
    c_events = get_calendar_events()
    with open(prefix('mobilize-events.json'), 'w', encoding='utf-8') as f:
        json.dump(m_events, f, ensure_ascii=False, indent=4)
    with open(prefix('calendar-events.json'), 'w', encoding='utf-8') as f:
        json.dump(c_events, f, ensure_ascii=False, indent=4)


def load_calendar_events():
    with open(prefix('calendar-events.json'), encoding='utf-8') as f:
        return json.load(f)


def load_mobilize_events():
    with open(prefix('mobilize-events.json'), encoding='utf-8') as f:
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
    the_events_calendar.set_global_calendar(sys.argv[1])
    dump_all()
