from slack_sdk import WebClient
import api_key
from pprint import pprint


def get_messages(channel_name, last_fetched):
    client = WebClient(token=api_key.slack_news_magic_key)
    conversations = client.conversations_list(types='private_channel,public_channel')
    channel_id = None
    for c in conversations['channels']:
        if c['name'] == channel_name:
            channel_id = c['id']
            break
    assert channel_id is not None
    return client.conversations_history(channel=channel_id, oldest=last_fetched)['messages']


def post_message(channel_name, text="", blocks=[]):
    client = WebClient(token=api_key.dkranz_test_key)
    conversations = client.conversations_list()
    channel_id = None
    for c in conversations['channels']:
        if c['name'] == channel_name:
            channel_id = c['id']
            break
    assert channel_id is not None
    client.chat_postMessage(channel=channel_id, text=text, blocks=blocks)

#get_messages('1-upcoming-events-for-the-next-month', '1615179600')
#post_message('slack-integration', attachments=[{"pretext": "*title*\ndate", "text": "hello-world"}])
