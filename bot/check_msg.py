import json
import os

MESSAGE_FILE = "bug_message.json"


def load_sent_messages():
    if not os.path.exists(MESSAGE_FILE):
        return {}
    with open(MESSAGE_FILE, "r") as f:
        return json.load(f)


def save_sent_message(guild_id, message_id):
    data = load_sent_messages()
    data[str(guild_id)] = message_id
    with open(MESSAGE_FILE, "w") as f:
        json.dump(data, f)
