import datetime
from dateutil import parser
import sys

try:
    print(datetime.datetime.fromtimestamp(float(sys.argv[1])).strftime('%c'))
except ValueError:
    print(parser.parse(sys.argv[1]).timestamp())