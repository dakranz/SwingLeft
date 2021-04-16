import argparse
import csv
import datetime
from dateutil import parser
import io
import markdown
from pprint import pprint
import re

import the_events_calendar
import slack

_parser = argparse.ArgumentParser()
_parser.add_argument("--hours", type=int,
                       help="Hours ago for oldest event to process.")
_parser.add_argument("-t", "--timestamp", action="store_true",
                    help="Use value in slack-timestamp.txt as oldest event to process")
_parser.add_argument("-d", "--debug", action="store_true",
                    help="Log debug info.")
_parser.add_argument("-u", "--update_timestamp", action="store_true",
                    help="Update slack-timestamp.txt to current time.")
args = _parser.parse_args()

months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']


def get_time_str(info, am_pm):
    if ':' in info:
        return info + am_pm
    return info + ':00' + am_pm


# We are using the date parser which defaults to the current year if none is specified. That is wrong if the month is
# one that has already passed.
def validate_year(dt, year):
    if not year and datetime.datetime.now() > dt:
        dt = dt.replace(dt.year + 1)
    return dt


# We have specified that a datetime string in a message must contain the month, date, start-time, end-time, am/pm
# basically in that order and it does not matter what other stuff is in between each of them as long as the numbers
# can be parsed out. The year is optional as is an am/pm for the start-time (but at least one am/pm is required).
# The calendar requires an end time
# so we assume an hour if no range is specified. The month can be as in 'January 6' or /1/6'.
def get_date_range(s):
    s = s.strip().lower()
    month = None
    day = None
    start_time = end_time = None
    for m in months:
        if m in s:
            month = m
            break
    if month is None:
        month_part = re.match(r'(\d+)/', s)
        if month_part is None:
            return None, None
        month_num = month_part[0][0]
        month = months[int(month_num) - 1]
        s = s.replace(month_num, '', 1)
    y = re.findall(r'(\d\d\d\d)', s)
    if len(y) > 0:
        year = y[0]
    else:
        year = ''
    am_pm = re.findall(r'([ap]m)', s)
    if len(am_pm) == 0:
        return None, None
    if len(am_pm) == 1:
        am_pm.append(am_pm[0])
    dt_info = re.findall(r'([\d\:]+)', s)
    for info in dt_info:
        if info == year:
            continue
        if day is None:
            day = info
            continue
        if start_time is None:
            start_time = get_time_str(info, am_pm[0])
            continue
        if end_time is None:
            end_time = get_time_str(info, am_pm[1])
    if month is None or day is None or start_time is None:
        return None, None
    start_date = validate_year(parser.parse('{} {} {} {}'.format(month, day, year, start_time)), year)
    if end_time is None:
        end_date = start_date.replace(hour=start_date.hour + 1)
    else:
        end_date = validate_year(parser.parse('{} {} {} {}'.format(month, day, year, end_time)), year)
    return start_date, end_date


# Basically anything in the slack message can have markdown but the title for the calendar is plain text. We will see
# if this is good enough.
def remove_markdown(s):
    s = s.replace('\xa0', ' ')
    s = s.replace('*', '')
    s = s.replace('_', '')
    return s.strip()


# Slack uses an enhanced markdown but the calendar uses HTML. The slack enhancement is that there are things enclosed
# in angle brackets. The most important is a hyperlink which can also have some text following a vertical bar. So we
# pull out all the angle bracket things and convert to <a> format, and then transform the whole thing to html using
# the markdown package. We don't have to worry about the escaping of '<', '>', and '&' which is required in slack
# because it encodes those as HTML entities already.
# This is all documented at: https://api.slack.com/reference/surfaces/formatting
# TODO: handle the other funky things that could follow a '<'
def convert_description(description):
    buf = io.StringIO()
    next_start = 0
    for match in re.finditer('<.*?>', description):
        (start, end) = match.span()
        buf.write(description[next_start:start])
        next_start = end
        link = description[start + 1:end - 1].split(sep='|')
        url = link[0]
        text = url if len(link) == 1 else link[1]
        buf.write('<a href={}>{}</a>'.format(url, text))
    buf.write(description[next_start:])
    return markdown.markdown(buf.getvalue())


# This function pulls all the events from the channel since the specified time. The channel must use a format where
# messages have been shared with a header that is several lines. The forwarded message shows up as an attachment. The
# headers are as follows:
# Required: title
# Required: date range
# Optional: "Organizer:" followed by the organizer name
def slack_event_feed(start):
    messages = slack.get_messages('1-upcoming-events-for-the-next-month', start)
    records = []
    for message in messages:
        print('****************************')
        attachments = message.get('attachments', None)
        if attachments is None:
            continue
        assert len(attachments) == 1
        description = attachments[0]['text']
        if 'mobilize.us' in description:
            continue
        header_block = message['text'].splitlines()
        pprint(header_block)
        organizer = ''
        ts = datetime.datetime.fromtimestamp(float(message['ts'])).strftime('%c')
        if len(header_block) < 2:
            print("Event header must have time and date ts=", ts)
            continue
        title = remove_markdown(header_block[0])
        start_dt, end_dt = get_date_range(header_block[1])
        if start_dt is None:
            print("No date found for ts=", ts, header_block[1])
            continue
        event_start_date = start_dt.strftime("%Y-%m-%d")
        event_start_time = start_dt.strftime("%H:%M:00")
        event_end_date = end_dt.strftime("%Y-%m-%d")
        event_end_time = end_dt.strftime("%H:%M:00")
        if len(header_block) > 2:
            organizer = remove_markdown(header_block[2])
            index = organizer.find('Group:')
            if index >= 0:
                organizer = organizer[index + 6:]
        text = title + ' ' + description
        categories = []
        tags = []
        the_events_calendar.add_state_categories(categories, text)
        the_events_calendar.add_activity_categories(categories, text, title)
        the_events_calendar.add_tags(tags, text)
        description = convert_description(description)
        event_record = ['NEWSMAGIC ' + title, description, organizer, 'Online/Anywhere', event_start_date,
                        event_start_time, event_end_date, event_end_time, '', '', '',
                        ','.join(categories), ','.join(tags), '']
        records.append(event_record)
        print(title)
        print(event_start_date, event_start_time, event_end_date, event_end_time)
    out_name = '{}-cal-import.csv'.format(datetime.datetime.now().strftime("%Y-%m-%d %H;%M"))
    with open(out_name, mode='w', newline='', encoding='utf-8') as ofile:
        writer = csv.writer(ofile)
        writer.writerow(the_events_calendar.calendar_import_headers)
        writer.writerows(records)
    print(out_name)


def main():
    if len([x for x in [args.hours, args.timestamp] if x]) != 1:
        print('Must specify exactly one of -t or --hours')
        exit(1)
    now = int(datetime.datetime.now().timestamp())
    update_stamp = args.timestamp or args.update_timestamp
    if args.hours:
        slack_event_feed(now - args.hours * 3600)
    elif args.timestamp:
        with open('slack-timestamp.txt') as f:
            try:
                slack_event_feed(int(f.read()))
            except FileNotFoundError:
                print('No timestamp file')
                exit(1)
    if update_stamp:
        with open('slack-timestamp.txt', 'w') as f:
            f.write(str(now))


main()
