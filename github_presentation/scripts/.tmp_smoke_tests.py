import asyncio
import types

import discord
from helpers.steam_helper import (
    create_comparison_embed,
    create_recommendation_embed,
    get_price_string,
    ComparisonView,
    RecommendationView,
    ScreenshotView,
)

class FakeUser:
    def __init__(self, id=12345, name="Tester"):
        self.id = id
        self.name = name

class SyncResult:
    def __init__(self):
        self.msgs = []

    async def defer(self, ephemeral=True):
        self.msgs.append(('defer', ephemeral))

    async def send(self, *args, **kwargs):
        self.msgs.append(('send', args, kwargs))

    async def edit_message(self, *args, **kwargs):
        self.msgs.append(('edit', args, kwargs))

async def run_tests():
    print('Running smoke tests for steam helper Views/embeds...')

    # Create minimal fake data for two games
    game1 = {
        'id': 1000,
        'data': {
            'name': 'Game One',
            'is_free': False,
            'price_overview': {'final_formatted': '$9.99'},
            'release_date': {'date': 'Jan 1, 2020'},
            'genres': [{'description': 'Action'}, {'description': 'Adventure'}],
            'metacritic': {'score': 78}
        }
    }
    game2 = {
        'id': 2000,
        'data': {
            'name': 'Game Two',
            'is_free': True,
            'price_overview': None,
            'release_date': {'date': 'Feb 2, 2021'},
            'genres': [{'description': 'RPG'}],
            'metacritic': {'score': 85}
        }
    }

    # Test price string
    print('get_price_string game1 ->', get_price_string(game1['data']))
    print('get_price_string game2 ->', get_price_string(game2['data']))

    # Test comparison embed
    embed = create_comparison_embed(game1, game2)
    print('Comparison embed title:', embed.title)
    print('Comparison embed fields:', [(f.name, f.value) for f in embed.fields])

    # Test recommendation embed
    rec = {
        'app_id': 3000,
        'score': 4.2,
        'details': {
            'name': 'Rec Game',
            'short_description': 'A recommended game for testing',
            'header_image': '',
            'genres': [{'description': 'Indie'}],
            'price_overview': {'final_formatted': '$4.99', 'initial_formatted': '$9.99', 'discount_percent': 50},
            'is_free': False,
            'release_date': {'date': 'Mar 3, 2022'}
        }
    }
    rec_embed = create_recommendation_embed(rec, 1, 3)
    print('Recommendation embed title:', rec_embed.title)
    print('Recommendation embed footer:', rec_embed.footer.text)

    # Instantiate RecommendationView and run update
    rv = RecommendationView([rec], FakeUser())
    # call internal _update_buttons to ensure it doesn't crash
    try:
        rv._update_buttons()
        print('RecommendationView _update_buttons OK')
    except Exception as e:
        print('RecommendationView _update_buttons ERROR', e)

    # Instantiate ComparisonView
    try:
        cv = ComparisonView(game1, game2, session=None)
        print('ComparisonView instantiated OK')
    except Exception as e:
        print('ComparisonView instantiation ERROR', e)

    # Screenshot view test
    screenshots = [{'path_full': 'https://example.com/s1.png'}, {'path_full': 'https://example.com/s2.png'}]
    try:
        sv = ScreenshotView(screenshots, 'Test Game')
        e = sv.create_screenshot_embed(0)
        print('Screenshot embed title:', e.title)
    except Exception as e:
        print('ScreenshotView ERROR', e)

    print('All smoke tests completed.')

if __name__ == '__main__':
    asyncio.run(run_tests())
