import datetime
import sys

print(datetime.datetime.fromtimestamp(int(sys.argv[1])).strftime('%c'))
