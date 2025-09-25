import asyncio
import json
import os
import sys
import tempfile
import types
from pathlib import Path

# Ensure project root is on sys.path so `import cogs.finisher` works when running this script
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cogs.finisher as finisher_mod


class DummyChannel:
    def __init__(self, name="dummy"):
        self.name = name
        self.sent = []

    async def send(self, *args, **kwargs):
        # capture either embed or content for inspection
        if 'embed' in kwargs:
            payload = ('embed', kwargs['embed'])
        elif args:
            payload = ('arg', args[0])
        else:
            payload = ('empty', None)
        self.sent.append(payload)


class DummyBot:
    def __init__(self):
        self._channels = {}

    def add_channel(self, cid, channel):
        self._channels[int(cid)] = channel

    def get_channel(self, cid):
        return self._channels.get(int(cid))


async def async_main():
    # Use a temp directory for SAVE_FILE and CHANNEL_SAVE_FILE to avoid touching real data/
    td = tempfile.TemporaryDirectory()
    save_file = os.path.join(td.name, 'manga_scan_test.json')
    channel_file = os.path.join(td.name, 'manga_channel_test.json')

    # Monkeypatch module-level constants
    finisher_mod.SAVE_FILE = save_file
    finisher_mod.CHANNEL_SAVE_FILE = channel_file

    bot = DummyBot()
    # create finisher instance
    f = finisher_mod.Finisher(bot)

    # cancel any scheduled task started by the cog to avoid background runs during test
    try:
        f.daily_check.cancel()
    except Exception:
        pass

    # Prepare a fake manga list
    sample_manga = [
        {
            'id': 123,
            'title': {'english': 'Big Manga'},
            'status': 'FINISHED',
            'chapters': 100,
            'format': 'MANGA',
            'endDate': {'year': 2025, 'month': 9, 'day': 24},
            'coverImage': {'large': 'https://example.com/cover.jpg'},
            'siteUrl': 'https://anilist.co/manga/123'
        },
        {
            'id': 124,
            'title': {'romaji': 'Small OneShot'},
            'status': 'FINISHED',
            'chapters': 1,
            'format': 'ONE_SHOT',
            'endDate': {'year': 2025, 'month': 9, 'day': 24},
            'coverImage': {'large': None},
            'siteUrl': 'https://anilist.co/manga/124'
        }
    ]

    # Monkeypatch instance.fetch_manga to return our sample list
    async def fake_fetch(self):
        return sample_manga

    f.fetch_manga = types.MethodType(fake_fetch, f)

    # Test save_current and load_previous
    await f.save_current(sample_manga)
    prev = await f.load_previous()
    print('load_previous ->', prev)
    assert isinstance(prev, list)

    # Test filter_new_manga: prev contains ids, check behavior
    filtered = f.filter_new_manga(sample_manga, [])
    print('filter_new_manga with empty prev ->', [m['id'] for m in filtered])
    assert any(m['id'] == 123 for m in filtered), 'expected id 123 in filtered results'
    # one-shot should be filtered out
    assert all(m['id'] != 124 for m in filtered), 'one-shot should be excluded by filter'

    # Test channel persistence
    test_gid = 9999
    test_cid = 5555
    await f.save_defined_channel(test_gid, test_cid)
    loaded = await f.load_defined_channel(test_gid)
    print('saved channel ->', loaded)
    assert loaded == test_cid

    # Test post_updates: attach a dummy channel and ensure a message is sent
    dummy = DummyChannel()
    bot.add_channel(test_cid, dummy)

    # Ensure previous state is empty so that the manga triggers
    # overwrite previous to empty list
    with open(save_file, 'w', encoding='utf-8') as fh:
        json.dump([], fh)

    await f.post_updates(bot.get_channel(test_cid))
    print('dummy.sent ->', dummy.sent)
    # We expect at least one embed sent for id 123
    assert any(item[0] == 'embed' for item in dummy.sent), 'expected an embed to be sent'

    # Clean up temp dir
    td.cleanup()

    print('\nALL TESTS PASSED')


if __name__ == '__main__':
    asyncio.run(async_main())
