from stream_chat import StreamChat
from django.conf import settings

def get_stream_client():
    return StreamChat(api_key=settings.STREAM_API_KEY, api_secret=settings.STREAM_API_SECRET)

def create_user_on_stream(user):
    client = get_stream_client()
    client.upsert_user({
        "id": str(user.userID),
        "name": user.username
    })

def create_chat_channel(members, is_group=False, channel_name=None):
    client = get_stream_client()
    members = [str(member) for member in members]
    type_ = "messaging"
    id_ = channel_name or "-".join(sorted(members))  # use sorted for consistency

    return client.channel(type_, id=id_, data={"members": members}).create()
