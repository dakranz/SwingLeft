import action_network
import csv
import json
import logging
from pathlib import Path
import sys
import tag_maps

handlers = [logging.FileHandler('output.log'), logging.StreamHandler()]

logging.basicConfig(level=logging.INFO, handlers=handlers)


def get_tags(state_info, interest_info):
    tags = []
    for tag, strings in tag_maps.states.items():
        for s in strings:
            if s in state_info:
                tags.append(tag)
                break
    for tag, strings in tag_maps.interests.items():
        for s in strings:
            if s in interest_info:
                tags.append(tag)
                break
    return tags


def upload_people(path):
    with open(Path(path), newline='', encoding='utf-8') as ifile:
        records = []
        reader = csv.reader(ifile)
        iheaders = next(reader)
        fn_index = iheaders.index('First Name')
        ln_index = iheaders.index('Last Name')
        email_index = iheaders.index('Email Address')
        phone_index = iheaders.index('Cell Phone')
        state_index = iheaders.index('I am interested in supporting Democratic campaigns in (check all that apply):')
        interest_index = iheaders.index('WORKING FROM MA. I am interested in (check all that apply):')

        for record in reader:
            if record[email_index] == '':
                continue
            tags = get_tags(record[state_index], record[interest_index])
            person = {"person": {"family_name": record[ln_index],
                                 "given_name": record[fn_index],
                                 "email_addresses": [{"address": record[email_index]}],
                                 "custom_fields": {"Phone": record[phone_index]}
                                 },
                      "add_tags": tags
                      }
            logging.info(json.dumps(action_network.add_person(person), indent=4))


upload_people(sys.argv[1])
