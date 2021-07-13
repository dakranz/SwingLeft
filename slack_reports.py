import csv
import datetime

import slack


def populate_user_history(users, last_ts):
    conversations = slack.get_conversations()
    for c in conversations:
        channel_name = c['name']
        if channel_name == "" or channel_name[0] in '0123456789x':
            continue
        print(channel_name)
        slack.invite_bot(c['id'])
        for message in slack.get_messages(channel_name, last_ts):
            if message['type'] != 'message' or message.get('subtype', None) is not None:
                continue
            if message['user'] not in users:
                continue
            user = users[message['user']]
            ts = float(message['ts'])
            user['channels_posted'].add(channel_name)
            if ts > user['last_post_time']:
                user['last_post_time'] = ts
                user['last_post_channel'] = channel_name
                user['last_post_text'] = message['text']


def populate_billing_info(users):
    for user, billing_status in slack.get_billable_info().items():
        if user in users and billing_status['billing_active']:
            users[user]['billing_status'] = 'Yes'


def generate_user_report():
    headers = ['Name', 'Title', 'Email', 'Last Post Time', 'Last Post Channel', 'Last Post Text',
               'Billing Active', 'Channels Posted']
    users = {}
    for user in slack.get_news_magic_users():
        if user['is_bot'] or user['real_name'] == 'Slackbot':
            continue
        profile = user['profile']
        users[user['id']] = {'name': profile['real_name'], 'title': profile['title'], 'email': profile['email'],
                             'last_post_time': 0, 'last_post_channel': None, 'channels_posted': set(),
                             'last_post_text': ''}
    now = datetime.datetime.now()
    # populate_user_history(users, (now - datetime.timedelta(weeks=8)).timestamp())
    populate_user_history(users, 0)
    populate_billing_info(users)
    out_name = '{}-slack_report.csv'.format(now.strftime("%Y-%m-%d %H;%M;%S"))
    with open(out_name, mode='w', newline='', encoding='utf-8') as ofile:
        writer = csv.writer(ofile)
        writer.writerow(headers)
        for user in users.values():
            if user['last_post_time'] == 0:
                continue
            last_post_time = datetime.datetime.fromtimestamp(user['last_post_time']).strftime('%Y-%m-%d %H:%M:%S')
            last_post_channel = user['last_post_channel']
            writer.writerow([user['name'], user['title'], user['email'], last_post_time, last_post_channel,
                             user['last_post_text'], user.get('billing_status', 'No'),
                             ','.join(list(user['channels_posted']))])
    print(out_name)


generate_user_report()