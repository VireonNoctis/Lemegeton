import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import aiosqlite
import asyncio
import math
from typing import Optional
from pathlib import Path

try:
    # Import helpers robustly: some deployment environments don't include the
    # project root on sys.path which causes `helpers` to be unresolvable. Try an
    # absolute import first, then add the repository root to sys.path and retry.
    try:
        from helpers.steam_helper import (
            logger, safe_json, STEAM_API_KEY, DB_PATH,
            RecommendationView, create_recommendation_embed
        )
    except Exception:
        import sys
        repo_root = Path(__file__).resolve().parents[2]
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))

        # Retry import; capture missing-name errors and provide safe fallbacks
        from helpers.steam_helper import (
            logger, safe_json, STEAM_API_KEY, DB_PATH,
            RecommendationView, create_recommendation_embed
        )
except ModuleNotFoundError:
    # Some deployment environments don't put the project root on sys.path.
    # Try to add the repo root (two levels up from this file: ../..) to sys.path
    # and re-import. This makes the cog robust when run as a module from
    # different working directories.
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    # Retry import; let any remaining ImportError bubble up to surface the
    # real problem (missing package, typo, etc.).
    from helpers.steam_helper import (
        logger, safe_json, STEAM_API_KEY, DB_PATH,
        RecommendationView, create_recommendation_embed
    )


