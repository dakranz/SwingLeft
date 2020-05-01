import csv
from operator import itemgetter
import os
from pathlib import Path
import sys
from zipfile import ZipFile

# Avoid funky pathnames for windows
def sanitize_path(txt):
    return ''.join(c if c.isalnum() or c in '-. _' else ';' for c in txt)

# Take a csv file of events that was exported from MobilizeAmerica and generate a zip file containing cvs files that
# can be uploaded into ActionNetwork. We create a separate file for each (event id, event start time). The csv files
# are named to include the event id, the tag that should be used when uploading into ActionNetwork, the start time,
# and a prefix of the name of the event. We are assuming that the export files are utf-8.


def mobalize_america_to_action_network(path):
    oheaders = ('first_name', 'last_name', 'email', 'zip_code', 'phone')
    ofiles = {}
    with open(Path(path), newline='', encoding='utf-8') as ifile:
        records = []
        reader = csv.reader(ifile)
        iheaders = next(reader)
        fn_index = iheaders.index('first name')
        ln_index = iheaders.index('last name')
        email_index = iheaders.index('email')
        zip_index = iheaders.index('zip')
        phone_index = iheaders.index('phone')
        eid_index = iheaders.index('event id')
        ename_index = iheaders.index('event name')
        start_index = iheaders.index('start')
        tag_index = iheaders.index('tag')

        for record in reader:
            records.append(record)
        records.sort(key=itemgetter(eid_index, start_index))

        current_eid = None
        current_start = None
        current_tag = None
        out_records = None
        i = 0
        while i < len(records):
            record = records[i]
            if record[eid_index] != current_eid or record[start_index] != current_start:
                current_eid = record[eid_index]
                current_start = record[start_index]
                current_tag = record[tag_index]
                assert current_tag is not None
                out_records = []
                ofile = sanitize_path('{}-{}-{}-{}.csv'.format(current_start[:10], record[ename_index][:20],
                                      current_tag, current_eid))
                ofiles[ofile] = out_records
            out_records.append([record[fn_index], record[ln_index], record[email_index],
                                record[zip_index], record[phone_index]])
            i += 1

        os.chdir('generated')

        for fname, records in ofiles.items():
            assert not os.path.exists(fname), fname
            with open(Path(fname), 'w', newline='', encoding='ascii') as ofile:
                writer = csv.writer(ofile)
                writer.writerow(oheaders)
                writer.writerows(records)

        zipname = path[:-4] + '.zip'
        with ZipFile(Path(zipname), 'w') as myzip:
            for f in ofiles:
                myzip.write(f)


mobalize_america_to_action_network(sys.argv[1])
