import datetime
import sys
import time

import events
import the_events_calendar

skip_list = {'news-magic': [],
             'sba': []}


def canonicalize_url(url):
    if 'mobilize.us/' not in url:
        return url
    parts = url.split(sep='/')
    mobilize_id = parts[-2] if url[-1] == '/' else parts[-1]
    return 'https://www.mobilize.us/swingbluealliance/event/{}/'.format(mobilize_id)


def find_duplicate_calendar_events():
    all_events = events.get_calendar_events()
    url_map = {}
    for event in all_events:
        for url in events.get_urls(event['description']):
            url = canonicalize_url(url)
            candidate = (url, event['start_date'])
            if candidate in url_map:
                url_map[candidate].add(event['url'])
            else:
                url_map[candidate] = set([event['url']])
    for (url, start), event_urls in url_map.items():
        if len(event_urls) == 1:
            continue
        if url in skip_list[the_events_calendar.calendar_name]:
            continue
        print(url)
        for event_url in event_urls:
            print(event_url)
        print('\n')


def time_slot_string(event_id, start):
    return '{}#{}'.format(event_id, start)


def find_orphaned_calendar_events(org):
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    calendar_events = events.get_calendar_events()
    mobilize_events = events.get_all_mobilize_events()
    all_slots = set()
    for event in mobilize_events:
        for slot in event['timeslots']:
            start = datetime.datetime.fromtimestamp(slot['start_date']).strftime('%Y-%m-%d %H:%M:%S')
            all_slots.add(time_slot_string(event['id'], start))
    for event in calendar_events:
        if event['start_date'] <= now or 'mobilize.us/' + org not in event['website']:
            continue
        if time_slot_string(events.get_event_id(event['website']), event['start_date']) not in all_slots:
            print(event['url'])
            #events.delete_calendar_event(event['id'])
            time.sleep(1)


def main():
    the_events_calendar.set_global_calendar(sys.argv[1])
    if the_events_calendar.calendar_name == 'sba':
        org = 'swingbluealliance'
    else:
        org = 'news-magic'
    find_duplicate_calendar_events()
    #find_orphaned_calendar_events(org)


main()