class SteamRecommendation(commands.Cog):
    """Steam game recommendation system with personalized suggestions"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="steam-recommendation", description="Get personalized game recommendations based on your Steam library")
    async def steam_recommendation(self, interaction: discord.Interaction):
        logger.info(f"/steam-recommendation by {interaction.user}")
        await interaction.response.defer(ephemeral=True)

        # Get user's Steam ID
        steamid = None
        async with aiosqlite.connect(DB_PATH) as db:
            # Prefer guild-scoped lookup when in a guild
            guild_id = getattr(interaction.guild, 'id', None)
            row = None
            if guild_id is not None:
                try:
                    cur = await db.execute("SELECT steam_id FROM steam_users WHERE discord_id = ? AND guild_id = ?", (interaction.user.id, guild_id))
                    row = await cur.fetchone()
                    await cur.close()
                except Exception:
                    row = None

            if not row:
                cur = await db.execute("SELECT steam_id FROM steam_users WHERE discord_id = ?", (interaction.user.id,))
                row = await cur.fetchone()
                await cur.close()
            if not row:
                return await interaction.followup.send("❌ You have not registered a Steam account. Use `/login` to register your Steam account.", ephemeral=True)
            steamid = row[0]

        async with aiohttp.ClientSession() as session:
            # Get user's owned games with detailed info
            owned = await safe_json(session, "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/",
                                    params={"key": STEAM_API_KEY, "steamid": steamid, "include_appinfo": 1, "include_played_free_games": 1})
            owned_games = owned.get("response", {}).get("games", []) if owned else []
            
            if not owned_games:
                return await interaction.followup.send("❌ No games found in your library or profile is private.", ephemeral=True)

            if len(owned_games) < 3:
                return await interaction.followup.send("❌ You need at least 3 games in your library to get recommendations.", ephemeral=True)

            # Analyze user preferences
            await interaction.followup.send("🔄 Analyzing your game library and preferences...", ephemeral=True)
            
            recommendations = await self._generate_recommendations(session, owned_games, steamid)
            
            if not recommendations:
                return await interaction.edit_original_response(content="❌ Could not generate recommendations. Try again later.")

            # Create interactive recommendation view
            view = RecommendationView(recommendations, interaction.user)
            embed = await self._create_recommendation_embed(recommendations[0], 1, len(recommendations))
            
            await interaction.edit_original_response(
                content="🎮 **Personalized Game Recommendations**\nBased on your library analysis:",
                embed=embed,
                view=view
            )

    async def _generate_recommendations(self, session, owned_games, steamid):
        """Generate personalized recommendations based on user's library"""
        
        # Step 1: Analyze user's gaming preferences
        total_playtime = sum(g.get("playtime_forever", 0) for g in owned_games)
        if total_playtime == 0:
            # If no playtime data, use all games equally
            analyzed_games = owned_games[:20]  # Analyze top 20 by app ID
        else:
            # Focus on games with significant playtime (at least 1 hour or top 50% by playtime)
            min_playtime = max(60, total_playtime * 0.02)  # 2% of total playtime or 1 hour minimum
            analyzed_games = [g for g in owned_games if g.get("playtime_forever", 0) >= min_playtime]
            if len(analyzed_games) < 3:
                analyzed_games = sorted(owned_games, key=lambda x: x.get("playtime_forever", 0), reverse=True)[:10]

        # Step 2: Collect detailed game information for analysis
        genre_scores = {}
        tag_scores = {}
        developer_scores = {}
        publisher_scores = {}
        
        analyzed_count = 0
        owned_app_ids = {str(g["appid"]) for g in owned_games}

        for game in analyzed_games[:15]:  # Limit API calls
            app_id = game["appid"]
            playtime_weight = max(1, math.log(game.get("playtime_forever", 60) + 1))  # Logarithmic weighting
            
            # Get detailed app info
            app_data = await safe_json(session, f"https://store.steampowered.com/api/appdetails", 
                                     params={"appids": app_id, "cc": "us", "l": "en"})
            
            if not app_data or str(app_id) not in app_data:
                continue
                
            details = app_data[str(app_id)].get("data", {})
            if not details:
                continue
                
            analyzed_count += 1
            
            # Analyze genres
            for genre in details.get("genres", []):
                genre_name = genre.get("description", "")
                if genre_name:
                    genre_scores[genre_name] = genre_scores.get(genre_name, 0) + playtime_weight
            
            # Analyze categories/tags
            for category in details.get("categories", []):
                cat_name = category.get("description", "")
                if cat_name:
                    tag_scores[cat_name] = tag_scores.get(cat_name, 0) + playtime_weight * 0.5
            
            # Analyze developers
            for dev in details.get("developers", []):
                developer_scores[dev] = developer_scores.get(dev, 0) + playtime_weight
            
            # Analyze publishers  
            for pub in details.get("publishers", []):
                publisher_scores[pub] = publisher_scores.get(pub, 0) + playtime_weight * 0.7
            
            await asyncio.sleep(0.1)  # Rate limiting

        if analyzed_count == 0:
            return []

        # Step 3: Find recommendation candidates
        # Use Steam's recommendation API and store search
        candidates = []
        
        # Get top genres for searching
        top_genres = sorted(genre_scores.items(), key=lambda x: x[1], reverse=True)[:3]
        
        for genre_name, _ in top_genres:
            # Search Steam store for games in preferred genres
            search_url = "https://store.steampowered.com/api/storesearch/"
            search_data = await safe_json(session, search_url, params={
                "term": genre_name,
                "l": "en",
                "cc": "us",
                "category1": "998"  # Games category
            })
            
            if search_data and "items" in search_data:
                for item in search_data["items"][:20]:  # Top 20 per genre
                    if str(item["id"]) not in owned_app_ids:  # Don't recommend owned games
                        candidates.append(item["id"])
            
            await asyncio.sleep(0.1)
        
        # Step 4: Score and rank candidates
        scored_recommendations = []
        
        for app_id in list(set(candidates))[:50]:  # Limit to 50 unique candidates
            # Get detailed info for scoring
            app_data = await safe_json(session, f"https://store.steampowered.com/api/appdetails",
                                     params={"appids": app_id, "cc": "us", "l": "en"})
            
            if not app_data or str(app_id) not in app_data:
                continue
                
            details = app_data[str(app_id)].get("data", {})
            if not details or details.get("type") != "game":
                continue
            
            # Calculate recommendation score
            score = 0
            match_reasons = []
            
            # Genre matching
            for genre in details.get("genres", []):
                genre_name = genre.get("description", "")
                if genre_name in genre_scores:
                    genre_weight = genre_scores[genre_name] / max(genre_scores.values())
                    score += genre_weight * 10
                    match_reasons.append(f"Genre: {genre_name}")
            
            # Tag/category matching
            for category in details.get("categories", []):
                cat_name = category.get("description", "")
                if cat_name in tag_scores:
                    tag_weight = tag_scores[cat_name] / max(tag_scores.values()) if tag_scores else 0
                    score += tag_weight * 5
                    match_reasons.append(f"Feature: {cat_name}")
            
            # Developer matching
            for dev in details.get("developers", []):
                if dev in developer_scores:
                    dev_weight = developer_scores[dev] / max(developer_scores.values())
                    score += dev_weight * 8
                    match_reasons.append(f"Developer: {dev}")
            
            # Publisher matching
            for pub in details.get("publishers", []):
                if pub in publisher_scores:
                    pub_weight = publisher_scores[pub] / max(publisher_scores.values())
                    score += pub_weight * 6
                    match_reasons.append(f"Publisher: {pub}")
            
            # Boost score for highly rated games
            metacritic_score = details.get("metacritic", {}).get("score", 0)
            if metacritic_score > 75:
                score += 3
                match_reasons.append(f"Highly rated ({metacritic_score}/100)")
            
            # Add popularity boost for games with many reviews
            # (This would require additional API calls, so we'll skip for now)
            
            if score > 0:
                scored_recommendations.append({
                    "app_id": app_id,
                    "score": score,
                    "details": details,
                    "match_reasons": match_reasons[:3]  # Top 3 reasons
                })
            
            await asyncio.sleep(0.08)
        
        # Sort by score and return top recommendations
        scored_recommendations.sort(key=lambda x: x["score"], reverse=True)
        return scored_recommendations[:12]  # Return top 12 recommendations

    async def _create_recommendation_embed(self, recommendation, current_index, total_count):
        """Create an embed for a single recommendation"""
        details = recommendation["details"]
        
        name = details.get("name", "Unknown Game")
        description = details.get("short_description", "No description available.")
        if len(description) > 300:
            description = description[:297] + "..."
        
        header_image = details.get("header_image", "")
        app_id = recommendation["app_id"]
        
        # Get genre and pricing info
        genres = [g["description"] for g in details.get("genres", [])]
        price_info = details.get("price_overview", {})
        is_free = details.get("is_free", False)
        release_date = details.get("release_date", {}).get("date", "Unknown")
        
        # Format price
        if is_free:
            price_str = "Free to Play"
            color = discord.Color.green()
        elif price_info:
            price_str = price_info.get("final_formatted", "Price unknown")
            discount = price_info.get("discount_percent", 0)
            if discount > 0:
                original = price_info.get("initial_formatted", "")
                price_str = f"~~{original}~~ → **{price_str}** ({discount}% off)"
                color = discord.Color.gold()
            else:
                color = discord.Color.blue()
        else:
            price_str = "Price not available"
            color = discord.Color.dark_gray()
        
        embed = discord.Embed(
            title=name,
            description=description,
            color=color,
            url=f"https://store.steampowered.com/app/{app_id}"
        )
        
        if header_image:
            embed.set_image(url=header_image)
        
        embed.add_field(name="💰 Price", value=price_str, inline=True)
        embed.add_field(name="📅 Release Date", value=release_date, inline=True)
        embed.add_field(name="🎮 Genres", value=", ".join(genres[:3]) if genres else "Unknown", inline=True)
        
        # Add match reasons if available
        if "match_reasons" in recommendation and recommendation["match_reasons"]:
            reasons = "\n".join(f"• {reason}" for reason in recommendation["match_reasons"][:3])
            embed.add_field(name="🎯 Why recommended", value=reasons, inline=False)
        
        embed.set_footer(text=f"Recommendation {current_index}/{total_count} • Score: {recommendation['score']:.1f}")
        
        return embed


async def setup(bot: commands.Bot):
    """Set up the SteamRecommendation cog."""
    try:
        await bot.add_cog(SteamRecommendation(bot))
        logger.info("SteamRecommendation cog successfully loaded")
    except Exception as e:
        logger.error(f"Failed to load SteamRecommendation cog: {e}", exc_info=True)
        raise