import api_key
import requests

entry_point = 'https://actionnetwork.org/api/v2/'
api_header = {'Content-Type': 'application/json', 'OSDI-API-Token': api_key.action_network_key}


def add_person(data):
    url = entry_point + 'people/'
    r = requests.post(url, json=data, headers=api_header)
    assert r.status_code == 200
    return r.json()


def get_person(email):
    url = entry_point + 'people/'
    r = requests.get(url, headers=api_header, params={'filter': 'email_address eq \'{}\''.format(email)})
    assert r.status_code == 200
    people = r.json()['_embedded']['osdi:people']
    assert len(people) < 2
    if len(people) == 0:
        return None
    return people[0]


