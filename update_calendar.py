import argparse
import base64
import csv
import datetime
import logging
import requests
from pprint import pformat

import api_key
import events

parser = argparse.ArgumentParser()
parser.add_argument("csv_file", help="csv file with event data")
parser.add_argument("-y", "--dry_run", action="store_true",
                    help="Do not actually post/update calendar events but log requests.")
parser.add_argument("-c", "--use_cached_data", action="store_true",
                    help="Do not fetch events and metadata from wordpress. Use data stored by running events.py")
parser.add_argument("-d", "--debug", action="store_true",
                    help="Log debug info.")
args = parser.parse_args()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG if args.debug else logging.INFO)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
logger.addHandler(sh)

if args.use_cached_data:
    events.use_saved_data = True

auth_header = {'Authorization': 'Basic ' + base64.standard_b64encode(api_key.wordpress_app_password.encode()).decode(),
               'User-Agent': 'Foo bar'}
events_base_url = 'https://' + api_key.wordpress_host_name + '/wp-json/tribe/events/v1/events'
venues_base_url = 'https://' + api_key.wordpress_host_name + '/wp-json/tribe/events/v1/venues'

# Unfortunately we cannot control the random names the events calendar assigns to custom fields but it should not change
custom_field_map = {'region': '_ecp_custom_2'}


def update_event(event_id, json):
    return requests.post('{}/{}'.format(events_base_url, event_id), headers=auth_header, json=json)


def create_event(json):
    return requests.post(events_base_url, headers=auth_header, json=json)


def get_metadata_id(metadata, kind, key, value):
    for x in metadata[kind]:
        if x.get(key, None) == value:
            return x['id']
    return None


def get_tag_id(metadata, value):
    return get_metadata_id(metadata, 'tags', 'slug', value)


def get_category_id(metadata, value):
    return get_metadata_id(metadata, 'categories', 'slug', value)


def get_venue_id(metadata, value, city, state, zip_code):
    venue_id = get_metadata_id(metadata, 'venues', 'venue', value)
    if venue_id is not None:
        return venue_id
    data = {'venue': value}
    if city:
        data['city'] = city
    # Calendar API seems to use province but not state
    if state:
        data['province'] = state
    # Calendar API bug makes this bomb out
    # if zip_code:
    #     data['zip'] = int(zip_code)
    r = requests.post(venues_base_url, headers=auth_header, json=data)
    if not r.ok:
        logger.warning("Could not create venue for %s: %s", value, r.text)
        return None
    new_venue = r.json()
    metadata['venues'].append(new_venue)
    logger.info("Created venue for %s", value)
    return new_venue['id']


def get_organizer_id(metadata, value):
    for x in metadata['organizers']:
        if x['organizer'] == value:
            return x['id']
    return None


def get_tag_ids(metadata, slugs):
    tags = [get_tag_id(metadata, slug) for slug in slugs]
    if len(tags) == 0 and len(slugs) > 0:
        logger.warning("No tag: %s", slugs)
    return tags


def get_category_ids(metadata, slugs):
    return [get_category_id(metadata, slug) for slug in slugs]


def get_existing_event(event_map, post_data, processed_mobilize_ids):
    website = post_data['website']
    if 'mobilize.us' not in website:
        return None
    mobilize_id = events.get_event_id(website)
    if mobilize_id not in event_map:
        return None
    # We try to match mobilize slots and calendar events with the same day. Each time we find an event, we remove it
    # from the list of calendar events for that mobilize event. After all slots for a mobilize event have been
    # processed, any left over calendar events are orphaned and can be deleted.
    processed_mobilize_ids.add(mobilize_id)
    # The dates that come in here are a date string and time string separated by whitespace.
    start_date = post_data['start_date'].split()[0]
    calendar_events = event_map[mobilize_id]
    for event in calendar_events:
        if event['start_date'].split()[0] == start_date:
            calendar_events.remove(event)
            return event
    return None


