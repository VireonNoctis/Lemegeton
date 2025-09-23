"""
Example Code Changes for Multi-Guild Support
===========================================

This file shows the specific code changes needed in your cogs to support
multiple guilds after running the migration script.

Key Changes:
1. Always include guild_id in database queries
2. Pass interaction.guild.id to database functions
3. Update database.py helper functions
"""

# =============================================================================
# 1. DATABASE.PY UPDATES
# =============================================================================

"""
Update your database.py file with these guild-aware functions:
"""

async def get_user_data(discord_id: int, guild_id: int):
    """Get user data for a specific guild"""
    return await execute_db_operation(
        "get user data",
        "SELECT * FROM users WHERE discord_id = ? AND guild_id = ?",
        (discord_id, guild_id)
    )

async def register_user(discord_id: int, guild_id: int, username: str, anilist_username: str = None, anilist_id: int = None):
    """Register a user in a specific guild"""
    return await execute_db_operation(
        "register user",
        """INSERT OR REPLACE INTO users 
           (discord_id, guild_id, username, anilist_username, anilist_id, updated_at) 
           VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
        (discord_id, guild_id, username, anilist_username, anilist_id)
    )

async def get_user_progress(discord_id: int, guild_id: int):
    """Get user challenge progress for a specific guild"""
    return await execute_db_operation(
        "get user progress",
        "SELECT * FROM user_progress WHERE discord_id = ? AND guild_id = ?",
        (discord_id, guild_id)
    )

async def get_guild_leaderboard(guild_id: int, limit: int = 10):
    """Get leaderboard for a specific guild"""
    return await execute_db_operation(
        "get guild leaderboard",
        """SELECT u.username, up.total_points, up.completed_challenges
           FROM user_progress up
           JOIN users u ON up.discord_id = u.discord_id AND up.guild_id = u.guild_id
           WHERE up.guild_id = ?
           ORDER BY up.total_points DESC
           LIMIT ?""",
        (guild_id, limit)
    )

# =============================================================================
# 2. COG UPDATES - PROFILE.PY EXAMPLE
# =============================================================================

"""
Example of updating cogs/profile.py:
"""

class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="profile", description="View your profile")
    async def profile(self, interaction: discord.Interaction, user: discord.Member = None):
        await interaction.response.defer()
        
        target_user = user or interaction.user
        guild_id = interaction.guild.id  # ALWAYS GET GUILD ID
        
        # OLD: user_data = await get_user_data(target_user.id)
        # NEW: Include guild_id
        user_data = await get_user_data(target_user.id, guild_id)
        
        if not user_data:
            embed = discord.Embed(
                title="❌ User Not Registered",
                description=f"{target_user.mention} is not registered in this server.",
                color=0xff0000
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Get guild-specific progress
        progress_data = await get_user_progress(target_user.id, guild_id)
        
        # Create profile embed (rest of code remains similar)
        embed = discord.Embed(
            title=f"📊 {user_data['username']}'s Profile",
            color=0x00ff00
        )
        # ... rest of profile display code

    @app_commands.command(name="register", description="Register your AniList account")
    async def register(self, interaction: discord.Interaction, anilist_username: str):
        await interaction.response.defer()
        
        guild_id = interaction.guild.id  # ALWAYS GET GUILD ID
        
        # OLD: await register_user(interaction.user.id, interaction.user.display_name, anilist_username)
        # NEW: Include guild_id
        await register_user(
            interaction.user.id, 
            guild_id, 
            interaction.user.display_name, 
            anilist_username
        )
        
        embed = discord.Embed(
            title="✅ Registration Successful",
            description=f"Registered {interaction.user.mention} in **{interaction.guild.name}**",
            color=0x00ff00
        )
        await interaction.followup.send(embed=embed)

# =============================================================================
# 3. COG UPDATES - LEADERBOARD.PY EXAMPLE
# =============================================================================

"""
Example of updating cogs/leaderboard.py:
"""

class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="leaderboard", description="View the server leaderboard")
    async def leaderboard(self, interaction: discord.Interaction, limit: int = 10):
        await interaction.response.defer()
        
        guild_id = interaction.guild.id  # ALWAYS GET GUILD ID
        
        # OLD: leaderboard_data = await get_leaderboard(limit)
        # NEW: Get guild-specific leaderboard
        leaderboard_data = await get_guild_leaderboard(guild_id, limit)
        
        if not leaderboard_data:
            embed = discord.Embed(
                title="📊 Server Leaderboard",
                description="No users found in this server.",
                color=0xff9900
            )
            await interaction.followup.send(embed=embed)
            return
        
        embed = discord.Embed(
            title=f"📊 {interaction.guild.name} Leaderboard",
            color=0x00ff00
        )
        
        description = ""
        for i, (username, points, challenges) in enumerate(leaderboard_data, 1):
            description += f"**{i}.** {username} - {points} points ({challenges} challenges)\n"
        
        embed.description = description
        await interaction.followup.send(embed=embed)

# =============================================================================
# 4. COG UPDATES - CHALLENGE_PROGRESS.PY EXAMPLE
# =============================================================================

"""
Example of updating challenge-related cogs:
"""

class ChallengeProgress(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="progress", description="View your challenge progress")
    async def progress(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        guild_id = interaction.guild.id  # ALWAYS GET GUILD ID
        user_id = interaction.user.id
        
        # Check if user is registered in THIS guild
        user_data = await get_user_data(user_id, guild_id)
        if not user_data:
            embed = discord.Embed(
                title="❌ Not Registered",
                description="You need to register in this server first! Use `/register`",
                color=0xff0000
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Get guild-specific progress
        progress = await get_user_progress(user_id, guild_id)
        
        embed = discord.Embed(
            title=f"📈 {interaction.user.display_name}'s Progress in {interaction.guild.name}",
            color=0x00ff00
        )
        
        if progress:
            embed.add_field(
                name="Total Points", 
                value=progress.get('total_points', 0), 
                inline=True
            )
            embed.add_field(
                name="Completed Challenges", 
                value=progress.get('completed_challenges', 0), 
                inline=True
            )
        else:
            embed.description = "No progress recorded yet. Start completing challenges!"
        
        await interaction.followup.send(embed=embed)

# =============================================================================
# 5. IMPORTANT PATTERNS TO FOLLOW
# =============================================================================

"""
Key Patterns for All Commands:

1. ALWAYS get guild_id early:
   guild_id = interaction.guild.id

2. ALWAYS pass guild_id to database functions:
   await get_user_data(user_id, guild_id)

3. ALWAYS check guild-specific registration:
   user_data = await get_user_data(user_id, guild_id)
   if not user_data:
       # Handle unregistered user

4. UPDATE error messages to mention "this server":
   "You are not registered in this server"
   "No data found for this server"

5. UPDATE embed titles to include server context:
   f"{interaction.guild.name} Leaderboard"
   f"Your progress in {interaction.guild.name}"

6. HANDLE bot permissions gracefully:
   if not interaction.guild:
       await interaction.response.send_message(
           "This command can only be used in servers!", 
           ephemeral=True
       )
       return
"""

# =============================================================================
# 6. MIGRATION CHECKLIST
# =============================================================================

"""
Before deploying your multi-guild bot:

□ Run migrate_to_public.py script
□ Update database.py with guild-aware functions
□ Update ALL cogs to include guild_id in queries
□ Test with multiple test servers
□ Verify data isolation between servers
□ Add proper error handling for missing guilds
□ Update help text/descriptions to mention "server"
□ Test bot leaving/joining servers
□ Set up monitoring and logging
□ Plan backup strategy for production

Database Functions to Update:
□ get_user_data(discord_id, guild_id)
□ register_user(discord_id, guild_id, ...)
□ get_user_progress(discord_id, guild_id)
□ update_user_progress(discord_id, guild_id, ...)
□ get_achievements(discord_id, guild_id)
□ get_leaderboard(guild_id, limit)
□ All challenge-related functions
□ All stats-related functions

Cogs to Update:
□ profile.py - Registration and profiles
□ leaderboard.py - Server leaderboards
□ challenge_*.py - All challenge cogs
□ stats.py - Statistics per server
□ achievements.py - Server achievements
□ Any other cogs using database
"""