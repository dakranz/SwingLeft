import csv
import datetime
import events
import re

events.dump_events('event-data')
mobilize_events = events.load_mobilize_events('event-data-mobilize.json')
calendar_events = events.load_calendar_events('event-data-calendar.json')
# missing = set()
# for event in c_events:
#     if not event['image']:
#         e = event['website'].split(sep='/')
#         if len(e) < 2 or not e[-2].isnumeric():
#             continue
#         eid = int(e[-2])
#         for e in m_events:
#             if e['id'] == eid:
#                 missing.add(e['featured_image_url'])
#                 break
# for image in missing:
#     print(image)

# dangling = {}
# for event in c_events:
#     if event['website'] == "" and "<a " not in event['description']:
#         if event['title'] not in dangling:
#             dangling[event['title']] = {'id': event['id'], 'title': event['title']}
# for k, v in dangling.items():
#     print(v)


def get_event_id(url):
    data = url.split(sep='/')
    if data[-1] == '':
        return data[-2]
    else:
        return data[-1]


def get_event_map():
    event_map = {}
    for event in calendar_events:
        mobilize_url = None
        for text in [event['website'], event['description']]:
            m = re.findall(r'(https://www.mobilize.us/[\w-]+/event/\d+/).*', text)
            if len(m) > 0 and all(element == m[0] for element in m):
                mobilize_url = m[0]
                break
        if mobilize_url is None:
            continue
        event_id = get_event_id(mobilize_url)
        if event_id in event_map:
            event_map[event_id].append(event)
        else:
            event_map[event_id] = [event]
    return event_map


def print_missing_calendar_events():
    event_map = get_event_map()
    now = int(datetime.datetime.now().timestamp())
    print('Mobilize events not in calendar:')
    for event in mobilize_events:
        if all([slot['start_date'] < now for slot in event['timeslots']]):
            continue
        event_id = get_event_id(event['browser_url'])
        if event_id not in event_map:
            print(event['browser_url'], datetime.datetime.fromtimestamp(event['created_date']).strftime('%c'))
            print(event['title'], '\n')
            for slot in event['timeslots']:
                if slot['start_date'] > now:
                    print(datetime.datetime.fromtimestamp(slot['start_date']).strftime('%Y-%m-%d %H:%M:%S'))
            print('\n')


def dump_new_time_slots():
    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H;%M")
    event_map = get_event_map()
    headers = ['Title', 'URL', 'New Times']
    records = []
    for m_event in mobilize_events:
        browser_url = m_event['browser_url']
        m_id = get_event_id(browser_url)
        if m_id in ['329148', '220981', '295218', '295224', '295226', '301337', '349969', '345286', '302734',
                    '337910', '345743']:
            # Events to be excluded from calendar.
            continue
        elif m_id not in event_map:
            c_events = []
        else:
            c_events = event_map[m_id]
        timeslots = m_event['timeslots']
        if len(timeslots) > 5:
            interval = timeslots[1]['start_date'] - timeslots[0]['start_date']
            if 23 * 3600 < interval < 25 * 3600:
                continue
        if len(c_events) < len(timeslots):
            print(browser_url)
            c_event_set = set()
            new_event_times = []
            for e in c_events:
                print('#', e['start_date'])
                c_event_set.add(e['start_date'])
            for s in timeslots:
                slot = s['start_date']
                time = datetime.datetime.fromtimestamp(slot).strftime('%Y-%m-%d %H:%M:%S')
                if time not in c_event_set:
                    new_event_times.append(str(slot))
                    print(time)
            records.append([m_event['title'], browser_url, ','.join(new_event_times)])
            if c_events:
                print(c_events[0]['url'])
            print('\n')
        # t_event_set = set()
        # for s in timeslots:
        #     slot = s['start_date']
        #     time = datetime.datetime.fromtimestamp(slot).strftime('%Y-%m-%d %H:%M:%S')
        #     t_event_set.add(time)
        # for e in c_events:
        #     if e['start_date'] not in t_event_set:
        #         print('Delete: ', e['url'])
    out_name = 'new-time-slots-{}.csv'.format(current_date)
    with open(out_name, mode='w', newline='', encoding='utf-8') as ofile:
        writer = csv.writer(ofile)
        writer.writerow(headers)
        writer.writerows(records)


dump_new_time_slots()