def comma_list(s):
    if s == "":
        return []
    return s.split(sep=',')


def update_calendar(path):
    with open(path, newline='', encoding='utf-8') as ifile:
        reader = csv.reader(ifile)
        headers = next(reader)
        calendar_metadata = events.get_calendar_metadata()
        event_map = events.get_event_map()
        processed_mobilize_ids = set()
        for event in reader:
            title = event[headers.index('Event Name')]
            description = event[headers.index('Event Description')]
            website = event[headers.index('Event Website')]
            city = event[headers.index('City')]
            state = event[headers.index('State')]
            zip_code = headers.index('Zip Code')
            start_date = event[headers.index('Event Start Date')] + ' ' + event[headers.index('Event Start Time')]
            end_date = event[headers.index('Event End Date')] + ' ' + event[headers.index('Event End Time')]
            categories_slugs = comma_list(event[headers.index('Event Category')])
            organizer_organizer = event[headers.index('Event Organizers')]
            venue_venue = event[headers.index('Event Venue Name')]
            tags_slugs = comma_list(event[headers.index('Event Tags')])
            tag_ids = get_tag_ids(calendar_metadata, tags_slugs)
            category_ids = get_category_ids(calendar_metadata, categories_slugs)
            venue_id = get_venue_id(calendar_metadata, venue_venue, city, state, zip_code)
            organizer_id = get_organizer_id(calendar_metadata, organizer_organizer)
            region = event[headers.index('Region')]
            post_data = {'title': title,
                         'description': description,
                         'start_date': start_date,
                         'end_date': end_date,
                         'website': website
                         }
            # Not doing regions at the moment
            # if region:
            #     post_data[custom_field_map['region']] = region
            # There is a bug in The Events Calendar where tags and categories are documented to accept an array,
            # but in reality they take a single item. The documentation also says that various of the following can
            # take string names as values but in reality only providing ids seems to work.
            if len(tag_ids) > 0:
                post_data['tags'] = {'id': tag_ids[0]}
            else:
                pass
                # Do not remove tags until there is a better tag inference strategy
                # post_data['tags'] = {}
            if len(category_ids) > 0:
                post_data['categories'] = {'id': category_ids[0]}
            else:
                post_data['categories'] = {}
            if venue_id:
                post_data['venue'] = {'id': venue_id}
            if organizer_id:
                post_data['organizer'] = {'id': organizer_id}
            event = get_existing_event(event_map, post_data, processed_mobilize_ids)
            if event is not None:
                # Do not update manually created events
                if str(event['author']) != api_key.wordpress_automation_author_id:
                    logger.info("Skipping manually created event %s: %s", event['id'], event['rest_url'])
                    continue
                post_data['id'] = event['id']
                # Do not overwrite an inferred category since it is not reliable enough and may have been fixed manually
                post_data.pop('categories', None)
                logger.info("Updating %s: %s", event['id'], event['rest_url'])
            else:
                logger.info("Creating: %s %s %s", post_data['start_date'], post_data['title'], post_data['website'])
            logger.debug("post data: %s", pformat(post_data))
            if args.dry_run:
                continue
            if event is None:
                r = create_event(post_data)
            else:
                r = update_event(event['id'], post_data)
            if not r.ok:
                logger.error(r.text)
                continue
            returned_data = r.json()
            logger.info("Returned: %s %s", returned_data['id'], returned_data['url'])
            logger.debug(pformat(returned_data))
        # The sublists here contain events that no longer had a slot in mobilize and should be deleted.
        now = datetime.datetime.now()
        for mobilize_id in processed_mobilize_ids:
            for calendar_event in event_map[mobilize_id]:
                if datetime.datetime.strptime(calendar_event['start_date'], '%Y-%m-%d %H:%M:%S') > now:
                    logger.warning("Need to delete: %s", calendar_event['url'])


if __name__ == '__main__':
    update_calendar(args.csv_file)
