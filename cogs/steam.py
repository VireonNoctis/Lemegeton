# cogs/steam.py
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import aiosqlite
from config import STEAM_API_KEY, DB_PATH, GUILD_ID
from datetime import datetime

class Steam(commands.Cog):
    """Steam commands: register, view profile, search games."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    steam_group = app_commands.Group(name="steam", description="Steam commands")
    steam_group = app_commands.guilds(discord.Object(id=GUILD_ID))(steam_group)

    # ------------------- REGISTER -------------------
    @steam_group.command(
        name="register",
        description="Register your Steam account"
    )
    @app_commands.describe(vanity_name="Your Steam profile's vanity URL name")
    async def register(self, interaction: discord.Interaction, vanity_name: str):
        await interaction.response.defer(ephemeral=True)
        discord_id = interaction.user.id

        # Resolve vanity name to SteamID64
        url = f"https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/?key={STEAM_API_KEY}&vanityurl={vanity_name}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                if data.get("response", {}).get("success") != 1:
                    return await interaction.followup.send(
                        f"❌ Could not find Steam account `{vanity_name}`.\n"
                        "Make sure you are using your **vanity URL**, which is the part of your profile URL after `https://steamcommunity.com/id/`.\n"
                        "For example, if your URL is `https://steamcommunity.com/id/kyerstorm/`, your vanity name is `kyerstorm`.",
                        ephemeral=True
                    )
                steam_id = data["response"]["steamid"]

        # Store in DB
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                INSERT INTO steam_users (discord_id, steam_id, vanity_name)
                VALUES (?, ?, ?)
                ON CONFLICT(discord_id) DO UPDATE SET
                    steam_id=excluded.steam_id,
                    vanity_name=excluded.vanity_name
                """,
                (discord_id, steam_id, vanity_name)
            )
            await db.commit()

        await interaction.followup.send(
            f"✅ Registered Steam account `{vanity_name}` successfully!", ephemeral=True
        )

    # ------------------- PROFILE -------------------
    @steam_group.command(
        name="profile",
        description="View your Steam profile (registered or by Steam ID/vanity name)"
    )
    @app_commands.describe(user="SteamID64 or custom profile URL (optional if registered)")
    async def steam_profile(self, interaction: discord.Interaction, user: str = None):
        await interaction.response.defer()

        steam_id = None
        # Use registered Steam ID if user not provided
        if not user:
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute(
                    "SELECT steam_id, vanity_name FROM steam_users WHERE discord_id = ?",
                    (interaction.user.id,)
                )
                row = await cursor.fetchone()
                await cursor.close()
                if not row:
                    return await interaction.followup.send(
                        "❌ You have not registered a Steam account.\n"
                        "Use `/steam register <vanity_name>` first.\n"
                        "Your vanity name is the part of your Steam profile URL after "
                        "`https://steamcommunity.com/id/`. For example, if your URL is "
                        "`https://steamcommunity.com/id/kyerstorm/`, your vanity name is `kyerstorm`.",
                        ephemeral=True
                    )
                steam_id, user = row

        async with aiohttp.ClientSession() as session:
            # Resolve vanity URL if needed
            if user and not user.isdigit():
                resolve_url = f"https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/?key={STEAM_API_KEY}&vanityurl={user}"
                async with session.get(resolve_url) as resp:
                    data = await resp.json()
                    if data.get("response", {}).get("success") != 1:
                        return await interaction.followup.send(
                            f"❌ Could not find Steam user `{user}`.\n"
                            "Double-check your SteamID64 or vanity name.",
                            ephemeral=True
                        )
                    steam_id = data["response"]["steamid"]

            # Get player summary
            profile_url = f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?key={STEAM_API_KEY}&steamids={steam_id}"
            async with session.get(profile_url) as resp:
                data = await resp.json()
                players = data.get("response", {}).get("players", [])
                if not players:
                    return await interaction.followup.send("❌ No profile data found.", ephemeral=True)
                player = players[0]

            # Steam level
            level_url = f"https://api.steampowered.com/IPlayerService/GetSteamLevel/v1/?key={STEAM_API_KEY}&steamid={steam_id}"
            async with session.get(level_url) as resp:
                level_data = await resp.json()
                level = level_data.get("response", {}).get("player_level", 0)

            # Recently played games
            recent_url = f"https://api.steampowered.com/IPlayerService/GetRecentlyPlayedGames/v1/?key={STEAM_API_KEY}&steamid={steam_id}&count=5"
            async with session.get(recent_url) as resp:
                recent_data = await resp.json()
                recent_games = recent_data.get("response", {}).get("games", [])

            # Owned games (top 5 by playtime)
            owned_url = f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?key={STEAM_API_KEY}&steamid={steam_id}&include_appinfo=1&include_played_free_games=1"
            async with session.get(owned_url) as resp:
                owned_data = await resp.json()
                total_games = owned_data.get("response", {}).get("game_count", 0)
                owned_games = owned_data.get("response", {}).get("games", [])

                # Sort by playtime_forever descending
                top_games = sorted(owned_games, key=lambda g: g.get("playtime_forever", 0), reverse=True)[:5]

            # Friends count
            friends_url = f"https://api.steampowered.com/ISteamUser/GetFriendList/v1/?key={STEAM_API_KEY}&steamid={steam_id}&relationship=all"
            async with session.get(friends_url) as resp:
                friends_data = await resp.json()
                friends_count = len(friends_data.get("friendslist", {}).get("friends", []))

        # Embed
        embed = discord.Embed(
            title=player.get("personaname", "Unknown"),
            url=player.get("profileurl"),
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=player.get("avatarfull"))
        embed.add_field(
            name="Profile Status",
            value={0:"Offline",1:"Online",2:"Busy",3:"Away",4:"Snooze",5:"Looking to trade",6:"Looking to play"}.get(player.get("personastate",0),"Unknown"),
            inline=True
        )
        embed.add_field(name="Account Created", value=f"<t:{player.get('timecreated',0)}:D>", inline=True)
        embed.add_field(name="Last Online", value=f"<t:{player.get('lastlogoff',0)}:R>", inline=True)
        embed.add_field(
            name="Visibility",
            value={1:"Private",2:"Friends Only",3:"Public",4:"Private"}.get(player.get("communityvisibilitystate",1),"Unknown"),
            inline=True
        )
        embed.add_field(name="Country", value=player.get("loccountrycode","N/A"), inline=True)
        embed.add_field(name="Steam Level", value=str(level), inline=True)
        embed.add_field(name="Total Games Owned", value=str(total_games), inline=True)
        embed.add_field(name="Friends Count", value=str(friends_count), inline=True)

        # Recently played
        if recent_games:
            recent_list = "\n".join(f"[{g['name']}](https://store.steampowered.com/app/{g['appid']})" for g in recent_games)
            embed.add_field(name="🎮 Recently Played (Top 5)", value=recent_list, inline=False)

        # Most played
        if top_games:
            top_list = "\n".join(
                f"[{g['name']}](https://store.steampowered.com/app/{g['appid']}) - {g.get('playtime_forever', 0)//60}h played"
                for g in top_games
            )
            embed.add_field(name="🏆 Most Played Games (Top 5)", value=top_list, inline=False)

        await interaction.followup.send(embed=embed)

    # ------------------- GAME -------------------
    @steam_group.command(
        name="game",
        description="Get info about a Steam game by name"
    )
    @app_commands.describe(game_name="Name of the game to search on Steam")
    async def game(self, interaction: discord.Interaction, game_name: str):
        await interaction.response.defer()
        search_url = f"https://store.steampowered.com/api/storesearch/?term={game_name}&l=en&cc=us"

        async with aiohttp.ClientSession() as session:
            async with session.get(search_url) as resp:
                if resp.status != 200:
                    return await interaction.followup.send(f"❌ Failed to search for '{game_name}'")
                search_data = await resp.json()

        items = search_data.get("items", [])
        if not items:
            return await interaction.followup.send(f"❌ No results found for '{game_name}'")

        top_items = items[:3]
        view = discord.ui.View(timeout=60)

        async def make_button(item):
            button = discord.ui.Button(label=item["name"][:80], style=discord.ButtonStyle.primary)

            async def button_callback(button_interaction: discord.Interaction):
                await button_interaction.response.defer()
                appid = item["id"]

                url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=us&l=en"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        data = await resp.json()
                app_data = data.get(str(appid), {}).get("data")
                if not app_data:
                    return await button_interaction.followup.send(f"❌ No data found for '{item['name']}'")

                name = app_data.get("name", "Unknown")
                description = app_data.get("short_description", "No description available.")
                description = (description[:300] + "…") if len(description) > 300 else description
                header_image = app_data.get("header_image")
                genres = [g["description"] for g in app_data.get("genres", [])]
                main_genre = genres[0] if genres else "Other"
                platforms = [k for k,v in app_data.get("platforms", {}).items() if v]
                price_info = app_data.get("price_overview")
                metacritic = app_data.get("metacritic", {}).get("score")
                tags = app_data.get("categories", [])
                is_free = app_data.get("is_free", False)
                release_date = app_data.get("release_date", {}).get("date", "Unknown")

                genre_colors = {"Action":0xE74C3C,"Adventure":0x3498DB,"RPG":0x9B59B6,"Strategy":0xF1C40F,"Simulation":0x1ABC9C,"Sports":0xE67E22,"Other":0x95A5A6}
                color = genre_colors.get(main_genre,0x95A5A6)
                if is_free:
                    price_str = "Free"
                elif price_info:
                    final = price_info.get("final_formatted","Unknown")
                    initial = price_info.get("initial_formatted","")
                    discount = price_info.get("discount_percent",0)
                    price_str = f"~~{initial}~~ → **{final}** ({discount}% off)" if discount>0 else final
                else:
                    price_str = "N/A"

                badge_list = []
                if metacritic: badge_list.append(f"⭐ Metacritic: {metacritic}")
                if tags:
                    top_tags = [t["description"] for t in tags[:5]]
                    badge_list.append(" | ".join(top_tags))
                badge_text = " | ".join(badge_list) if badge_list else "No badges"

                embed = discord.Embed(title=name, description=description, color=color)
                embed.set_thumbnail(url=header_image)
                embed.add_field(name="Price", value=price_str, inline=True)
                embed.add_field(name="Release Date", value=release_date, inline=True)
                embed.add_field(name="Platforms", value=", ".join(platforms) if platforms else "Unknown", inline=True)
                embed.add_field(name="Tags & Ratings", value=badge_text, inline=False)

                result_view = discord.ui.View()
                result_view.add_item(discord.ui.Button(label="View on Steam", url=f"https://store.steampowered.com/app/{appid}", style=discord.ButtonStyle.link))
                await button_interaction.followup.send(embed=embed, view=result_view)

            button.callback = button_callback
            view.add_item(button)

        for item in top_items:
            await make_button(item)

        await interaction.followup.send(content=f"Select a game from the top {len(top_items)} results:", view=view)

# ------------------- SETUP -------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(Steam(bot))
