import csv
import datetime
import events
import re

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


def print_missing_calendar_events():
    event_map = events.get_event_map()
    now = int(datetime.datetime.now().timestamp())
    print('Mobilize events not in calendar:')
    for event in events.get_mobilize_events():
        if all([slot['start_date'] < now for slot in event['timeslots']]):
            continue
        event_id = events.get_event_id(event['browser_url'])
        if event_id not in event_map:
            print(event['browser_url'], datetime.datetime.fromtimestamp(event['created_date']).strftime('%c'))
            print(event['title'], '\n')
            for slot in event['timeslots']:
                if slot['start_date'] > now:
                    print(datetime.datetime.fromtimestamp(slot['start_date']).strftime('%Y-%m-%d %H:%M:%S'))
            print('\n')


def dump_new_time_slots():
    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H;%M")
    event_map = events.get_event_map()
    mobilize_events = events.get_mobilize_events()
    headers = ['Title', 'URL', 'New Times']
    records = []
    for m_event in mobilize_events:
        browser_url = m_event['browser_url']
        m_id = events.get_event_id(browser_url)
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
