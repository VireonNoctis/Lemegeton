"""
AniList Analytics Dashboard Implementation
Provides comprehensive personal analytics and insights for users

Features:
- Yearly Wrap (Spotify-style)  
- Genre Evolution Analysis
- Completion Pattern Recognition
- Social Comparisons
- Achievement System
- Progress Predictions
"""

import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import json
import calendar
from enum import Enum
import math
import statistics
from collections import defaultdict, Counter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AnalyticsPeriod(Enum):
    """Time periods for analytics"""
    MONTH = "month"
    QUARTER = "quarter" 
    YEAR = "year"
    ALL_TIME = "all_time"

class AnalyticsMetric(Enum):
    """Analytics metric types"""
    READING_VELOCITY = "reading_velocity"
    GENRE_DIVERSITY = "genre_diversity"  
    COMPLETION_RATE = "completion_rate"
    BINGE_PATTERNS = "binge_patterns"
    DISCOVERY_RATE = "discovery_rate"

class AnalyticsDashboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = None
        logger.info("Analytics Dashboard cog initialized")
        
    async def cog_load(self):
        """Initialize aiohttp session when cog loads"""
        self.session = aiohttp.ClientSession()
        logger.info("Analytics Dashboard cog loaded successfully")
        
    async def cog_unload(self):
        """Clean up aiohttp session when cog unloads"""
        if self.session:
            await self.session.close()
        logger.info("Analytics Dashboard cog unloaded")

    # ===== CORE ANALYTICS METHODS =====
    
    async def fetch_user_analytics_data(self, anilist_username: str, period: AnalyticsPeriod = AnalyticsPeriod.YEAR) -> Dict:
        """Fetch comprehensive analytics data for a user"""
        try:
            # Calculate date range based on period
            end_date = datetime.now()
            if period == AnalyticsPeriod.MONTH:
                start_date = end_date - timedelta(days=30)
            elif period == AnalyticsPeriod.QUARTER:
                start_date = end_date - timedelta(days=90)
            elif period == AnalyticsPeriod.YEAR:
                start_date = end_date - timedelta(days=365)
            else:  # ALL_TIME
                start_date = datetime(2000, 1, 1)
            
            # GraphQL query for comprehensive user data
            query = '''
            query ($username: String) {
                User(name: $username) {
                    id
                    name
                    statistics {
                        anime {
                            count
                            meanScore
                            standardDeviation
                            minutesWatched
                            episodesWatched
                            statuses {
                                status
                                count
                                meanScore
                                minutesWatched
                            }
                            scores {
                                score
                                count
                                meanScore
                                minutesWatched
                            }
                            lengths {
                                length
                                count
                                meanScore
                                minutesWatched
                            }
                            releaseYears {
                                releaseYear
                                count
                                meanScore
                                minutesWatched
                            }
                            startYears {
                                startYear
                                count
                                meanScore
                                minutesWatched
                            }
                            genres {
                                genre
                                count
                                meanScore
                                minutesWatched
                            }
                            tags {
                                tag {
                                    name
                                }
                                count
                                meanScore
                                minutesWatched
                            }
                            countries {
                                country
                                count
                                meanScore
                                minutesWatched
                            }
                            voiceActors {
                                voiceActor {
                                    name {
                                        full
                                    }
                                }
                                count
                                meanScore
                                minutesWatched
                            }
                            staff {
                                staff {
                                    name {
                                        full
                                    }
                                }
                                count
                                meanScore
                                minutesWatched
                            }
                            studios {
                                studio {
                                    name
                                }
                                count
                                meanScore
                                minutesWatched
                            }
                        }
                        manga {
                            count
                            meanScore
                            standardDeviation
                            chaptersRead
                            volumesRead
                            statuses {
                                status
                                count
                                meanScore
                                chaptersRead
                                volumesRead
                            }
                            scores {
                                score
                                count
                                meanScore
                                chaptersRead
                                volumesRead
                            }
                            lengths {
                                length
                                count
                                meanScore
                                chaptersRead
                                volumesRead
                            }
                            releaseYears {
                                releaseYear
                                count
                                meanScore
                                chaptersRead
                                volumesRead
                            }
                            startYears {
                                startYear
                                count
                                meanScore
                                chaptersRead
                                volumesRead
                            }
                            genres {
                                genre
                                count
                                meanScore
                                chaptersRead
                                volumesRead
                            }
                            tags {
                                tag {
                                    name
                                }
                                count
                                meanScore
                                chaptersRead
                                volumesRead
                            }
                            countries {
                                country
                                count
                                meanScore
                                chaptersRead
                                volumesRead
                            }
                            staff {
                                staff {
                                    name {
                                        full
                                    }
                                }
                                count
                                meanScore
                                chaptersRead
                                volumesRead
                            }
                        }
                    }
                }
            }
            '''
            
            variables = {"username": anilist_username}
            
            async with self.session.post(
                "https://graphql.anilist.co",
                json={"query": query, "variables": variables},
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("data", {}).get("User", {})
                else:
                    logger.error(f"AniList API error: {response.status}")
                    return {}
                    
        except Exception as e:
            logger.error(f"Error fetching analytics data: {e}")
            return {}

    async def calculate_reading_velocity(self, user_data: Dict) -> Dict:
        """Calculate reading velocity metrics"""
        try:
            manga_stats = user_data.get("statistics", {}).get("manga", {})
            
            total_chapters = manga_stats.get("chaptersRead", 0)
            total_volumes = manga_stats.get("volumesRead", 0)
            
            # Estimate reading time (avg 5 minutes per chapter)
            estimated_hours = total_chapters * 5 / 60
            
            # Get completion data by year to calculate velocity trends
            start_years = manga_stats.get("startYears", [])
            yearly_data = {}
            
            for year_data in start_years:
                year = year_data.get("startYear")
                chapters = year_data.get("chaptersRead", 0)
                if year and year >= 2020:  # Recent years only
                    yearly_data[year] = chapters
            
            # Calculate trends
            recent_velocity = 0
            velocity_trend = "stable"
            
            if len(yearly_data) >= 2:
                years = sorted(yearly_data.keys())
                recent_years = years[-2:]
                if len(recent_years) == 2:
                    old_velocity = yearly_data[recent_years[0]]
                    recent_velocity = yearly_data[recent_years[1]]
                    
                    if recent_velocity > old_velocity * 1.2:
                        velocity_trend = "increasing"
                    elif recent_velocity < old_velocity * 0.8:
                        velocity_trend = "decreasing"
            
            return {
                "total_chapters": total_chapters,
                "total_volumes": total_volumes,
                "estimated_hours": round(estimated_hours, 1),
                "chapters_per_month": round(total_chapters / 12, 1) if total_chapters > 0 else 0,
                "recent_velocity": recent_velocity,
                "velocity_trend": velocity_trend,
                "yearly_breakdown": yearly_data
            }
            
        except Exception as e:
            logger.error(f"Error calculating reading velocity: {e}")
            return {}

    async def analyze_genre_evolution(self, user_data: Dict) -> Dict:
        """Analyze how user's genre preferences have evolved"""
        try:
            manga_stats = user_data.get("statistics", {}).get("manga", {})
            genres = manga_stats.get("genres", [])
            
            # Sort genres by reading volume
            genre_data = {}
            total_chapters = sum(g.get("chaptersRead", 0) for g in genres)
            
            for genre in genres:
                name = genre.get("genre", "Unknown")
                chapters = genre.get("chaptersRead", 0)
                count = genre.get("count", 0)
                mean_score = genre.get("meanScore", 0)
                
                percentage = (chapters / total_chapters * 100) if total_chapters > 0 else 0
                
                genre_data[name] = {
                    "chapters": chapters,
                    "count": count,
                    "mean_score": mean_score,
                    "percentage": round(percentage, 1),
                    "avg_chapters_per_series": round(chapters / count, 1) if count > 0 else 0
                }
            
            # Find top genres and preferences
            top_genres = sorted(genre_data.items(), key=lambda x: x[1]["chapters"], reverse=True)[:10]
            favorite_genres = sorted(genre_data.items(), key=lambda x: x[1]["mean_score"], reverse=True)[:5]
            
            # Calculate diversity score (how varied user's reading is)
            genre_percentages = [g[1]["percentage"] for g in top_genres]
            diversity_score = 100 - max(genre_percentages) if genre_percentages else 0
            
            return {
                "total_genres": len(genres),
                "diversity_score": round(diversity_score, 1),
                "top_genres": top_genres,
                "favorite_genres": favorite_genres,
                "genre_data": genre_data
            }
            
        except Exception as e:
            logger.error(f"Error analyzing genre evolution: {e}")
            return {}

    async def detect_completion_patterns(self, user_data: Dict) -> Dict:
        """Detect patterns in completion behavior"""
        try:
            manga_stats = user_data.get("statistics", {}).get("manga", {})
            statuses = manga_stats.get("statuses", [])
            
            # Analyze completion rates
            status_data = {}
            total_entries = sum(s.get("count", 0) for s in statuses)
            
            for status in statuses:
                status_name = status.get("status", "UNKNOWN")
                count = status.get("count", 0)
                chapters = status.get("chaptersRead", 0)
                mean_score = status.get("meanScore", 0)
                
                percentage = (count / total_entries * 100) if total_entries > 0 else 0
                
                status_data[status_name] = {
                    "count": count,
                    "chapters": chapters,
                    "mean_score": mean_score,
                    "percentage": round(percentage, 1)
                }
            
            # Calculate completion rate
            completed = status_data.get("COMPLETED", {}).get("count", 0)
            completion_rate = (completed / total_entries * 100) if total_entries > 0 else 0
            
            # Analyze dropping patterns
            dropped = status_data.get("DROPPED", {}).get("count", 0)
            drop_rate = (dropped / total_entries * 100) if total_entries > 0 else 0
            
            # Completion personality
            personality = "Completer"
            if completion_rate >= 70:
                personality = "Dedicated Finisher"
            elif completion_rate >= 50:
                personality = "Selective Reader"
            elif drop_rate >= 30:
                personality = "Quick Dropper"
            elif status_data.get("PLANNING", {}).get("count", 0) > completed:
                personality = "Eternal Planner"
            
            return {
                "completion_rate": round(completion_rate, 1),
                "drop_rate": round(drop_rate, 1),
                "status_breakdown": status_data,
                "reading_personality": personality,
                "total_entries": total_entries
            }
            
        except Exception as e:
            logger.error(f"Error detecting completion patterns: {e}")
            return {}

    async def generate_social_comparison(self, user_data: Dict, guild_id: int) -> Dict:
        """Generate social comparisons with other guild members"""
        try:
            from database import get_all_guild_users
            
            # Get all guild users with AniList accounts
            guild_users = await get_all_guild_users(guild_id)
            if not guild_users or len(guild_users) < 2:
                return {"error": "Not enough guild members with linked AniList accounts"}
            
            user_stats = user_data.get("statistics", {}).get("manga", {})
            user_chapters = user_stats.get("chaptersRead", 0)
            user_mean_score = user_stats.get("meanScore", 0)
            user_count = user_stats.get("count", 0)
            
            # Compare with other guild members (simplified for now)
            comparisons = {
                "guild_rank": "Unknown",
                "chapters_percentile": 0,
                "activity_level": "Average",
                "total_members": len(guild_users)
            }
            
            # Simulate ranking (in real implementation, would fetch other users' data)
            if user_chapters >= 10000:
                comparisons["guild_rank"] = "Top Reader"
                comparisons["chapters_percentile"] = 90
                comparisons["activity_level"] = "Very High"
            elif user_chapters >= 5000:
                comparisons["guild_rank"] = "Active Reader" 
                comparisons["chapters_percentile"] = 75
                comparisons["activity_level"] = "High"
            elif user_chapters >= 1000:
                comparisons["guild_rank"] = "Regular Reader"
                comparisons["chapters_percentile"] = 50
                comparisons["activity_level"] = "Moderate"
            else:
                comparisons["guild_rank"] = "Casual Reader"
                comparisons["chapters_percentile"] = 25
                comparisons["activity_level"] = "Low"
            
            return comparisons
            
        except Exception as e:
            logger.error(f"Error generating social comparison: {e}")
            return {"error": "Could not generate social comparison"}

    async def predict_reading_trends(self, user_data: Dict) -> Dict:
        """Predict reading trends and recommendations"""
        try:
            manga_stats = user_data.get("statistics", {}).get("manga", {})
            
            # Analyze reading trends
            start_years = manga_stats.get("startYears", [])
            yearly_chapters = {}
            
            for year_data in start_years:
                year = year_data.get("startYear")
                chapters = year_data.get("chaptersRead", 0)
                if year and year >= 2020:  # Recent years only
                    yearly_chapters[year] = chapters
            
            # Simple trend prediction
            predictions = {
                "velocity_trend": "stable",
                "predicted_2024_chapters": 0,
                "reading_consistency": "moderate",
                "burn_out_risk": "low"
            }
            
            if len(yearly_chapters) >= 2:
                years = sorted(yearly_chapters.keys())
                recent_years = years[-2:]
                
                if len(recent_years) == 2:
                    old_chapters = yearly_chapters[recent_years[0]]
                    new_chapters = yearly_chapters[recent_years[1]]
                    
                    # Calculate trend
                    if new_chapters > old_chapters * 1.3:
                        predictions["velocity_trend"] = "rapidly_increasing"
                        predictions["burn_out_risk"] = "medium"
                    elif new_chapters > old_chapters * 1.1:
                        predictions["velocity_trend"] = "increasing"
                        predictions["burn_out_risk"] = "low"
                    elif new_chapters < old_chapters * 0.7:
                        predictions["velocity_trend"] = "decreasing"
                    
                    # Predict next year
                    growth_rate = new_chapters / old_chapters if old_chapters > 0 else 1
                    predictions["predicted_2024_chapters"] = int(new_chapters * growth_rate)
            
            return predictions
            
        except Exception as e:
            logger.error(f"Error predicting reading trends: {e}")
            return {}

    # ===== DASHBOARD EMBED BUILDERS =====
    
    async def build_yearly_wrap_embed(self, user_data: Dict, analytics: Dict) -> discord.Embed:
        """Build Spotify-style yearly wrap embed"""
        try:
            username = user_data.get("name", "Unknown User")
            current_year = datetime.now().year
            
            # Get key statistics
            velocity = analytics.get("velocity", {})
            genres = analytics.get("genres", {})
            patterns = analytics.get("patterns", {})
            
            embed = discord.Embed(
                title=f"📊 {username}'s {current_year} Wrap",
                description=f"Your year in manga & anime",
                color=discord.Color.purple()
            )
            
            # Reading volume
            chapters = velocity.get("total_chapters", 0)
            hours = velocity.get("estimated_hours", 0)
            embed.add_field(
                name="📚 Reading Volume",
                value=f"**{chapters:,}** chapters read\n**{hours}** estimated hours\n**{velocity.get('chapters_per_month', 0)}** chapters/month",
                inline=True
            )
            
            # Top genres
            top_genres = genres.get("top_genres", [])[:3]
            genre_text = "\n".join([f"**{g[0]}** ({g[1]['percentage']}%)" for g in top_genres])
            embed.add_field(
                name="🎭 Top Genres",
                value=genre_text or "No data available",
                inline=True
            )
            
            # Reading personality
            personality = patterns.get("reading_personality", "Unknown")
            completion_rate = patterns.get("completion_rate", 0)
            embed.add_field(
                name="🧬 Reading DNA",
                value=f"**{personality}**\n{completion_rate}% completion rate",
                inline=True
            )
            
            # Achievements and milestones
            achievements = []
            if chapters >= 10000:
                achievements.append("🏆 10K+ Chapter Master")
            if completion_rate >= 80:
                achievements.append("💯 Completion Champion")
            if genres.get("diversity_score", 0) >= 70:
                achievements.append("🌟 Genre Explorer")
            
            if achievements:
                embed.add_field(
                    name="🏅 Achievements Unlocked",
                    value="\n".join(achievements),
                    inline=False
                )
            
            embed.set_footer(text="Data from AniList • Powered by Lemegeton")
            return embed
            
        except Exception as e:
            logger.error(f"Error building yearly wrap embed: {e}")
            return discord.Embed(title="Error", description="Failed to build yearly wrap", color=discord.Color.red())

    async def build_genre_analysis_embed(self, analytics: Dict) -> discord.Embed:
        """Build genre evolution analysis embed"""
        try:
            genres = analytics.get("genres", {})
            
            embed = discord.Embed(
                title="🎭 Genre Evolution Analysis",
                description="How your taste has evolved over time",
                color=discord.Color.blue()
            )
            
            # Diversity metrics
            diversity = genres.get("diversity_score", 0)
            total_genres = genres.get("total_genres", 0)
            
            embed.add_field(
                name="📈 Diversity Score",
                value=f"**{diversity}/100**\n({total_genres} genres explored)",
                inline=True
            )
            
            # Top genres by volume
            top_genres = genres.get("top_genres", [])[:5]
            volume_text = ""
            for genre, data in top_genres:
                volume_text += f"**{genre}**: {data['chapters']:,} chapters ({data['percentage']}%)\n"
            
            embed.add_field(
                name="📚 Most Read Genres",
                value=volume_text or "No data available",
                inline=False
            )
            
            # Favorite genres by score
            favorite_genres = genres.get("favorite_genres", [])[:5]
            favorite_text = ""
            for genre, data in favorite_genres:
                if data['mean_score'] > 0:
                    favorite_text += f"**{genre}**: {data['mean_score']}/10 avg score\n"
            
            if favorite_text:
                embed.add_field(
                    name="⭐ Highest Rated Genres",
                    value=favorite_text,
                    inline=False
                )
            
            embed.set_footer(text="Genre preferences based on your reading history")
            return embed
            
        except Exception as e:
            logger.error(f"Error building genre analysis embed: {e}")
            return discord.Embed(title="Error", description="Failed to build genre analysis", color=discord.Color.red())

    # ===== SLASH COMMANDS =====
    
    @app_commands.command(name="analytics_dashboard", description="Open your comprehensive analytics dashboard")
    @app_commands.describe(
        period="Time period for analysis (default: year)",
        user="AniList username (uses your linked account if not specified)"
    )
    async def analytics_dashboard(
        self, 
        interaction: discord.Interaction, 
        period: Optional[str] = "year",
        user: Optional[str] = None
    ):
        """Open the interactive analytics dashboard"""
        await interaction.response.defer()
        
        try:
            # Get user's AniList username
            if user is None:
                from database import get_user_guild_aware
                user_row = await get_user_guild_aware(interaction.user.id, interaction.guild.id)
                if not user_row or not user_row[2]:  # anilist_username is index 2
                    await interaction.followup.send(
                        "❌ You need to link your AniList account first! Use `/login` to get started.",
                        ephemeral=True
                    )
                    return
                anilist_username = user_row[2]
            else:
                anilist_username = user
            
            # Parse period
            try:
                analytics_period = AnalyticsPeriod(period.lower())
            except ValueError:
                analytics_period = AnalyticsPeriod.YEAR
            
            # Fetch analytics data
            user_data = await self.fetch_user_analytics_data(anilist_username, analytics_period)
            if not user_data:
                await interaction.followup.send(
                    f"❌ Could not fetch data for AniList user '{anilist_username}'",
                    ephemeral=True
                )
                return
            
            # Calculate all analytics
            velocity_analysis = await self.calculate_reading_velocity(user_data)
            genre_analysis = await self.analyze_genre_evolution(user_data)
            pattern_analysis = await self.detect_completion_patterns(user_data)
            social_analysis = await self.generate_social_comparison(user_data, interaction.guild.id)
            predictions = await self.predict_reading_trends(user_data)
            
            analytics = {
                "velocity": velocity_analysis,
                "genres": genre_analysis,
                "patterns": pattern_analysis,
                "social": social_analysis,
                "predictions": predictions
            }
            
            # Create interactive dashboard view
            from .analytics_views import AnalyticsDashboardView
            view = AnalyticsDashboardView(user_data, analytics, anilist_username)
            
            # Build initial embed (yearly wrap)
            embed = await view.build_yearly_wrap_embed()
            
            await interaction.followup.send(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"Error in analytics_dashboard command: {e}")
            await interaction.followup.send(
                "❌ An error occurred while loading your analytics dashboard. Please try again.",
                ephemeral=True
            )
    
    @app_commands.command(name="yearly_wrap", description="Get your personalized yearly reading wrap")
    @app_commands.describe(
        period="Time period for analysis (default: year)",
        user="AniList username (uses your linked account if not specified)"
    )
    async def yearly_wrap(
        self, 
        interaction: discord.Interaction, 
        period: Optional[str] = "year",
        user: Optional[str] = None
    ):
        """Generate a personalized yearly wrap for the user"""
        await interaction.response.defer()
        
        try:
            # Get user's AniList username
            if user is None:
                from database import get_user_guild_aware
                user_row = await get_user_guild_aware(interaction.user.id, interaction.guild.id)
                if not user_row or not user_row[2]:  # anilist_username is index 2
                    await interaction.followup.send(
                        "❌ You need to link your AniList account first! Use `/login` to get started.",
                        ephemeral=True
                    )
                    return
                anilist_username = user_row[2]
            else:
                anilist_username = user
            
            # Parse period
            try:
                analytics_period = AnalyticsPeriod(period.lower())
            except ValueError:
                analytics_period = AnalyticsPeriod.YEAR
            
            # Fetch analytics data
            user_data = await self.fetch_user_analytics_data(anilist_username, analytics_period)
            if not user_data:
                await interaction.followup.send(
                    f"❌ Could not fetch data for AniList user '{anilist_username}'",
                    ephemeral=True
                )
                return
            
            # Calculate analytics
            velocity_analysis = await self.calculate_reading_velocity(user_data)
            genre_analysis = await self.analyze_genre_evolution(user_data)
            pattern_analysis = await self.detect_completion_patterns(user_data)
            
            analytics = {
                "velocity": velocity_analysis,
                "genres": genre_analysis,
                "patterns": pattern_analysis
            }
            
            # Build and send embed
            embed = await self.build_yearly_wrap_embed(user_data, analytics)
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in yearly_wrap command: {e}")
            await interaction.followup.send(
                "❌ An error occurred while generating your yearly wrap. Please try again.",
                ephemeral=True
            )

    @app_commands.command(name="genre_analysis", description="Analyze your genre preferences and evolution")
    @app_commands.describe(user="AniList username (uses your linked account if not specified)")
    async def genre_analysis(self, interaction: discord.Interaction, user: Optional[str] = None):
        """Analyze user's genre preferences and evolution"""
        await interaction.response.defer()
        
        try:
            # Get user's AniList username
            if user is None:
                from database import get_user_guild_aware
                user_row = await get_user_guild_aware(interaction.user.id, interaction.guild.id)
                if not user_row or not user_row[2]:
                    await interaction.followup.send(
                        "❌ You need to link your AniList account first! Use `/login` to get started.",
                        ephemeral=True
                    )
                    return
                anilist_username = user_row[2]
            else:
                anilist_username = user
            
            # Fetch analytics data
            user_data = await self.fetch_user_analytics_data(anilist_username)
            if not user_data:
                await interaction.followup.send(
                    f"❌ Could not fetch data for AniList user '{anilist_username}'",
                    ephemeral=True
                )
                return
            
            # Calculate genre analytics
            genre_analysis = await self.analyze_genre_evolution(user_data)
            analytics = {"genres": genre_analysis}
            
            # Build and send embed
            embed = await self.build_genre_analysis_embed(analytics)
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in genre_analysis command: {e}")
            await interaction.followup.send(
                "❌ An error occurred while analyzing your genres. Please try again.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(AnalyticsDashboard(bot))