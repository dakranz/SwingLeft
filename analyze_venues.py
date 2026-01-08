import argparse
import time
import traceback

import events
import slack
import the_events_calendar


def find_orphaned_venues(calendar_events, venues):
    seen_venues = set()
    for event in calendar_events:
        if 'venue' in event and event['venue']:
            seen_venues.add(event['venue']['id'])
    for venue in venues:
        if venue['id'] in seen_venues:
            continue
        print('Deleting orphaned: ', venue['venue'])
        if not args.dry_run:
            events.delete_venue(venue['id'])
            time.sleep(1)
    print('\n')


def report_error(message):
    header = "<!channel> *Orphan venue detection failed*"
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": header}},
              {"type": "section", "text": {"type": "plain_text", "text": message}}]
    slack.post_message('automation', text=header, blocks=blocks)


parser = argparse.ArgumentParser()
parser.add_argument("-y", "--dry_run", action="store_true", help="Do not actually delete venues.")
parser.add_argument("-r", "--report", action="store_true", help="Report errors to slack.")
parser.add_argument("calendar", help="Which calendar to analyze.")
args = parser.parse_args()


def main():
    try:
        the_events_calendar.set_global_calendar(args.calendar)
        calendar_events = events.get_calendar_events()
        venues = events.get_calendar_metadata(kinds=['venues'])['venues']
        find_orphaned_venues(calendar_events, venues)
    except Exception as e:
        err_message = traceback.format_exc()
        if args.report:
            report_error(err_message)
        else:
            print(err_message)


main()

