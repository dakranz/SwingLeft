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
parser.add_argument("--url", nargs="+",
                    help="List of mobilize urls to process.")
parser.add_argument("-t", "--timestamp", action="store_true",
                    help="Use value in mobilize-timestamp.txt as oldest event to process")
parser.add_argument("-d", "--debug", action="store_true",
                    help="Log debug info.")
parser.add_argument("-u", "--update_timestamp", action="store_true",
                    help="Update mobilize-timestamp.txt to current time.")
args = parser.parse_args()

entry_point = 'https://api.mobilize.us/v1/'
api_header = {'Content-Type': 'application/json'}


skip_list = {}


def get_mobilize_event(url):
    event_id = events.get_event_id(url)
    url = entry_point + 'events/' + event_id
    r = requests.get(url, headers=api_header)
    return r.json()['data']


def get_mobilize_events(since):
    event_list = []
    url = '{}organizations/1535/events?per_page=100&updated_since={}&timeslot_start=gt_now'.format(entry_point, since)
    while True:
        r = requests.get(url, headers=api_header)
        j_data = r.json()
        for event in j_data['data']:
            if event['browser_url'] is not None:
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
        if title in skip_list and event['id'] == skip_list[title]:
            print('Skipping:' + title)
            continue
        event_data = mobilize_to_calendar.mobilize_to_calendar(event)
        if event_data is not None:
            records.extend(event_data)
        out_name = '{}-cal-import.csv'.format(current_date)
        with open(out_name, mode='w', newline='', encoding='utf-8') as ofile:
            writer = csv.writer(ofile)
            writer.writerow(the_events_calendar.calendar_import_headers)
            writer.writerows(records)
    print(out_name)


def main():
    if len([x for x in [args.hours, args.timestamp, args.url] if x]) != 1:
        print('Must specify exactly one of -t or --hours or --url')
        exit(1)
    now = int(datetime.datetime.now().timestamp())
    update_timestamp = args.timestamp or args.update_timestamp
    if args.hours:
        mobilize_event_feed(now - args.hours * 3600)
    elif args.timestamp:
        with open('mobilize-timestamp.txt') as f:
            try:
                mobilize_event_feed(int(f.read()))
            except FileNotFoundError:
                print('No timestamp file')
                exit(1)
    elif args.url:
        process_event_feed([get_mobilize_event(url) for url in args.url])
        return
    if update_timestamp:
        shutil.copy('slack-timestamp.txt', 'slack-timestamp-last.txt')
        with open('mobilize-timestamp.txt', 'w') as f:
            f.write(str(now))


main()
