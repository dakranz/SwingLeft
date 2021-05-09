import datetime
import markdown

import events
import regions
import the_events_calendar

entry_point = 'https://api.mobilize.us/v1/'
api_header = {'Content-Type': 'application/json'}


def mobilize_to_calendar(event):
    event_url = event['browser_url']
    event_organizers = event['sponsor']['name']
    # Mobilize uses markdown. There are many variants but we hope this markdown package will do no harm.
    # https://github.com/Python-Markdown/markdown
    event_description = markdown.markdown(event['description'])
    event_description = event_description + '\n\n<b><a target=_blank href=' \
                        + event_url + '>PLEASE SIGN UP HERE FOR THE EVENT</a></b>'
    city = ''
    state = ''
    zip_code = ''
    sponsor = event['sponsor']['slug']
    if event['location'] is not None:
        city = event['location']['locality']
        state = event['location']['region']
        zip_code = event['location']['postal_code']
        # Skip outside MA
        if zip_code >= '02800':
            return None
    # Skip events with no location unless sponsored by us or a close sponsor
    if not (city or zip_code or sponsor in events.inside_orgs):
        return None
    categories = []
    tags = []
    region = ''
    if state in regions.state_categories:
        region = regions.state_categories[state]
    elif state == 'MA' and 'location' in event['location']:
        region = regions.get_ma_region_by_location(event['location']['location'], city)
    elif state == 'MA':
        region = regions.get_ma_region_by_zip(zip_code)
    text = event['title'] + ' ' + event['description']
    the_events_calendar.add_state_categories(categories, text)
    the_events_calendar.add_activity_categories(categories, text, event['title'])
    the_events_calendar.add_tags(tags, text)
    if the_events_calendar.has_real_venue(categories):
        if city and state:
            event_name = '{}, {} - {}'.format(city.upper(), state, event['title'])
            event_venue_name = '{}, {}'.format(city, state)
        else:
            event_name = event['title']
            event_venue_name = ''
    else:
        event_name = event['title']
        event_venue_name = 'Online/Anywhere'
    now = int(datetime.datetime.now().timestamp())
    time_slots = [slot for slot in event['timeslots'] if slot['start_date'] > now]
    # Skip daily events
    if len(time_slots) > 5:
        interval = time_slots[1]['start_date'] - time_slots[0]['start_date']
        if 23 * 3600 < interval < 25 * 3600:
            print('Skipping daily event: ', event['browser_url'])
            return None
    event_records = []
    for time_slot in time_slots:
        start = datetime.datetime.fromtimestamp(time_slot['start_date'])
        end = datetime.datetime.fromtimestamp(time_slot['end_date'])
        event_start_date = start.strftime("%Y-%m-%d")
        event_start_time = start.strftime("%H:%M:00")
        event_end_date = end.strftime("%Y-%m-%d")
        event_end_time = end.strftime("%H:%M:00")
        event_record = [event_name, event_description, event_organizers, event_venue_name, event_start_date,
                        event_start_time, event_end_date, event_end_time, event_url, city, state,
                        ','.join(categories), ','.join(tags), zip_code, region]
        # Accept full events for now
        # if time_slot['is_full']:
        #     continue
        event_records.append(event_record)
    num = "[{}]".format(len(event_records))
    created = datetime.datetime.fromtimestamp(event['created_date'])
    modified = datetime.datetime.fromtimestamp(event['modified_date'])
    print(created, modified, num, event['title'], event_url)
    return event_records
