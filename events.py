import datetime
import json
import requests
import urllib.parse


skip_list = {'Maine Voter Protection': 294182}


def filter_event(event):
    if 'Maine' in event['sponsor']['name']:
        return None
    city = ''
    state = ''
    zipcode = ''
    sponsor = event['sponsor']['slug']
    if event['location'] is not None:
        city = event['location']['locality']
        state = event['location']['region']
        zipcode = event['location']['postal_code']
        if zipcode >= '08000':  # '02800':
            return None
    if not (city or zipcode or sponsor in ['swingleftboston', 'togetherfor2020', 'swingleftnorthshore']):
        return None
    title = event['title']
    if title in skip_list and event['id'] == skip_list[title]:
        return None
    return {'city': city, 'state': state, 'zipcode': zipcode, 'sponsor': sponsor}


def get_mobilize_events():
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
    events = []
    headers = {'User-Agent': 'Foo bar'}
    now = urllib.parse.quote(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    url = 'https://swingleftboston.org/wp-json/tribe/events/v1/events?per_page=50&start_date=' + now
    while True:
        print(url)
        r = requests.get(url, headers=headers)
        j_data = r.json()
        events.extend(j_data['events'])
        if 'next_rest_url' not in j_data:
            break
        url = j_data['next_rest_url']
    return events


def dump_events(fname):
    with open(fname + '-mobilize.json', 'w', encoding='utf-8') as f:
        json.dump(get_mobilize_events(), f, ensure_ascii=False, indent=4)
    with open(fname + '-calendar.json', 'w', encoding='utf-8') as f:
        json.dump(get_calendar_events(), f, ensure_ascii=False, indent=4)


def load_mobilize_events(fname):
    with open(fname, encoding='utf-8') as f:
        return json.load(f)


def load_calendar_events(fname):
    with open(fname, encoding='utf-8') as f:
        return json.load(f)


if __name__ == "__main__":
    dump_events('event-data')
