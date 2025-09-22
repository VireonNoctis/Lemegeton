import discord
from discord.ext import commands
from discord.ui import View, Button
import yt_dlp
import datetime
import aiohttp
import os

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")  # put your key in env vars

class EmbedCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def fetch_youtube_api(self, video_id: str):
        """Fetch video details from YouTube Data API if available."""
        api_url = (
            "https://www.googleapis.com/youtube/v3/videos"
            f"?id={video_id}&key={YOUTUBE_API_KEY}&part=snippet"
        )
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if "items" in data and data["items"]:
                        snippet = data["items"][0]["snippet"]
                        return {
                            "title": snippet["title"],
                            "channel": snippet["channelTitle"],
                            "channel_id": snippet["channelId"],
                            "pfp": snippet["thumbnails"]["default"]["url"],
                            "thumbnail": snippet["thumbnails"]["high"]["url"],
                            "date": snippet["publishedAt"],
                        }
        return None

    async def build_youtube_embed(self, url: str):
        """Builds a styled YouTube embed."""
        # Extract video ID
        if "watch?v=" in url:
            video_id = url.split("watch?v=")[-1].split("&")[0]
        elif "youtu.be/" in url:
            video_id = url.split("youtu.be/")[-1].split("?")[0]
        else:
            video_id = None

        video_data = None
        if YOUTUBE_API_KEY and video_id:
            video_data = await self.fetch_youtube_api(video_id)

        if not video_data:  # fallback to yt_dlp
            ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            video_data = {
                "title": info.get("title"),
                "channel": info.get("uploader"),
                "channel_id": info.get("channel_id"),
                "pfp": info.get("thumbnail"),
                "thumbnail": info.get("thumbnail"),
                "date": info.get("upload_date"),
            }

        # Format date
        if video_data.get("date"):
            try:
                if "T" in video_data["date"]:  # API returns ISO
                    dt = datetime.datetime.fromisoformat(video_data["date"].replace("Z", "+00:00"))
                else:  # yt_dlp returns YYYYMMDD
                    dt = datetime.datetime.strptime(video_data["date"], "%Y%m%d")
                formatted_date = dt.strftime("%b %d, %Y")
            except Exception:
                formatted_date = "Unknown Date"
        else:
            formatted_date = "Unknown Date"

        # Build embed
        embed = discord.Embed(
            title=video_data["title"],
            url=url,
            color=discord.Color.red()
        )

        embed.set_author(
            name=video_data["channel"],
            url=f"https://www.youtube.com/channel/{video_data['channel_id']}",
            icon_url=video_data["pfp"] or discord.Embed.Empty
        )

        embed.set_image(url=video_data["thumbnail"])
        embed.add_field(name="", value="💬 ❤️ 👁️", inline=False)
        embed.set_footer(
            text=f"YouTube • {formatted_date}",
            icon_url="https://cdn-icons-png.flaticon.com/512/1384/1384060.png"
        )

        # Add View button
        view = View(timeout=None)
        view.add_item(Button(label="View", style=discord.ButtonStyle.link, url=url))

        return embed, view

    @commands.Cog.listener()
    async def on_message(self, message):
        """Auto-detect YouTube links and replace with styled embed."""
        if message.author.bot:
            return

        if "youtube.com/watch" in message.content or "youtu.be/" in message.content:
            url = message.content.strip()
            try:
                embed, view = await self.build_youtube_embed(url)
                await message.channel.send(embed=embed, view=view)
                await message.delete()
            except Exception as e:
                await message.channel.send(f"❌ Failed to embed YouTube link: {e}")

async def setup(bot):
    await bot.add_cog(EmbedCog(bot))
