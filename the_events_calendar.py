import base64
import io
import json
import logging
import re

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
logger.addHandler(sh)

calendar_name = None
wordpress_app_password = None
wordpress_host_name = None
wordpress_automation_author_id = None


def set_global_calendar(name):
    global calendar_name
    global wordpress_app_password
    global wordpress_host_name
    global wordpress_automation_author_id

    with open('calendars.json', encoding='utf-8') as f:
        calendar = json.load(f)['calendars'][name]
        calendar_name = name
        wordpress_app_password = calendar['wordpress_app_password']
        wordpress_host_name = calendar['wordpress_host_name']
        wordpress_automation_author_id = calendar['wordpress_automation_author_id']


def auth_header():
    return {'Authorization': 'Basic ' + base64.standard_b64encode(wordpress_app_password.encode()).decode(),
            'User-Agent': 'Foo bar'}


calendar_import_headers = ['Event Name', 'Event Description', 'Event Organizers', 'Event Venue Name',
                           'Event Start Date', 'Event Start Time', 'Event End Date', 'Event End Time',
                           'Event Website', 'City', 'State', 'Event Category', 'Event Tags', 'Zip Code',
                           'Region']


# Matching will be case-sensitive iff a search term has an uppercase char
event_tags = {"vote-by-mail": ["vote by mail", 'VBM', "vote-by-mail"],
              "voter-suppression": ["supression", "protecti", "watcher"],
              "voter-registration": ["reclaim our vote", "ROV", "registration", "register vote"],
              "gotv": ["get out the vote", "gotv"],
              }

activities = {"canvassing": ["canvas"],
              "phone-banking": ["phone"],
              "letters-postcards": [" letter", "postcard", "post card", "pick up", "pick up", "pick-up"],
              "texting": ["texting", "text bank", "textbank"],
              "fundraisers": ["fundrai"],
              "training": ["training"],
              "rallies": ["rally", "rallies"],
              "activism-huddle": ["activism huddle"]
              }

mobilize_event_type_map = {'CANVASS': 'canvassing', 'PHONE_BANK': 'phone-banking', 'TEXT_BANK': 'texting',
                           'MEETING': 'meeting', 'COMMUNITY': 'meeting', 'FUNDRAISER': 'fundraisers', 'MEET_GREET': None,
                           'HOUSE_PARTY': 'meeting', 'VOTER_REG': None, 'TRAINING': 'training',
                           'FRIEND_TO_FRIEND_OUTREACH': None, 'DEBATE_WATCH_PARTY': 'meeting', 'ADVOCACY_CALL': None,
                           'RALLY': 'rallies', 'TOWN_HALL': None, 'OFFICE_OPENING': None, 'BARNSTORM': None,
                           'SOLIDARITY_EVENT': None, 'COMMUNITY_CANVASS': 'canvassing', 'SIGNATURE_GATHERING': None,
                           'CARPOOL': 'travel', 'WORKSHOP': None, 'PETITION': None, 'AUTOMATED_PHONE_BANK': 'phone-banking',
                           'LETTER_WRITING': 'letters-postcards', 'LITERATURE_DROP_OFF': None, 'VISIBILITY_EVENT': 'rallies',
                           'SOCIAL_MEDIA_CAMPAIGN': None, 'POSTCARD_WRITING': 'letters-postcards', 'OTHER': None}


def has_real_venue(categories):
    return "letters-postcards" in categories or "rallies" in categories or "travel" in categories or "canvassing" in categories


# Using the events calendar tag slugs
states = {"florida": ["FL", "Florida"],
          "georgia": ["GA", "Georgia"],
          "new-hampshire": ["NH", "New Hampshire"],
          "north-carolina": ["NC", "North Carolina"],
          "pennsylvania": ["PA", "Pennsylvania"],
          }


def lookup_mobilize_event_type(mobilize_event_type):
    return mobilize_event_type_map.get(mobilize_event_type, None)


def get_state_tags(tags_list):
    tags = set([tag['name'] for tag in tags_list])
    for tag, strings in states.items():
        if strings[1] in tags:
            return tag, True
    if 'Democracy-national' in tags:
        return 'national' if 'news-magic' not in calendar_name else 'democracy-reform', False
    return None, False


def infer_state_tags(text):
    for tag, strings in states.items():
        pattern = '.*\\W{}\\W.*'.format(strings[0])
        if re.match(pattern, text) or strings[1] in text:
            return tag, True
    return None, False


def add_activity_categories(category_list, text, title):
    text = text.lower()
    added = False
    for category, strings in activities.items():
        for s in strings:
            if s in text:
                category_list.append(category)
                added = True
                break
    if 'fundraisers' in category_list:
        category_list.clear()
        category_list.append('fundraisers')
    if not added:
        category_list.append('meeting')
    return added


def add_tags(tag_list, text):
    lc_text = text.lower()
    for tag, strings in event_tags.items():
        for s in strings:
            if s in (lc_text if s.islower() else text):
                tag_list.append(tag)
                break


def strip_html_tags_and_split(text):
    buf = io.StringIO()
    next_start = 0
    for match in re.finditer('<.*?>', text):
        (start, end) = match.span()
        buf.write(' ')
        buf.write(text[next_start:start])
        next_start = end
    buf.write(' ')
    buf.write(text[next_start:])
    return re.split(r'\b[^\w\-\']+\b', buf.getvalue().strip())


def index(l, item, start):
    try:
        return l.index(item, start)
    except ValueError:
        return -1


def match_lists(org, target):
    max_match_count = 0
    next_index = -1
    while True:
        # First word must match case
        next_index = index(target, org[0], next_index + 1)
        if next_index < 0:
            break
        next_count = 1
        for i in range(1, len(org)):
            if next_index + i >= len(target) or org[i].lower() != target[next_index + i].lower():
                continue
            next_count += 1
        max_match_count = max(max_match_count, next_count)
    return max_match_count / len(org), max_match_count


def infer_organizer(organizers_list, specified_org, title, description):
    d_words = strip_html_tags_and_split(title + ' ' + description if not specified_org else specified_org)
    best_match = 0
    len_best_match = 0
    matches = []
    matched_organizer = None
    for x in organizers_list:
        match, len_match = match_lists(strip_html_tags_and_split(x['organizer']), d_words)
        if match >= best_match and match >= .75:
            if match > best_match or len_match > len_best_match:
                best_match = match
                len_best_match = len_match
                matches.append((match, x['organizer']))
                matched_organizer = x
    if best_match == 0:
        return None
    if len(matches) > 1:
        logger.warning("Multiple organizer matches: %s %s", specified_org, matches)
    return matched_organizer
