import datetime
import sys

print(datetime.datetime.fromtimestamp(float(sys.argv[1])).strftime('%c'))
