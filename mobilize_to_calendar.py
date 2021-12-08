import datetime
import logging
import markdown

import events
import regions
import the_events_calendar

entry_point = 'https://api.mobilize.us/v1/'
api_header = {'Content-Type': 'application/json'}

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
logger.addHandler(sh)


def get_calendar_tags(mobilize_tags, calendar_tags):
    for mobilize_tag in mobilize_tags:
        mobilize_tag_name = mobilize_tag['name'].lower()
        for calendar_tag in calendar_tags:
            if mobilize_tag_name == calendar_tag['name'].lower():
                return [calendar_tag['name']]
    return []


# Handle cases where another org is using the swing left mobilize and other random cases where the calendar org should
# be different from the sponsor as reported by mobilize.
def get_event_organizer(event):
    if any([tag['name'] == 'Org: All In For Nc' for tag in event['tags']]):
        return 'All in for NC'
    if any([tag['name'] == 'Org: Ma Flip Pa' for tag in event['tags']]):
        return 'MAFlipPA'
    org = event['sponsor']['name']
    if org == 'JP Progressives':
        return 'Jamaica Plain Progressives'
    return org


def mobilize_to_calendar(event, force):
    event_url = event['browser_url']
    event_organizer = get_event_organizer(event)
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
#        if zip_code >= '02800' and sponsor not in events.inside_orgs and not force:
#            return None
    # Skip events with no location unless sponsored by us or a close sponsor
#    if not (city or zip_code or sponsor in events.inside_orgs or force):
#        return None
    categories = []
    region = ''
    if state in regions.state_categories:
        region = regions.state_categories[state]
    elif state == 'MA' and 'location' in event['location']:
        region = regions.get_ma_region_by_location(event['location']['location'], city)
    elif state == 'MA':
        region = regions.get_ma_region_by_zip(zip_code)
    text = event['title'] + ' ' + event['description']
    tags = []
    tag, is_target_state = the_events_calendar.get_state_tags(event['tags'])
    if tag is None:
        tag, is_target_state = the_events_calendar.infer_state_tags(text)
    if tag is not None:
        tags = [tag]
    # For the grassroots news-magic calendar we only post Swing Blue Alliance events. For the Swing Blue Alliance
    # calendar we also post promoted events that are locally hosted and part of a target state campaign.
    if sponsor not in events.inside_orgs:
        # if not force and ('news-magic' in the_events_calendar.calendar_name or not is_target_state):
        if not force and ('news-magic' in the_events_calendar.calendar_name):
            return None
    if 'event_type' not in event or the_events_calendar.lookup_mobilize_event_type(event['event_type']) is None:
        the_events_calendar.add_activity_categories(categories, text, event['title'])
    else:
        category = the_events_calendar.lookup_mobilize_event_type(event['event_type'])
        if category is not None:
            categories.append(category)
    if the_events_calendar.has_real_venue(categories):
        if city and state:
            event_name = '{}, {} - {}'.format(city.upper(), state, event['title'])
            event_venue_name = '{}, {}'.format(city, state)
        else:
            event_name = event['title']
            event_venue_name = 'Online/Anywhere'
    else:
        event_name = event['title']
        event_venue_name = 'Online/Anywhere'
    now = int(datetime.datetime.now().timestamp())
    time_slots = [slot for slot in event['timeslots'] if slot['end_date'] > now]
    # Skip daily events
    # if len(time_slots) > 5:
    #     interval = time_slots[1]['start_date'] - time_slots[0]['start_date']
    #     if 23 * 3600 < interval < 25 * 3600:
    #         logger.info('Skipping daily event: %s', event['browser_url'])
    #         return None
    event_records = []
    for time_slot in time_slots:
        start = datetime.datetime.fromtimestamp(time_slot['start_date'])
        end = datetime.datetime.fromtimestamp(time_slot['end_date'])
        event_start_date = start.strftime("%Y-%m-%d")
        event_start_time = start.strftime("%H:%M:00")
        event_end_date = end.strftime("%Y-%m-%d")
        event_end_time = end.strftime("%H:%M:00")
        event_record = [event_name, event_description, event_organizer, event_venue_name, event_start_date,
                        event_start_time, event_end_date, event_end_time, event_url, city, state,
                        ','.join(categories), ','.join(tags), zip_code, region]
        # Accept full events for now
        # if time_slot['is_full']:
        #     continue
        event_records.append(event_record)
    num = "[{}]".format(len(event_records))
    created = datetime.datetime.fromtimestamp(event['created_date'])
    modified = datetime.datetime.fromtimestamp(event['modified_date'])
    logger.info("%s %s %s %s %s %s", created, modified, num, event['title'], event_url, event.get('event_type', ''))
    return event_records
