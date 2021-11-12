import sys

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


def main():
    the_events_calendar.set_global_calendar(sys.argv[1])
    find_duplicate_calendar_events()


main()

