from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import api_key
from pprint import pprint


def get_billable_info():
    client = WebClient(token=api_key.slack_user_key)
    return client.team_billableInfo(team_id=api_key.slack_news_magic_team_id)['billable_info']


def invite_bot(channel_id):
    client = WebClient(token=api_key.slack_user_key)
    try:
        client.conversations_invite(channel=channel_id, users=api_key.slack_bot_id)
    except SlackApiError:
        # Bot is already in channel
        pass


def get_conversations():
    client = WebClient(token=api_key.slack_news_magic_key)
    return client.conversations_list()['channels']


def get_channel_id(client, channel_name):
    conversations = client.conversations_list(types='private_channel,public_channel')
    channel_id = None
    for c in conversations['channels']:
        if c['name'] == channel_name:
            channel_id = c['id']
            break
    assert channel_id is not None
    return channel_id


def get_messages(channel_name, last_fetched):
    client = WebClient(token=api_key.slack_news_magic_key)
    all_messages = []
    cursor = ""
    while True:
        messages = client.conversations_history(channel=get_channel_id(client, channel_name),
                                                oldest=last_fetched,
                                                cursor=cursor)
        all_messages.extend(messages['messages'])
        if messages.get('response_metadata', None) is None or messages['response_metadata']['next_cursor'] == '':
            return all_messages
        cursor = messages['response_metadata']['next_cursor']


def post_message(channel_name, text="", blocks=[]):
    client = WebClient(token=api_key.slack_slgb_key)
    client.chat_postMessage(channel=get_channel_id(client, channel_name), text=text, blocks=blocks)


def get_news_magic_users():
    client = WebClient(token=api_key.slack_news_magic_key)
    users = []
    cursor = ""
    while True:
        next_users = client.users_list(cursor=cursor, limit=200)
        users.extend(next_users['members'])
        if next_users.get('response_metadata', None) is None or next_users['response_metadata']['next_cursor'] == '':
            return users
        cursor = next_users['response_metadata']['next_cursor']


#get_messages('1-upcoming-events-for-the-next-month', '1615179600')
#post_message('slack-integration', attachments=[{"pretext": "*title*\ndate", "text": "hello-world"}])
