import datetime
from dateutil import parser
import sys

try:
    print(datetime.datetime.fromtimestamp(float(sys.argv[1])).strftime('%c'))
except ValueError:
    if 'timestamp' in sys.argv[1]:
        with open(sys.argv[1]) as f:
            print(datetime.datetime.fromtimestamp(float(f.read())).strftime('%c'))
    else:
        print(parser.parse(sys.argv[1]).timestamp())