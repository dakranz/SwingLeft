import re
import sys

import events
import the_events_calendar

GRUBER_URLINTEXT_PAT = re.compile(r'(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:\'".,<>?\xab\xbb\u201c\u201d\u2018\u2019]))')


def get_urls(text):
    return [matches[0] for matches in GRUBER_URLINTEXT_PAT.findall(text) if matches[0] != 'http://news-magic.org/']


skip_list = {'news-magic': ['https://www.mobilize.us/indivisiblegreaterandover/event/411938/'],
             'sba': []}


def find_duplicate_calendar_events():
    all_events = events.get_calendar_events()
    url_map = {}
    for event in all_events:
        for url in get_urls(event['description']):
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

