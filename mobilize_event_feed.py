import argparse
import csv
import datetime
import operator
import requests
import shutil

import the_events_calendar
import events
import mobilize_to_calendar

parser = argparse.ArgumentParser()
parser.add_argument("--hours", type=int,
                    help="Hours ago for oldest event to process.")
parser.add_argument("-a", "--all", action="store_true",
                    help="Process all future events.")
parser.add_argument("-c", "--calendar", required=True,
                    help="Name of the calendar being updated.")
parser.add_argument("--url", nargs="+",
                    help="List of mobilize urls to process.")
parser.add_argument("-t", "--timestamp", action="store_true",
                    help="Use value in mobilize-timestamp.txt as oldest event to process")
parser.add_argument("-d", "--debug", action="store_true",
                    help="Log debug info.")
parser.add_argument("--update_timestamp", action="store_true",
                    help="Update mobilize-timestamp.txt to current time.")
args = parser.parse_args()

entry_point = 'https://api.mobilize.us/v1/'
api_header = {'Content-Type': 'application/json'}


skip_list = [389926]


def get_mobilize_event(url):
    event_id = events.get_event_id(url)
    url = entry_point + 'events/' + event_id
    r = requests.get(url, headers=api_header)
    assert r.ok, r.text
    event = r.json()['data']
    browser_url = event['browser_url']
    if 'swingleftboston' in browser_url:
        event['browser_url'] = browser_url.replace('swingleftboston', 'swingbluealliance')
    return event


def get_mobilize_events(since):
    event_list = []
    if since is None:
        update = ''
    else:
        update = '&updated_since={}'.format(since)
    url = '{}organizations/1535/events?per_page=100{}&timeslot_start=gt_now'.format(entry_point, update)
    while True:
        r = requests.get(url, headers=api_header)
        assert r.ok, r.text
        j_data = r.json()
        for event in j_data['data']:
            browser_url = event['browser_url']
            if browser_url is not None:
                if 'swingleftboston' in browser_url:
                    event['browser_url'] = browser_url.replace('swingleftboston', 'swingbluealliance')
                event_list.append(event)
        next_url = j_data['next']
        if next_url is None:
            break
        url = next_url
    return event_list


def mobilize_event_feed(start):
    return process_event_feed(get_mobilize_events(start))


def process_event_feed(event_list):
    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H;%M;%S")
    event_list.sort(key=operator.itemgetter('created_date'), reverse=True)
    records = []
    for event in event_list:
        title = event['title']
        if event['id'] in skip_list:
            print('Skipping: ' + event['title'])
            continue
        event_data = mobilize_to_calendar.mobilize_to_calendar(event)
        if event_data is not None:
            records.extend(event_data)
    if len(records) == 0:
        return
    out_name = '{}--{}-cal-import.csv'.format(the_events_calendar.calendar_name, current_date)
    with open(out_name, mode='w', newline='', encoding='utf-8') as ofile:
        writer = csv.writer(ofile)
        writer.writerow(the_events_calendar.calendar_import_headers)
        writer.writerows(records)
    print(out_name)


def main():
    if len([x for x in [args.hours, args.timestamp, args.url, args.all] if x]) != 1:
        print('Must specify exactly one of -t or --hours or --url or --all')
        exit(1)
    now = int(datetime.datetime.now().timestamp())
    update_timestamp = args.timestamp or args.update_timestamp
    timestamp_file = args.calendar + '-mobilize-timestamp.txt'
    timestamp_backup_file = args.calendar + '-mobilize-timestamp-last.txt'
    if args.hours:
        mobilize_event_feed(now - args.hours * 3600)
    elif args.all:
        mobilize_event_feed(None)
    elif args.timestamp:
        with open(timestamp_file) as f:
            try:
                mobilize_event_feed(int(f.read()))
            except FileNotFoundError:
                print('No timestamp file')
                exit(1)
    elif args.url:
        process_event_feed([get_mobilize_event(url) for url in args.url])
        return
    if update_timestamp:
        try:
            shutil.copy(timestamp_file, timestamp_backup_file)
        except FileNotFoundError:
            pass
        with open(timestamp_file, 'w') as f:
            f.write(str(now))


if __name__ == '__main__':
    the_events_calendar.set_global_calendar(args.calendar)
    main()
