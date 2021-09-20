import base64
import json
import requests
from pprint import pformat

import events
import regions
import the_events_calendar

the_events_calendar.set_global_calendar('sba')

auth_header = {'Authorization': 'Basic ' + base64.standard_b64encode(the_events_calendar.wordpress_app_password.encode()).decode(),
               'User-Agent': 'Foo bar'}
base_url = 'https://' + the_events_calendar.wordpress_host_name + '/wp-json/tribe/events/v1/events'


def update_event(event_id, json):
    return requests.post('{}/{}'.format(base_url, event_id), headers=auth_header, json=json)


def create_event(json):
    return requests.post(base_url, headers=auth_header, json=json)


def main(event_id):
    post_data = {'title': 'Post test',
                 'description': 'This is a post test',
                 'start_date': '2021-12-01 10:00:00',
                 'end_date': '2021-12-01 11:00:00',
                 'tags': {'id': 6337},
                 'categories': {'id': 6344}
                 }
    if event_id is not None:
        post_data['id'] = event_id
    print(pformat(post_data))
    if event_id is None:
        r = create_event(post_data)
    else:
        r = update_event(event_id, post_data)
    print(pformat(r.json()))


# def delete_bad_venues(n):
#     venues = calendar_metadata = events.get_calendar_metadata()['venues']
#     i = 0
#     for venue in venues:
#         if "venue" not in venue:
#             url = 'https://' + the_events_calendar.wordpress_host_name + '/wp-json/tribe/events/v1/venues/' + str(venue['id'])
#             print(url)
#             # r = requests.delete(url, headers=auth_header)
#             # if not r.ok:
#             #     print(r.text)
#             i += 1
#             if i >= n:
#                 break
#     print(i)
#

#delete_bad_venues(250)
main(44489)

# url = 'https://files.slack.com/files-pri/T01H6FDKJ12-F01VC97DBAN/download/ruralcaucus-i1.png'
# r = requests.get(url, headers={'Authorization': 'Bearer ' + api_key.slack_news_magic_key})
# with open('test.png', 'wb') as f:
#     f.write(r.content)


# media = {'file': open('test.png', "rb"), 'caption': 'My great demo picture'}
# r = requests.post('https://' + api_key.wordpress_host_name + "/wp-json/wp/v2/media", headers=auth_header, files=media)
# if not r.ok:
#     print(r.text)
# else:
#     print(pformat(r.json))

# r = requests.post('https://' + api_key.wordpress_host_name + "/wp-json/wp/v2/media/42795", headers=auth_header,
#                   json={'id': 42795, "slug": 'this-is-a-test-slug'})
# print(pformat(r.json()))
