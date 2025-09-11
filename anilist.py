import re
import aiohttp
import discord
from discord.ext import commands
import logging

logger = logging.getLogger("AniListCog")
ANILIST_API_URL = "https://graphql.anilist.co"

# Regex to detect AniList activity links
ACTIVITY_REGEX = re.compile(r"https?://anilist\.co/activity/(\d+)")


class AniList(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --------------------------------------------
    # Fetch AniList Activity (Text/List/Message)
    # --------------------------------------------
    async def fetch_activity(self, activity_id: int):
        query = """
        query ($id: Int) {
            Activity(id: $id) {
                __typename
                ... on TextActivity {
                    id
                    type
                    text
                    createdAt
                    user {
                        name
                        siteUrl
                        avatar { large }
                        statistics { anime { count } manga { count } }
                    }
                    replies {
                        id
                        text
                        user {
                            name
                            siteUrl
                            avatar { large }
                        }
                    }
                }
                ... on ListActivity {
                    id
                    type
                    status
                    progress
                    createdAt
                    media {
                        title { romaji english }
                        siteUrl
                        coverImage { large }
                    }
                    user {
                        name
                        siteUrl
                        avatar { large }
                        statistics { anime { count } manga { count } }
                    }
                    replies {
                        id
                        text
                        user {
                            name
                            siteUrl
                            avatar { large }
                        }
                    }
                }
                ... on MessageActivity {
                    id
                    type
                    message
                    createdAt
                    messenger {
                        name
                        siteUrl
                        avatar { large }
                        statistics { anime { count } manga { count } }
                    }
                    recipient {
                        name
                        siteUrl
                        avatar { large }
                    }
                }
            }
        }
        """
        variables = {"id": activity_id}

        async with aiohttp.ClientSession() as session:
            async with session.post(ANILIST_API_URL, json={"query": query, "variables": variables}) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"AniList API request failed for activity {activity_id}: {response.status} {error_text}")
                    return None
                data = await response.json()
                return data.get("data", {}).get("Activity")

    # --------------------------------------------
    # Build Embed
    # --------------------------------------------
    def build_activity_embed(self, activity: dict) -> discord.Embed:
        typename = activity["__typename"]

        # 🌸 Common author info
        if typename == "MessageActivity":
            user = activity["messenger"]
        else:
            user = activity["user"]

        username = user["name"]
        avatar = user["avatar"]["large"]
        profile_url = user["siteUrl"]

        embed = discord.Embed(color=discord.Color.purple())
        embed.set_author(name=username, url=profile_url, icon_url=avatar)

        # ----------------------
        # TextActivity
        # ----------------------
        if typename == "TextActivity":
            embed.title = "💬 New Post"
            embed.description = activity.get("text", "—")

        # ----------------------
        # ListActivity
        # ----------------------
        elif typename == "ListActivity":
            media = activity.get("media", {})
            media_title = media.get("title", {}).get("english") or media.get("title", {}).get("romaji")
            media_url = media.get("siteUrl")
            progress = activity.get("progress")

            embed.title = f"📺 {username} {activity['status']} {progress or ''}".strip()
            embed.url = media_url
            embed.description = f"**{media_title}**"

            if media.get("coverImage", {}).get("large"):
                embed.set_thumbnail(url=media["coverImage"]["large"])

        # ----------------------
        # MessageActivity
        # ----------------------
        elif typename == "MessageActivity":
            recipient = activity.get("recipient", {})
            embed.title = f"📩 Message to {recipient.get('name')}"
            embed.url = recipient.get("siteUrl")
            embed.description = activity.get("message", "—")

        # ----------------------
        # Stats
        # ----------------------
        stats = user.get("statistics", {})
        anime_count = stats.get("anime", {}).get("count", "?")
        manga_count = stats.get("manga", {}).get("count", "?")
        embed.add_field(name="📊 Stats", value=f"Anime: **{anime_count}**\nManga: **{manga_count}**", inline=True)

        # ----------------------
        # Replies
        # ----------------------
        replies = activity.get("replies", [])
        if replies:
            reply_lines = []
            for reply in replies[:5]:
                reply_user = reply["user"]
                reply_name = reply_user["name"]
                reply_url = reply_user["siteUrl"]
                reply_avatar = reply_user["avatar"]["large"]
                reply_text = reply.get("text", "—")
                reply_lines.append(f"[![pfp]({reply_avatar})]({reply_url}) **[{reply_name}]({reply_url})**: {reply_text}")

            embed.add_field(
                name=f"💭 Replies ({len(replies)})",
                value="\n".join(reply_lines),
                inline=False
            )

        return embed

    # --------------------------------------------
    # Listener: Auto-detect AniList links
    # --------------------------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        match = ACTIVITY_REGEX.search(message.content)
        if not match:
            return

        activity_id = int(match.group(1))
        activity = await self.fetch_activity(activity_id)

        if not activity:
            await message.channel.send("❌ Could not fetch AniList activity.")
            return

        embed = self.build_activity_embed(activity)
        await message.channel.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AniList(bot))
