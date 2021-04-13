calendar_import_headers = ['Event Name', 'Event Description', 'Event Organizers', 'Event Venue Name',
                           'Event Start Date', 'Event Start Time', 'Event End Date', 'Event End Time',
                           'Event Website', 'City', 'State', 'Event Category', 'Event Tags', 'Event Featured Image']


state_categories = {'RI': 'rhode-island-events',
                    'VT': 'vermont-events',
                    'CT': 'connecticut-events',
                    'ME': 'maine-events-2'
                   }

other_states = 'outside-new-england'


# Matching will be case-sensitive iff a search term has an uppercase char
event_tags = {"vote-by-mail": ["vote by mail", 'VBM', "vote-by-mail"],
              "voter-suppression": ["supression", "protecti", "watcher"],
              "voter-registration": ["reclaim our vote", "ROV", "registration", "register vote"],
              "gotv": ["get out the vote", "gotv"],
              }

activities = {"canvassing": ["canvas"],
              "phone-calls": ["phone"],
              "postcards-letters": ["letter", "postcard", "post card", "pick up", "pick up", "pick-up"],
              "texting": ["texting"],
              "fundraiser": ["fundrai"],
              "training": ["training"],
              "briefing": ["briefing"]
              }

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
