import asyncio
import discord

from cogs.anilist.profile import ProfilePager, AchievementsView, FavoritesView

async def main():
    pages = [discord.Embed(title='Page 1'), discord.Embed(title='Page 2')]
    # create subviews
    achievements_view = AchievementsView({'achieved': [], 'progress': [], 'stats': {}}, {'name': 'Tester'}, 'http://avatar', 'http://profile')
    favorites_view = FavoritesView({'name': 'Tester', 'favourites': {}}, 'http://avatar', 'http://profile')
    pager = ProfilePager(pages, achievements_view, favorites_view)
    # set backrefs
    achievements_view.profile_pager = pager
    favorites_view.profile_pager = pager

    print('Pager children count:', len(pager.children))
    for child in pager.children:
        print(type(child), getattr(child, 'label', None), getattr(child, 'custom_id', None))

    print('\nAchievementsView children:')
    for child in achievements_view.children:
        print(type(child), getattr(child, 'label', None))

    print('\nFavoritesView children:')
    for child in favorites_view.children:
        print(type(child), getattr(child, 'label', None))

if __name__ == '__main__':
    asyncio.run(main())
