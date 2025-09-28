import asyncio
import types
import logging

from cogs.server_management.invite_tracker import InviteTracker

# Prepare fake async DB executor to capture SQL and return simulated rows
async def fake_execute_db_operation(description, sql, params=None, fetch_type=None):
    print(f"DB OPERATION: {description}")
    print("SQL:", sql)
    print("PARAMS:", params)
    # Simulate returning None for inviter lookup
    if description == "get inviter for leaving member":
        return None
    if description == "record member leave":
        print("Simulated insert into user_leaves")
        return None
    return None

# Minimal fake objects to feed into the cog
class FakeChannel:
    def __init__(self, name='announce'):
        self.name = name
        self.sent = []
    def permissions_for(self, member):
        class Perms: send_messages = True
        return Perms()
    async def send(self, msg):
        print(f"Channel.send(): {msg}")
        self.sent.append(msg)

class FakeGuild:
    def __init__(self, id=123, name='TestGuild'):
        self.id = id
        self.name = name
        self._channels = {999: FakeChannel('announce')}
        self.me = None
    def get_channel(self, cid):
        return self._channels.get(cid)

class FakeMember:
    def __init__(self, id=456, display_name='Leaver', guild=None, joined_at=None):
        self.id = id
        self.display_name = display_name
        self.guild = guild
        self.joined_at = joined_at
        self.bot = False

async def run_test():
    # Instantiate the cog (bot is not needed for this test)
    cog = InviteTracker(bot=None)

    # Monkeypatch the DB operation used inside the cog
    cog.execute_db_operation = fake_execute_db_operation
    # Also patch module-level name used by other functions
    import cogs.server_management.invite_tracker as mod
    mod.execute_db_operation = fake_execute_db_operation

    # Prepare guild, channel, and map announcement channel
    guild = FakeGuild(id=321, name='UnitTestGuild')
    cog.announcement_channels[guild.id] = 999

    # Create member with a naive joined_at datetime
    import datetime
    joined = datetime.datetime.utcnow()
    member = FakeMember(id=1337, display_name='cinemonkwu', guild=guild, joined_at=joined)

    print('Calling on_member_remove...')
    await cog.on_member_remove(member)
    print('Done')

if __name__ == '__main__':
    asyncio.run(run_test())
