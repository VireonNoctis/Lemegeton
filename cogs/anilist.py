import re
import aiohttp
import discord
from discord.ext import commands
from discord.ui import View, Button

API_URL = "https://graphql.anilist.co"

ACTIVITY_QUERY = """
query ($id: Int) {
  Activity(id: $id) {
    __typename
    ... on TextActivity {
      id
      text
      siteUrl
      createdAt
      likeCount
      replyCount
      user {
        name
        siteUrl
        avatar { large }
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
      status
      progress
      siteUrl
      createdAt
      likeCount
      replyCount
      media {
        id
        siteUrl
        title { romaji english }
        coverImage { large }
      }
      user {
        name
        siteUrl
        avatar { large }
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
      message
      siteUrl
      createdAt
      likeCount
      replyCount
      messenger {
        name
        siteUrl
        avatar { large }
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

class PageView(View):
    def __init__(self, pages):
        super().__init__(timeout=180)
        self.pages = pages
        self.index = 0

    async def update(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    @discord.ui.button(label="◀️ Prev", style=discord.ButtonStyle.blurple)
    async def prev_page(self, interaction: discord.Interaction, button: Button):
        self.index = (self.index - 1) % len(self.pages)
        await self.update(interaction)

    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.blurple)
    async def next_page(self, interaction: discord.Interaction, button: Button):
        self.index = (self.index + 1) % len(self.pages)
        await self.update(interaction)


class AniListCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------------------
    # Fetch activity
    # ---------------------------
    async def fetch_activity(self, activity_id: int):
        async with aiohttp.ClientSession() as session:
            async with session.post(
                API_URL,
                json={"query": ACTIVITY_QUERY, "variables": {"id": activity_id}},
            ) as resp:
                if resp.status != 200:
                    print(f"[ERROR] AniList API request failed for activity {activity_id}: {resp.status}")
                    return None
                data = await resp.json()
                return data.get("data", {}).get("Activity")

    # ---------------------------
    # Clean text + extract images
    # ---------------------------
    def process_text_and_media(self, text: str):
        if not text:
            return "—", []

        matches = re.findall(r"img\d+\((https?://[^\)]+)\)", text)
        cleaned = re.sub(r"img\d+\((https?://[^\)]+)\)", "", text)
        return cleaned.strip(), matches

    # ---------------------------
    # Build star rating
    # ---------------------------
    def star_rating(self, likes: int, max_likes: int = 100) -> str:
        if max_likes <= 0:
            return "☆☆☆☆☆ (0/5)"
        score = (likes / max_likes) * 5
        full = int(score)
        half = 1 if (score - full) >= 0.5 else 0
        empty = 5 - full - half
        stars = "⭐" * full + "½" * half + "☆" * empty
        return f"{stars} ({round(score,1)}/5)"

    # ---------------------------
    # Build embeds with pagination
    # ---------------------------
    def build_activity_embeds(self, activity: dict) -> list[discord.Embed]:
        typename = activity["__typename"]

        # pick main user
        user = activity["messenger"] if typename == "MessageActivity" else activity["user"]

        username = user["name"]
        avatar = user["avatar"]["large"]
        profile_url = user["siteUrl"]

        base_embed = discord.Embed(color=discord.Color.purple())
        base_embed.set_author(name=username, url=profile_url, icon_url=avatar)

        images = []

        # ----------------------
        # TextActivity
        # ----------------------
        if typename == "TextActivity":
            base_embed.title = "💬 New Post"
            text, imgs = self.process_text_and_media(activity.get("text"))
            base_embed.description = text
            images.extend(imgs)

        # ----------------------
        # ListActivity
        # ----------------------
        elif typename == "ListActivity":
            media = activity.get("media", {})
            media_title = media.get("title", {}).get("english") or media.get("title", {}).get("romaji")
            media_url = media.get("siteUrl")
            progress = activity.get("progress")

            base_embed.title = f"📺 {username} {activity['status']} {progress or ''}".strip()
            base_embed.url = media_url
            base_embed.description = f"**{media_title}**"

            if media.get("coverImage", {}).get("large"):
                base_embed.set_thumbnail(url=media["coverImage"]["large"])

        # ----------------------
        # MessageActivity
        # ----------------------
        elif typename == "MessageActivity":
            recipient = activity.get("recipient", {})
            base_embed.title = f"📩 Message to {recipient.get('name')}"
            base_embed.url = recipient.get("siteUrl")
            text, imgs = self.process_text_and_media(activity.get("message"))
            base_embed.description = text
            images.extend(imgs)

        # ----------------------
        # Engagement (likes + stars + comments)
        # ----------------------
        likes = activity.get("likeCount", 0)
        comments = activity.get("replyCount", 0)

        base_embed.add_field(
            name="⭐ Engagement",
            value=f"❤️ {likes} Likes\n💬 {comments} Comments\n{self.star_rating(likes)}",
            inline=False,
        )

        if images:
            base_embed.set_image(url=images[0])
            if len(images) > 1:
                base_embed.add_field(
                    name="📷 More Media",
                    value="\n".join([f"[Image {i+2}]({url})" for i, url in enumerate(images[1:])]),
                    inline=False,
                )

        pages = [base_embed]

        # ----------------------
        # Replies grouped (5 per page)
        # ----------------------
        replies = activity.get("replies", [])
        if replies:
            chunk_size = 5
            for i in range(0, len(replies), chunk_size):
                chunk = replies[i:i+chunk_size]
                reply_embed = discord.Embed(
                    title=f"💬 Replies ({i+1}–{i+len(chunk)} of {len(replies)})",
                    color=discord.Color.blurple(),
                )
                for reply in chunk:
                    reply_user = reply["user"]
                    reply_name = reply_user["name"]
                    reply_url = reply_user["siteUrl"]
                    reply_avatar = reply_user["avatar"]["large"]
                    reply_text, imgs = self.process_text_and_media(reply.get("text"))

                    reply_embed.add_field(
                        name=f"[{reply_name}]({reply_url})",
                        value=reply_text or "—",
                        inline=False,
                    )

                    if imgs:
                        reply_embed.add_field(
                            name="📷 Media",
                            value="\n".join([f"[Image]({url})" for url in imgs]),
                            inline=False,
                        )

                pages.append(reply_embed)

        return pages

    # ---------------------------
    # Listen for AniList links
    # ---------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        match = re.search(r"anilist\.co/activity/(\d+)", message.content)
        if not match:
            return

        activity_id = int(match.group(1))
        activity = await self.fetch_activity(activity_id)
        if not activity:
            return

        pages = self.build_activity_embeds(activity)

        if len(pages) == 1:
            await message.channel.send(embed=pages[0])
        else:
            view = PageView(pages)
            await message.channel.send(embed=pages[0], view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(AniListCog(bot))
