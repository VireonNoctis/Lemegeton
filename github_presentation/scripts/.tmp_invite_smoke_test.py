import asyncio
from datetime import datetime, timezone, timedelta

# Lightweight smoke test for InviteTracker (offline)
# Creates dummy bot/guild/member/invite objects and runs on_member_join/on_member_remove

async def main():
    from cogs.server_management.invite_tracker import InviteTracker
    import cogs.server_management.invite_tracker as invite_mod

    # Capture DB operations for inspection
    db_ops = []

    async def fake_execute_db_operation(desc, query, params=(), fetch_type=None):
        db_ops.append((desc, query, params, fetch_type))
        # Simulate returning a previous inviter when asked for leaving member
        if desc == "get inviter for leaving member":
            return (42,) if fetch_type == 'one' else [(42,)]
        if desc == "get recruit count":
            return (1,) if fetch_type == 'one' else None
        # Return no data for selects
        if fetch_type == 'one':
            return None
        return []

    # Monkeypatch the module-level DB helper so InviteTracker calls our fake
    invite_mod.execute_db_operation = fake_execute_db_operation

    # Create dummy objects
    class DummyChannel:
        def __init__(self, id, name="test-channel"):
            self.id = id
            self.name = name
            self.sent_messages = []
        def permissions_for(self, me):
            class P: send_messages = True
            return P()
        async def send(self, content=None, **kwargs):
            self.sent_messages.append((content, kwargs))
            return None

    class DummyGuild:
        def __init__(self, id, name, channel: DummyChannel):
            self.id = id
            self.name = name
            self._channel = channel
            self.me = object()
            # invites to return is set externally
            self._invites_to_return = []
        def get_channel(self, cid):
            return self._channel if self._channel.id == cid else None
        async def invites(self):
            return list(self._invites_to_return)

    class DummyMember:
        def __init__(self, id, display_name, guild, joined_at=None, bot=False):
            self.id = id
            self.display_name = display_name
            self.guild = guild
            self.joined_at = joined_at
            self.bot = bot
        @property
        def mention(self):
            return f"<@{self.id}>"

    class DummyInvite:
        def __init__(self, code, inviter, channel, max_uses=None, uses=0):
            self.code = code
            self.inviter = inviter
            self.channel = channel
            self.max_uses = max_uses
            self.uses = uses

    class DummyBot:
        def __init__(self, guilds):
            self.guilds = guilds
        def get_guild(self, gid):
            for g in self.guilds:
                if g.id == gid:
                    return g
            return None
        def is_ready(self):
            return True

    # Setup guild, channel, bot
    channel = DummyChannel(111, "announcements")
    guild = DummyGuild(1, "GuildOne", channel)
    bot = DummyBot([guild])

    # Instantiate tracker
    tracker = InviteTracker(bot)

    # Configure guild as opt-in
    tracker.announcement_channels[guild.id] = channel.id

    # Prepare initial cached invite (uses=0)
    inviter = DummyMember(42, "InviterUser", guild)
    invite_code = "abc123"
    cached_invite = DummyInvite(invite_code, inviter, channel, uses=0)
    tracker.invite_cache[guild.id] = [cached_invite]

    # Simulate current invites where invite uses increased to 1
    current_invite = DummyInvite(invite_code, inviter, channel, uses=1)
    guild._invites_to_return = [current_invite]

    # Simulate a new member joining
    new_member = DummyMember(99, "NewUser", guild, joined_at=datetime.now(timezone.utc))

    print("Before join: cached_invites=", [(i.code, i.uses) for i in tracker.invite_cache[guild.id]])
    await tracker.on_member_join(new_member)
    print("After join: cached_invites=", [(i.code, i.uses) for i in tracker.invite_cache[guild.id]])
    print("Channel messages sent:", channel.sent_messages)
    print("DB ops recorded:")
    for op in db_ops:
        print(op[0])

    # Now simulate leaving: ensure invite_uses contains inviter via fake DB
    # Create a leave member with joined_at 5 days ago
    leave_member = DummyMember(99, "NewUser", guild, joined_at=datetime.now(timezone.utc)-timedelta(days=5))
    await tracker.on_member_remove(leave_member)
    print("After leave: channel messages sent:", channel.sent_messages)
    print("DB ops recorded (total):", len(db_ops))

if __name__ == '__main__':
    asyncio.run(main())
