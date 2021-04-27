import argparse
import csv
import datetime
from dateutil import parser
import io
import logging
import markdown
from pprint import pformat
import re
import shutil

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

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG if args.debug else logging.INFO)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
logger.addHandler(sh)

months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']


def get_time_str(info, am_pm):
    if ':' in info:
        return info + am_pm
    return info + ':00' + am_pm


# We are using the date parser which defaults to the current year if none is specified. That is wrong if the month is
# one that has already passed. Only up the year at six month boundary in case we pick up an older event for some reason.
def validate_year(dt, year):
    if not year and datetime.datetime.now() - datetime.timedelta(weeks=26) > dt:
        dt = dt.replace(dt.year + 1)
    return dt


# We have specified that a datetime string in a message must contain the month, date, start-time, end-time, am/pm
# basically in that order and it does not matter what other stuff is in between each of them as long as the numbers
# can be parsed out. The year is optional as is an am/pm for the start-time (but at least one am/pm is required).
# The calendar requires an end time
# so we assume an hour if no range is specified. The month can be as in 'January 6' or /1/6'. It is also possible that
# the date will be inside a markup link.
def get_date_range(s):
    s = s.strip().lower()
    link_match = re.match(r'<.*\|(.*?)>', s)
    if link_match:
        return get_date_range_no_link(link_match[1])
    return get_date_range_no_link(s)


def get_date_range_no_link(s):
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
    process_slack_messages(messages)


def process_slack_messages(messages):
    now = datetime.datetime.now()
    records = []
    for message in messages:
        ts = datetime.datetime.fromtimestamp(float(message['ts'])).strftime('%c')
        logger.info('****************************')
        logger.debug(pformat(message))
        attachments = message.get('attachments', None)
        if attachments is None:
            logger.warning("Message has no attachment: ts=%s", ts)
            continue
        description = '\n\n'.join([a['text'] for a in attachments])
        header_block = message['text'].splitlines()
        logger.info(pformat(header_block))
        if 'mobilize.us/swingleftbos' in description:
            logger.info('Ignoring message with swing left boston mobilize event')
            continue
        organizer = ''
        title = remove_markdown(header_block[0])
        text = title + ' ' + description
        categories = []
        tags = []
        the_events_calendar.add_activity_categories(categories, text, title)
        for attachment in attachments:
            if 'channel_name' in attachment:
                tags.append(attachment['channel_name'])
        date_lines = []
        for line in header_block[1:]:
            # remove markup bold
            line = line.replace('*', '').strip()
            if len(line) == 0:
                continue
            m = re.match(r'(\w+)\s*:(.*)', line)
            if m is None:
                date_lines.append(line)
                continue
            key = m[1].lower()
            value = m[2].strip()
            if key == 'group':
                organizer = value
            elif key == 'rsvp':
                description += ('\n\n' + value)
            elif key == 'activity':
                categories = [value]
        description += '\n\nImported from NewsMAGIC'
        description = convert_description(description)
        logger.info(title)
        if len(date_lines) == 0:
            logger.warning("No date found: ts=%s", ts)
        for line in date_lines:
            start_dt = end_dt = None
            try:
                start_dt, end_dt = get_date_range(line)
            except ValueError:
                pass
            if start_dt is None:
                logger.warning("Bad date string: %s", line)
                continue
            if start_dt < now:
                logger.warning("Date has already past: %s", line)
                continue
            event_start_date = start_dt.strftime("%Y-%m-%d")
            event_start_time = start_dt.strftime("%H:%M:00")
            event_end_date = end_dt.strftime("%Y-%m-%d")
            event_end_time = end_dt.strftime("%H:%M:00")
            event_record = [title, description, organizer, 'Online/Anywhere', event_start_date,
                            event_start_time, event_end_date, event_end_time, '', '', '',
                            ','.join(categories), ','.join(tags), '', '']
            records.append(event_record)
            logger.info("start: %s %s end: %s %s", event_start_date, event_start_time, event_end_date, event_end_time)
    if len(records) == 0:
        return
    out_name = '{}-cal-import.csv'.format(now.strftime("%Y-%m-%d %H;%M;%S"))
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
        shutil.copy('slack-timestamp.txt', 'slack-timestamp-last.txt')
        with open('slack-timestamp.txt', 'w') as f:
            f.write(str(now))


if __name__ == '__main__':
    main()

