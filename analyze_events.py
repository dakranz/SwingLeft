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


def print_dups():
    dups = {}
    for event in calendar_events:
        eid = None
        for text in [event['website'], event['description']]:
            m = re.match(r'.*(mobilize.us/\w+/event)/(\d+)', text)
            if m is not None:
                eid = m.groups()[1]
                break
        if eid is None:
            continue
        start = event['start_date']
        if (eid, start) not in dups:
            dups[(eid, start)] = [{'title': event['title'], 'url': event['url']}]
        else:
            dups[(eid, start)].append({'title': event['title'], 'url': event['url']})

    titles = set()
    for (id, start), v in dups.items():
        if len(v) > 1:
            done_already = False
            for e in v:
                if e['title'] in titles:
                    done_already = True
            if done_already:
                continue
            print(id, start)
            for e in v:
                titles.add(e['title'])
                print(e['title'])
                print(e['url'])
            print('\n')


def print_missing_calendar_events():
    event_map = get_event_map()
    print('Mobilize events not in calendar:')
    for event in mobilize_events:
        event_id = get_event_id(event['browser_url'])
        if event_id not in event_map:
            print(event['browser_url'], datetime.datetime.fromtimestamp(event['created_date']).strftime('%c'))
            print(event['title'], '\n')


def dump_new_time_slots():
    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H;%M")
    event_map = get_event_map()
    headers = ['Title', 'URL', 'New Times']
    records = []
    for m_event in mobilize_events:
        browser_url = m_event['browser_url']
        m_id = get_event_id(browser_url)
        if m_id not in event_map:
            continue
        if m_id == '329148':
            # This is a 6 day a week event with one calendar entry
            continue
        c_events = event_map[m_id]
        timeslots = m_event['timeslots']
        if len(timeslots) > 5:
            interval = timeslots[1]['start_date'] - timeslots[0]['start_date']
            if 23 * 3600 < interval < 25 * 3600 :
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
    out_name = 'new-time-slots-{}.csv'.format(current_date)
    with open(out_name, mode='w', newline='', encoding='utf-8') as ofile:
        writer = csv.writer(ofile)
        writer.writerow(headers)
        writer.writerows(records)


#print_missing_calendar_events()
dump_new_time_slots()
