This package contains code to pull event data from
various event sources and to post them to the wordpress 
events calendar. It currently supports pulling events from
slack and mobilize.

When events are pulled they are written to a csv file as a
common format. The calendar update code reads the csv files.

These are the runnable scripts:

events.py -- This script downloads all the data from the events calendar
and stores it locally so it can be used for testing and debugging.

mobilize_event_feed.py - This script pulls events from mobilize and writes a csv file

slack_event_feed.py -- This script pulls events from slack and writes a csv file.

update_calendar.py -- This script reads a csv file containing events and 
creates or updates them in the calendar.