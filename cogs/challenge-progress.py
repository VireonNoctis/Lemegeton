import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import aiohttp
from config import GUILD_ID
from database import DB_PATH, set_user_manga_progress, get_challenge_rules
from discord.ui import View, Button

# In-memory cache: {user_id: {manga_id: (progress, status)}}
user_progress_cache = {}

# -----------------------------------------
# Fetch AniList info for a Discord user
# -----------------------------------------
async def get_anilist_info(discord_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT anilist_id, anilist_username FROM users WHERE discord_id = ?", (discord_id,)
        )
        row = await cursor.fetchone()
        await cursor.close()
        if not row:
            return None
        anilist_id, anilist_username = row
        if not anilist_id and not anilist_username:
            return None
        return {"id": anilist_id, "username": anilist_username}

async def fetch_user_manga_progress(anilist_username: str, manga_id: int):
    query = """
    query ($username: String, $id: Int) {
      MediaList(userName: $username, mediaId: $id, type: MANGA) {
        progress
        status
      }
    }
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://graphql.anilist.co",
            json={"query": query, "variables": {"username": anilist_username, "id": manga_id}}
        ) as resp:
            data = await resp.json()
            media_list = data.get("data", {}).get("MediaList")
            if media_list:
                return media_list.get("progress", 0), media_list.get("status", "Not Started")
            return 0, "Not Started"

class MangaChallenges(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="challenge-progress",
        description="📚 View your progress in all global manga challenges"
    )
    async def manga_challenges(self, interaction: discord.Interaction):
        await interaction.response.defer()

        user_id = interaction.user.id
        anilist_info = await get_anilist_info(user_id)
        if not anilist_info:
            await interaction.followup.send(
                "⚠️ You have not linked your AniList account. Use `/link_anilist` first.",
                ephemeral=True
            )
            return

        anilist_username = anilist_info.get("username")

        async with aiosqlite.connect(DB_PATH) as db:
            challenges = await db.execute_fetchall(
                "SELECT challenge_id, title FROM global_challenges"
            )
            if not challenges:
                await interaction.followup.send("⚠️ No global challenges found.", ephemeral=True)
                return

            embeds = []
            options = []

            for challenge_id, title in challenges:
                manga_rows = await db.execute_fetchall(
                    "SELECT id, manga_id, title, total_chapters FROM challenge_manga WHERE challenge_id = ?",
                    (challenge_id,)
                )

                description = ""
                if manga_rows:
                    for _, manga_id, manga_title, total_chapters in manga_rows:
                        cache_key = (user_id, manga_id)
                        if cache_key in user_progress_cache:
                            chapters_read, status = user_progress_cache[cache_key]
                        else:
                            chapters_read, status = await fetch_user_manga_progress(anilist_username, manga_id)
                            user_progress_cache[cache_key] = (chapters_read, status)

                        await set_user_manga_progress(user_id, manga_id, chapters_read, status)

                        description += (
                            f"[{manga_title}](https://anilist.co/manga/{manga_id}) "
                            f"- `{chapters_read}/{total_chapters}` • Status: `{status}`\n\n"
                        )
                else:
                    description = "_No manga added to this challenge yet._"

                embed = discord.Embed(
                    title=f"📖 Challenge: {title}",
                    description=description.strip(),
                    color=discord.Color.random()
                )
                embeds.append(embed)
                options.append(discord.SelectOption(label=title, value=str(len(embeds) - 1)))

        # View with pagination + rules button
        class ChallengeView(ChallengePaginator):
            def __init__(self, embeds, options, bot: commands.Bot):
                super().__init__(embeds, options)
                self.bot = bot

                # ❌ Removed the add_item call here to prevent duplicate buttons
                # self.add_item(discord.ui.Button(...))

            @discord.ui.button(
                label="📜 View Challenge Rules",
                style=discord.ButtonStyle.primary,
                row=2
            )
            async def view_rules_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                """Send the challenge rules embed when button is pressed."""
                try:
                    rules_text = await get_challenge_rules()
                except Exception:
                    rules_text = None

                if not rules_text:
                    rules_text = "No rules have been set yet. Administrators can set them using `/challenge-rules-create`"

                embed = discord.Embed(
                    title="📜 Manga Challenge Rules",
                    description="**Follow these rules when participating in any manga challenge!**",
                    colour=discord.Colour.purple()
                )

                # Fields copied from ChallengeRules.view_rules
                embed.add_field(
                    name="📝 Progress Updates",
                    value=(
                        "- Name which trial it is (e.g. *Trial*, *Stage 1*) and resend your updated progress message when finished.\n"
                        "- Notify **@kyerstorm** when done.\n"
                        "- Use one of the following statuses:\n"
                        "`Reread` • `Completed` • `Caught Up` • `In-Progress` • `Skipped` • `Paused` • `Dropped` • `Not Started`\n\n"
                        "**Status Definitions:**\n"
                        "• **Completed** → Fully read a finished work.\n"
                        "• **Caught-Up** → Reached the latest chapter of an ongoing work.\n"
                        "• **In-Progress** → Currently reading.\n"
                        "• **Skipped** → Previously read, not rereading.\n"
                        "• **Reread** → Reread a previously completed work.\n"
                        "• **Dropped** → Read **≥25 chapters** and chose not to continue."
                    ),
                    inline=False
                )

                embed.add_field(
                    name="📌 General Rules",
                    value=(
                        "- Cannot complain or request changes if absent during challenge discussions.\n"
                        "- **70%** of titles must be **Completed / Caught Up / Skipped**.\n"
                        "- **30%** of titles can be **Dropped**.\n"
                        "- Must read **≥25 chapters** before marking as Dropped.\n"
                        "- No time limits unless stated.\n"
                        "- Challenge entries are decided via **community voting**."
                    ),
                    inline=False
                )

                embed.add_field(
                    name="👥 Community Challenge Rules",
                    value=(
                        "- No points awarded while a challenge is marked **Awaiting Approval**, but you may start it.\n"
                        "- Cannot suggest or use titles already in other challenges.\n"
                        "[**📄 Full Title List Here**](https://docs.google.com/spreadsheets/d/11WFnWLsLB5aSCcSuPTTfxBbPc105VgTXPpI5ePnxy54/edit?usp=sharing)\n"
                        "- Check challenge pins — rules may vary per challenge."
                    ),
                    inline=False
                )

                embed.add_field(
                    name="🏆 Leaderboard",
                    value=(
                        "- Use `/show \"Manga Challenge Leaderboard\"` to view rankings.\n"
                        "- Updated on the **1st of each month**.\n"
                        "- **Important:** Progress edits won't count unless you notify @kyerstorm."
                    ),
                    inline=False
                )

                embed.add_field(
                    name="📚 Manga Point System",
                    value=(
                        "- **20** Grimoires → 100% completed\n"
                        "- **10** Grimoires → 70% completed\n"
                        "- **7** Grimoires → Reread (only if ≥1/3 already read)\n"
                        "- **5** Grimoires → Per manga completed\n"
                        "- **2** Grimoires → Per skip\n"
                        "- **1** Grimoire → Per drop"
                    ),
                    inline=False
                )

                embed.add_field(
                    name="📖 CN/KN Novel Point System",
                    value=(
                        "- **20** Grimoires → 100% completed\n"
                        "- **15** Grimoires → 70% completed\n"
                        "- **20** Grimoires → Per novel completed (**>2000 chapters**)\n"
                        "- **15** Grimoires → Per novel completed (**1501–2000 chapters**)\n"
                        "- **10** Grimoires → Per novel completed (**501–1500 chapters**)\n"
                        "- **5** Grimoires → Per novel completed (**<500 chapters**)\n"
                        "- **3** Grimoires → Per skip\n"
                        "- **1** Grimoire → Per drop"
                    ),
                    inline=False
                )

                embed.set_footer(text="📌 Always double-check challenge pins for specific rules!")
                await interaction.response.send_message(embed=embed, ephemeral=True)

        # Send initial embed
        view = ChallengeView(embeds, options, self.bot)
        await interaction.followup.send(embed=embeds[0], view=view)


class ChallengePaginator(discord.ui.View):
    def __init__(self, embeds, options):
        super().__init__(timeout=180)
        self.embeds = embeds
        self.current_page = 0

        self.select = discord.ui.Select(
            placeholder="Jump to a challenge...",
            options=options,
            row=0
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def update_message(self, interaction: discord.Interaction):
        embed = self.embeds[self.current_page]
        embed.set_footer(text=f"Page {self.current_page + 1} of {len(self.embeds)}")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⬅️ Previous", style=discord.ButtonStyle.secondary, row=1)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = (self.current_page - 1) % len(self.embeds)
        await self.update_message(interaction)

    @discord.ui.button(label="➡️ Next", style=discord.ButtonStyle.secondary, row=1)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = (self.current_page + 1) % len(self.embeds)
        await self.update_message(interaction)

    async def select_callback(self, interaction: discord.Interaction):
        self.current_page = int(self.select.values[0])
        await self.update_message(interaction)


async def setup(bot: commands.Bot):
    await bot.add_cog(MangaChallenges(bot))
