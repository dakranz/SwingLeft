import csv
import datetime
import operator
import os
import requests
import sys
import time

from pprint import pprint

entry_point = 'https://api.mobilize.us/v1/'
api_header = {'Content-Type': 'application/json'}


skip_list = {'Maine Voter Protection': 294182}


def get_events(hours_ago):
    events = []
    since = int(datetime.datetime.now().timestamp() - hours_ago * 60 * 60)
    url = '{}organizations/1535/events?per_page=100&updated_since={}&timeslot_start=gt_now'.format(entry_point, since)
    while True:
        r = requests.get(url, headers=api_header)
        j_data = r.json()
        for event in j_data['data']:
            if event['browser_url'] is not None:
                events.append(event)
        next_url = j_data['next']
        if next_url is None:
            break
        url = next_url
    return events


def date_display(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def mobilize_event_feed(hours_ago):
    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H;%M")
    events = get_events(hours_ago)
    events.sort(key=operator.itemgetter('created_date'), reverse=True)
    headers = ['Mod Date', 'Created Date', 'Title', 'City', 'State Code', 'Zip', 'Organization', 'Start Date', 'N', 'URL']
    records = []
    now = int(datetime.datetime.now().timestamp())
    for event in events:
        city = ''
        state = ''
        zipcode = ''
        sponsor = event['sponsor']['slug']
        if event['location'] is not None:
            city = event['location']['locality']
            state = event['location']['region']
            zipcode = event['location']['postal_code']
            if zipcode >= '08000':#'02800':
                continue
        if not (city or zipcode or sponsor in ['swingleftboston', 'togetherfor2020']):
            continue
        title = event['title']
        if title in skip_list and event['id'] == skip_list[title]:
            print('Skipping:' + title)
            continue
        all_timeslots = event['timeslots']
        timeslots = []
        for slot in all_timeslots:
            if slot['start_date'] > now:
                timeslots.append(slot)
        n = len(timeslots)
        assert n > 0
        # Mark daily events
        if n > 5:
            interval = timeslots[1]['start_date'] - timeslots[0]['start_date']
            if 23 * 3600 < interval < 25 * 3600 :
                n = str(n) + 'D'
        start = datetime.datetime.fromtimestamp(timeslots[0]['start_date']).strftime('%m/%d')
        records.append([date_display(datetime.datetime.fromtimestamp(event['modified_date'])),
                        date_display(datetime.datetime.fromtimestamp(event['created_date'])),
                        title, city, state, zipcode, sponsor, start, n, event['browser_url']])
        print(datetime.datetime.fromtimestamp(event['created_date']).strftime('%Y-%m-%d %H:%M'), title)
        out_name = '{}-mobilize-feed-{}.csv'.format(current_date, hours_ago)
        with open(out_name, mode='w', newline='', encoding='utf-8') as ofile:
            writer = csv.writer(ofile)
            writer.writerow(headers)
            writer.writerows(records)


mobilize_event_feed(int(sys.argv[1]))
