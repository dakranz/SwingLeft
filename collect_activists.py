import csv
from pathlib import Path
import sys


def add_activists(path, activists):
    print(path)
    with open(Path(path), newline='', encoding='utf-8') as ifile:
        reader = csv.reader(ifile)
        iheaders = next(reader)
        fn_index = iheaders.index('first name')
        ln_index = iheaders.index('last name')
        email_index = iheaders.index('email')
        zip_index = iheaders.index('zip')
        phone_index = iheaders.index('phone')

        for record in reader:
            zip_code = record[zip_index]
            if len(zip_code) == 4:
                zip_code = '0' + zip_code
            activists[record[email_index]] = ([record[fn_index], record[ln_index], record[email_index],
                                zip_code, record[phone_index]])


def collect_activists(file_list_name):
    oheaders = ('first_name', 'last_name', 'email', 'zip_code', 'phone')
    activists = {}
    with open(file_list_name + '.txt', "r") as paths:
        files = paths.read().splitlines()
    for file in files:
        add_activists('archived/' + file, activists)
    with open(Path(file_list_name + '-activists.csv'), 'w', newline='', encoding='utf-8') as ofile:
        writer = csv.writer(ofile)
        writer.writerow(oheaders)
        for email, record in activists.items():
            writer.writerow(record)


collect_activists(sys.argv[1])
