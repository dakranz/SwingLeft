import argparse
import datetime
import sys
import time
import traceback

import events
import slack
import the_events_calendar

skip_list = {'news-magic': [],
             'sba': []}


def canonicalize_url(url):
    if 'mobilize.us/' not in url:
        return url
    q = url.find('?')
    if q >= 0:
        url = url[0:q]
    parts = url.split(sep='/')
    mobilize_id = parts[-2] if url[-1] == '/' else parts[-1]
    return 'https://www.mobilize.us/swingbluealliance/event/{}/'.format(mobilize_id)


def find_duplicate_calendar_events(all_events):
    url_map = {}
    for event in all_events:
        for url in events.get_urls(event['description']):
            url = canonicalize_url(url)
            candidate = (url, event['start_date'])
            if candidate in url_map:
                url_map[candidate].append(event)
            else:
                url_map[candidate] = [event]
    for (url, start), event_list in url_map.items():
        # dedup
        event_set = []
        for event in event_list:
            if event not in event_set:
                event_set.append(event)
        if len(event_set) == 1:
            continue
        if url in skip_list[the_events_calendar.calendar_name]:
            continue
        last_mod = max(event['modified'] for event in event_set)
        # If there is a manually created event, delete all automated events
        for event in event_set:
            if str(event['author']) != the_events_calendar.wordpress_automation_author_id:
                last_mod = 0
                break
        for event in event_set:
            if event['modified'] == last_mod or \
                    str(event['author']) != the_events_calendar.wordpress_automation_author_id:
                print('Keeping: ', event['url'])
            else:
                print('Deleting duplicate: ', event['url'])
                if not args.dry_run:
                    events.delete_calendar_event(event['id'])
                    time.sleep(1)
        print('\n')


def time_slot_string(event_id, start):
    return '{}#{}'.format(event_id, start)


def find_orphaned_calendar_events(orgs, calendar_events, mobilize_events):
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    all_slots = set()
    for event in mobilize_events:
        for slot in event['timeslots']:
            start = datetime.datetime.fromtimestamp(slot['start_date']).strftime('%Y-%m-%d %H:%M:%S')
            all_slots.add(time_slot_string(event['id'], start))
    for event in calendar_events:
        if event['start_date'] <= now:
            continue
        check_date = False
        for org in orgs:
            if 'mobilize.us/' + org in event['website']:
                check_date = True
                break
        if not check_date:
            continue
        if time_slot_string(events.get_event_id(event['website']), event['start_date']) not in all_slots:
            print('Deleting orphaned: ', event['url'])
            if not args.dry_run:
                events.delete_calendar_event(event['id'])
                time.sleep(1)
    print('\n')


def report_error(message):
    header = "<!channel> *Duplicate and orphan detection failed*"
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": header}},
              {"type": "section", "text": {"type": "plain_text", "text": message}}]
    slack.post_message('automation', text=header, blocks=blocks)


parser = argparse.ArgumentParser()
parser.add_argument("-y", "--dry_run", action="store_true", help="Read events but do not update the sheet.")
parser.add_argument("-r", "--report", action="store_true", help="Report errors to slack.")
parser.add_argument("calendar", help="Which calendar to analyze.")
args = parser.parse_args()


def main():
    try:
        the_events_calendar.set_global_calendar(args.calendar)
        if the_events_calendar.calendar_name == 'sba':
            orgs = ['swingbluealliance', 'activist-afternoons']
        else:
            org = 'news-magic'
        calendar_events = events.get_calendar_events()
        mobilize_events = events.get_all_mobilize_events()
        find_duplicate_calendar_events(calendar_events)
        find_orphaned_calendar_events(orgs, calendar_events, mobilize_events)
    except Exception as e:
        err_message = traceback.format_exc()
        if args.report:
            report_error(err_message)
        else:
            print(err_message)


main()

