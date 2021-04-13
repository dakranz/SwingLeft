import slack

import csv
import datetime
import os
import re
import sys
import time


# date format is dd/mm/yyyy
# time format is hh:mm:ss
def make_date_time_string(start_date, start_time, end_date, end_time):
    start_date_string = datetime.datetime.strptime(start_date, '%Y-%m-%d').strftime('%A, %B %d')
    if start_date == end_date:
        return "*{}*\n{} - {}".format(start_date_string, convert_time(start_time), convert_time(end_time))
    end_date_string = datetime.datetime.strptime(end_date, '%Y-%m-%d').strftime('%A, %B %d')
    return "*{}* {} - \n*{}* {}".format(start_date_string, convert_time(start_time),
                                        end_date_string, convert_time(end_time))


def convert_time(t):
    t = datetime.datetime.strptime(t, "%H:%M:%S").strftime("%I:%M %p")
    if t[0] == '0':
        t = t[1:]
    return t


# Slack markdown is different than mobilize:
# In slack you must escape < and > and & as html entities.
# For links, Slack uses <url|text> but mobilize uses [text](url).
def post_mobilize_in_slack_channel(path, channel):
    with open(path, newline='', encoding='utf-8') as ifile:
        reader = csv.reader(ifile)
        headers = next(reader)
        event_name = headers.index('Event Name')
        event_description = headers.index('Event Description')
        event_organizers = headers.index('Event Organizers')
        event_venue_name = headers.index('Event Venue Name')
        event_start_date = headers.index('Event Start Date')
        event_start_time = headers.index('Event Start Time')
        event_end_date = headers.index('Event End Date')
        event_end_time = headers.index('Event End Time')
        event_website = headers.index('Event Website')
        city = headers.index('City')
        state = headers.index('State')
        event_category = headers.index('Event Category')
        event_tags = headers.index('Event Tags')
        event_featured_image = headers.index('Event Featured Image')
        for event in reader:
            title = "*{}*".format(event[event_name])
            description = event[event_description]
            i = description.find('\n\n<b><a target=_blank')
            if i >= 0:
                description = description[0:i] + '\n<{}|RSVP> here.'.format(event[event_website])
            image = event[event_featured_image]
            date = make_date_time_string(event[event_start_date], event[event_start_time],
                                         event[event_end_date], event[event_end_time])
            slack.post_message(channel,
                               text=title,
                               blocks=[{'type': 'section',
                                        'text': {'type': 'mrkdwn', 'text': title},
                                       },
                                       {'type': 'section',
                                        'text': {'type': 'mrkdwn', 'text': date}
                                        },
                                       #{'type': 'image', 'image_url': image, 'alt_text': image},
                                       {'type': 'section',
                                        'text': {'type': 'mrkdwn', 'text': description},
                                       }
                                      ]
                               )


if __name__ == '__main__':
    post_mobilize_in_slack_channel(sys.argv[1], '1-upcoming-events-for-the-next-month')
