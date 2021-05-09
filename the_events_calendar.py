import io
import re

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
              "texting": ["texting", "text bank"],
              "fundraiser": ["fundrai"],
              "training": ["training"],
              "briefing": ["briefing"]
              }


def has_real_venue(categories):
    return "letters-postcards" in categories


states = {"arizona-events": ["AZ", "Arizona"],
          "colorado-events": ["CO", "Colorado"],
          "florida-events": ["FL", "Florida"],
          "georgia-events": ["GA", "Georgia"],
          "iowa-events": ["IA", "Iowa"],
          "maine-events": ["ME", "Maine"],
          "michigan-events": ["MI", "Michigan"],
          "north-carolina-events": ["NC", "North Carolina"],
          "ohio-events": ["OH", "Ohio"],
          "pennsylvania-events": ["PA", "Pennsylvania"],
          "texas-events": ["TX", "Texas"],
          "wisconsin-events": ["WI", "Wisconsin"]
          }


def add_state_categories(category_list, text):
    # Need to figure this out
    return
    state_list = []
    for category, strings in states.items():
        # only doing GA for now
        if category != 'georgia-events':
            continue
        pattern = '.*\\W{}\\W.*'.format(strings[0])
        if re.match(pattern, text) or strings[1] in text:
            state_list.append(category)
    if len(state_list) == 1:
        category_list.append(state_list[0])
    elif len(state_list) >=2:
        print("Multiple states:", state_list)
        category_list.extend(state_list)


def add_activity_categories(category_list, text, title):
    text = text.lower()
    added = False
    for category, strings in activities.items():
        for s in strings:
            if s in text:
                category_list.append(category)
                added = True
                break
    if 'phone-calls' in category_list and 'training' in category_list and 'training' not in title:
        category_list.remove('training')


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
    return max_match_count / len(org)


def infer_organizer(organizers_list, specified_org, title, description):
    d_words = strip_html_tags_and_split(title + ' ' + description if not specified_org else specified_org)
    best_match = 0
    matches = []
    matched_organizer = None
    for x in organizers_list:
        match = match_lists(strip_html_tags_and_split(x['organizer']), d_words)
        if match > best_match and match > .65:
            best_match = match
            matches.append(match)
            matched_organizer = x
    if best_match == 0:
        return None
    if len(matches) > 1:
        print("Warning: multiple organizer matches: ", matches)
    return matched_organizer
