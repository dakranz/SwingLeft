import base64
import requests
from pprint import pformat

import api_key
import events
import regions

auth_header = {'Authorization': 'Basic ' + base64.standard_b64encode(api_key.wordpress_app_password.encode()).decode(),
               'User-Agent': 'Foo bar'}
base_url = 'https://' + api_key.wordpress_host_name + '/wp-json/tribe/events/v1/events'


def update_event(event_id, json):
    return requests.post('{}/{}'.format(base_url, event_id), headers=auth_header, json=json)


def create_event(json):
    return requests.post(base_url, headers=auth_header, json=json)


def main(event_id):
    post_data = {'title': 'Custom field test',
                 'description': 'This is a custom field test',
                 'start_date': '2021-05-01 10:00:00',
                 'end_date': '2021-05-01 11:00:00',
                 '_ecp_custom_6': 'western-mass-events'
                 }
    if event_id is not None:
        post_data['id'] = event_id
    print(pformat(post_data))
    if event_id is None:
        r = create_event(post_data)
    else:
        r = update_event(event_id, post_data)
    print(r.text)


def delete_bad_venues(n):
    venues = calendar_metadata = events.get_calendar_metadata()['venues']
    i = 0
    for venue in venues:
        if "venue" not in venue:
            url = 'https://' + api_key.wordpress_host_name + '/wp-json/tribe/events/v1/venues/' + str(venue['id'])
            print(url)
            # r = requests.delete(url, headers=auth_header)
            # if not r.ok:
            #     print(r.text)
            i += 1
            if i >= n:
                break
    print(i)


#delete_bad_venues(250)
main(42759)
