import csv
import os
import sys
import tempfile


def fix_zipcodes(path):
    with open(path, newline='', encoding='utf-8') as ifile, tempfile.NamedTemporaryFile(
            dir=os.path.dirname(path), mode='w', newline='', encoding='utf-8', delete=False) as ofile:
        reader = csv.reader(ifile)
        writer = csv.writer(ofile)
        headers = next(reader)
        zip_index = headers.index('zip')
        writer.writerow(headers)
        for record in reader:
            zip_code = record[zip_index]
            if len(zip_code) == 4:
                zip_code = '0' + zip_code
                record[zip_index] = zip_code
            writer.writerow(record)

    os.remove(path)
    os.rename(ofile.name, path)


fix_zipcodes(sys.argv[1])
