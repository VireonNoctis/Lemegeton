"""
Interactive Analytics Dashboard Views
Provides interactive UI components for the analytics dashboard
"""

import discord
from discord.ext import commands
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class AnalyticsDashboardView(discord.ui.View):
    """Main analytics dashboard with navigation buttons"""
    
    def __init__(self, user_data: Dict, analytics: Dict, anilist_username: str):
        super().__init__(timeout=300.0)
        self.user_data = user_data
        self.analytics = analytics
        self.anilist_username = anilist_username
        self.current_page = "wrap"
        
    @discord.ui.button(label="📊 Yearly Wrap", style=discord.ButtonStyle.primary, custom_id="yearly_wrap")
    async def yearly_wrap_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show yearly wrap dashboard"""
        try:
            self.current_page = "wrap"
            embed = await self.build_yearly_wrap_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            logger.error(f"Error in yearly wrap button: {e}")
            await interaction.response.send_message("❌ Error loading yearly wrap", ephemeral=True)
    
    @discord.ui.button(label="🎭 Genres", style=discord.ButtonStyle.secondary, custom_id="genres")
    async def genres_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show genre analysis dashboard"""
        try:
            self.current_page = "genres"
            embed = await self.build_genre_analysis_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            logger.error(f"Error in genres button: {e}")
            await interaction.response.send_message("❌ Error loading genre analysis", ephemeral=True)
    
    @discord.ui.button(label="📈 Patterns", style=discord.ButtonStyle.secondary, custom_id="patterns")
    async def patterns_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show completion patterns dashboard"""
        try:
            self.current_page = "patterns"
            embed = await self.build_patterns_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            logger.error(f"Error in patterns button: {e}")
            await interaction.response.send_message("❌ Error loading patterns analysis", ephemeral=True)
    
    @discord.ui.button(label="⚡ Velocity", style=discord.ButtonStyle.secondary, custom_id="velocity")
    async def velocity_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show reading velocity dashboard"""
        try:
            self.current_page = "velocity"
            embed = await self.build_velocity_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            logger.error(f"Error in velocity button: {e}")
            await interaction.response.send_message("❌ Error loading velocity analysis", ephemeral=True)
    
    @discord.ui.button(label="🏆 Achievements", style=discord.ButtonStyle.success, custom_id="achievements")
    async def achievements_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show achievements dashboard"""
        try:
            self.current_page = "achievements"
            embed = await self.build_achievements_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            logger.error(f"Error in achievements button: {e}")
            await interaction.response.send_message("❌ Error loading achievements", ephemeral=True)

    @discord.ui.button(label="👥 Social", style=discord.ButtonStyle.secondary, custom_id="social", row=1)
    async def social_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show social comparison dashboard"""
        try:
            self.current_page = "social"
            embed = await self.build_social_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            logger.error(f"Error in social button: {e}")
            await interaction.response.send_message("❌ Error loading social comparison", ephemeral=True)

    @discord.ui.button(label="🔮 Predictions", style=discord.ButtonStyle.secondary, custom_id="predictions", row=1)
    async def predictions_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show reading predictions dashboard"""
        try:
            self.current_page = "predictions"
            embed = await self.build_predictions_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            logger.error(f"Error in predictions button: {e}")
            await interaction.response.send_message("❌ Error loading predictions", ephemeral=True)

    async def on_timeout(self):
        """Disable all buttons when view times out"""
        for item in self.children:
            item.disabled = True
        
    # ===== EMBED BUILDERS =====
    
    async def build_yearly_wrap_embed(self) -> discord.Embed:
        """Build yearly wrap embed"""
        try:
            username = self.user_data.get("name", "Unknown User")
            current_year = datetime.now().year
            
            velocity = self.analytics.get("velocity", {})
            genres = self.analytics.get("genres", {})
            patterns = self.analytics.get("patterns", {})
            
            embed = discord.Embed(
                title=f"📊 {username}'s {current_year} Wrap",
                description=f"Your year in manga & anime reading",
                color=discord.Color.purple()
            )
            
            # Key metrics
            chapters = velocity.get("total_chapters", 0)
            hours = velocity.get("estimated_hours", 0)
            completion_rate = patterns.get("completion_rate", 0)
            
            embed.add_field(
                name="📚 Reading Volume",
                value=f"**{chapters:,}** chapters\n**{hours}** hours\n**{velocity.get('chapters_per_month', 0)}**/month",
                inline=True
            )
            
            # Top genres
            top_genres = genres.get("top_genres", [])[:3]
            genre_text = "\n".join([f"**{g[0]}** ({g[1]['percentage']}%)" for g in top_genres])
            embed.add_field(
                name="🎭 Top Genres",
                value=genre_text or "No data",
                inline=True
            )
            
            # Personality & achievements
            personality = patterns.get("reading_personality", "Unknown")
            embed.add_field(
                name="🧬 Reading DNA",
                value=f"**{personality}**\n{completion_rate}% completion",
                inline=True
            )
            
            # Year highlights
            highlights = []
            if chapters >= 5000:
                highlights.append("🌟 Heavy Reader (5K+ chapters)")
            if completion_rate >= 75:
                highlights.append("💯 Completion Master")
            if genres.get("diversity_score", 0) >= 60:
                highlights.append("🌈 Genre Explorer")
            
            if highlights:
                embed.add_field(
                    name="✨ Year Highlights",
                    value="\n".join(highlights),
                    inline=False
                )
            
            embed.set_footer(text=f"Dashboard • Use buttons to explore more analytics")
            return embed
            
        except Exception as e:
            logger.error(f"Error building yearly wrap: {e}")
            return discord.Embed(title="Error", description="Failed to build yearly wrap", color=discord.Color.red())
    
    async def build_genre_analysis_embed(self) -> discord.Embed:
        """Build genre analysis embed"""
        try:
            username = self.user_data.get("name", "Unknown User")
            genres = self.analytics.get("genres", {})
            
            embed = discord.Embed(
                title=f"🎭 {username}'s Genre Analysis",
                description="Deep dive into your reading preferences",
                color=discord.Color.blue()
            )
            
            # Diversity metrics
            diversity = genres.get("diversity_score", 0)
            total_genres = genres.get("total_genres", 0)
            
            diversity_level = "Focused Reader"
            if diversity >= 80:
                diversity_level = "Genre Hopper"
            elif diversity >= 60:
                diversity_level = "Balanced Explorer"
            elif diversity >= 40:
                diversity_level = "Moderate Explorer"
            
            embed.add_field(
                name="🌈 Diversity Analysis",
                value=f"**{diversity}/100** Diversity Score\n**{diversity_level}**\n{total_genres} genres explored",
                inline=True
            )
            
            # Top genres by volume
            top_genres = genres.get("top_genres", [])[:5]
            volume_text = ""
            for i, (genre, data) in enumerate(top_genres):
                emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i]
                volume_text += f"{emoji} **{genre}**: {data['chapters']:,} ch ({data['percentage']}%)\n"
            
            embed.add_field(
                name="📊 Most Read Genres",
                value=volume_text or "No data available",
                inline=False
            )
            
            # Favorite genres by rating
            favorite_genres = genres.get("favorite_genres", [])[:5]
            favorite_text = ""
            for i, (genre, data) in enumerate(favorite_genres):
                if data['mean_score'] > 0:
                    emoji = ["⭐", "🌟", "✨", "💫", "🔥"][i]
                    favorite_text += f"{emoji} **{genre}**: {data['mean_score']:.1f}/10\n"
            
            if favorite_text:
                embed.add_field(
                    name="💝 Highest Rated Genres",
                    value=favorite_text,
                    inline=False
                )
            
            embed.set_footer(text="Genre preferences • Based on your reading history")
            return embed
            
        except Exception as e:
            logger.error(f"Error building genre analysis: {e}")
            return discord.Embed(title="Error", description="Failed to build genre analysis", color=discord.Color.red())
    
    async def build_patterns_embed(self) -> discord.Embed:
        """Build completion patterns embed"""
        try:
            username = self.user_data.get("name", "Unknown User")
            patterns = self.analytics.get("patterns", {})
            
            embed = discord.Embed(
                title=f"📈 {username}'s Reading Patterns",
                description="Analysis of your completion behavior",
                color=discord.Color.green()
            )
            
            # Core metrics
            completion_rate = patterns.get("completion_rate", 0)
            drop_rate = patterns.get("drop_rate", 0)
            personality = patterns.get("reading_personality", "Unknown")
            
            embed.add_field(
                name="🧬 Reading Personality",
                value=f"**{personality}**",
                inline=True
            )
            
            embed.add_field(
                name="✅ Completion Rate",
                value=f"**{completion_rate}%**\n{'Above Average' if completion_rate > 50 else 'Below Average'}",
                inline=True
            )
            
            embed.add_field(
                name="❌ Drop Rate",
                value=f"**{drop_rate}%**\n{'High' if drop_rate > 20 else 'Low' if drop_rate < 10 else 'Moderate'}",
                inline=True
            )
            
            # Status breakdown
            status_breakdown = patterns.get("status_breakdown", {})
            status_text = ""
            status_emojis = {
                "COMPLETED": "✅",
                "CURRENT": "📖", 
                "PLANNING": "📋",
                "PAUSED": "⏸️",
                "DROPPED": "❌",
                "REPEATING": "🔄"
            }
            
            for status, data in status_breakdown.items():
                emoji = status_emojis.get(status, "📊")
                count = data.get("count", 0)
                percentage = data.get("percentage", 0)
                if count > 0:
                    status_text += f"{emoji} {status.title()}: {count} ({percentage}%)\n"
            
            if status_text:
                embed.add_field(
                    name="📊 Status Breakdown",
                    value=status_text,
                    inline=False
                )
            
            # Insights
            insights = []
            if completion_rate >= 80:
                insights.append("🏆 You're a dedicated finisher!")
            if drop_rate <= 5:
                insights.append("💪 You rarely drop series")
            if status_breakdown.get("PLANNING", {}).get("count", 0) > 50:
                insights.append("📚 You have a big to-read list!")
            
            if insights:
                embed.add_field(
                    name="💡 Insights",
                    value="\n".join(insights),
                    inline=False
                )
            
            embed.set_footer(text="Reading patterns • Based on your AniList data")
            return embed
            
        except Exception as e:
            logger.error(f"Error building patterns embed: {e}")
            return discord.Embed(title="Error", description="Failed to build patterns analysis", color=discord.Color.red())
    
    async def build_velocity_embed(self) -> discord.Embed:
        """Build reading velocity embed"""
        try:
            username = self.user_data.get("name", "Unknown User")
            velocity = self.analytics.get("velocity", {})
            
            embed = discord.Embed(
                title=f"⚡ {username}'s Reading Velocity",
                description="How fast do you read?",
                color=discord.Color.orange()
            )
            
            # Core velocity metrics
            total_chapters = velocity.get("total_chapters", 0)
            estimated_hours = velocity.get("estimated_hours", 0)
            chapters_per_month = velocity.get("chapters_per_month", 0)
            
            embed.add_field(
                name="📊 Total Volume",
                value=f"**{total_chapters:,}** chapters\n**{estimated_hours}** hours\n**{velocity.get('total_volumes', 0):,}** volumes",
                inline=True
            )
            
            embed.add_field(
                name="⚡ Reading Speed",
                value=f"**{chapters_per_month}** ch/month\n**{round(chapters_per_month/30, 1) if chapters_per_month > 0 else 0}** ch/day",
                inline=True
            )
            
            # Velocity trend
            trend = velocity.get("velocity_trend", "stable")
            trend_emojis = {
                "increasing": "📈 Accelerating",
                "decreasing": "📉 Slowing Down", 
                "stable": "➡️ Consistent"
            }
            
            embed.add_field(
                name="📈 Trend",
                value=trend_emojis.get(trend, "➡️ Stable"),
                inline=True
            )
            
            # Yearly breakdown
            yearly_data = velocity.get("yearly_breakdown", {})
            if yearly_data:
                yearly_text = ""
                for year in sorted(yearly_data.keys(), reverse=True)[:5]:  # Last 5 years
                    chapters = yearly_data[year]
                    yearly_text += f"**{year}**: {chapters:,} chapters\n"
                
                if yearly_text:
                    embed.add_field(
                        name="📅 Yearly Breakdown",
                        value=yearly_text,
                        inline=False
                    )
            
            # Speed classification
            speed_class = "Moderate Reader"
            if chapters_per_month >= 500:
                speed_class = "Speed Reader"
            elif chapters_per_month >= 200:
                speed_class = "Fast Reader"
            elif chapters_per_month >= 100:
                speed_class = "Active Reader"
            elif chapters_per_month < 20:
                speed_class = "Casual Reader"
            
            embed.add_field(
                name="🏷️ Reader Type",
                value=f"**{speed_class}**",
                inline=True
            )
            
            embed.set_footer(text="Reading velocity • Based on chapter counts and estimates")
            return embed
            
        except Exception as e:
            logger.error(f"Error building velocity embed: {e}")
            return discord.Embed(title="Error", description="Failed to build velocity analysis", color=discord.Color.red())
    
    async def build_achievements_embed(self) -> discord.Embed:
        """Build achievements embed"""
        try:
            username = self.user_data.get("name", "Unknown User")
            velocity = self.analytics.get("velocity", {})
            genres = self.analytics.get("genres", {})
            patterns = self.analytics.get("patterns", {})
            
            embed = discord.Embed(
                title=f"🏆 {username}'s Achievements",
                description="Unlock achievements based on your reading habits",
                color=discord.Color.gold()
            )
            
            achievements = []
            
            # Volume achievements
            chapters = velocity.get("total_chapters", 0)
            if chapters >= 50000:
                achievements.append("🌟 **Legendary Reader** - 50,000+ chapters")
            elif chapters >= 25000:
                achievements.append("💎 **Chapter Master** - 25,000+ chapters")
            elif chapters >= 10000:
                achievements.append("🏆 **10K Club** - 10,000+ chapters")
            elif chapters >= 5000:
                achievements.append("🥇 **Heavy Reader** - 5,000+ chapters")
            elif chapters >= 1000:
                achievements.append("🥈 **Committed Reader** - 1,000+ chapters")
            
            # Completion achievements  
            completion_rate = patterns.get("completion_rate", 0)
            if completion_rate >= 90:
                achievements.append("💯 **Perfectionist** - 90%+ completion rate")
            elif completion_rate >= 80:
                achievements.append("✅ **Finisher** - 80%+ completion rate")
            elif completion_rate >= 70:
                achievements.append("🎯 **Dedicated** - 70%+ completion rate")
            
            # Genre achievements
            diversity = genres.get("diversity_score", 0)
            total_genres = genres.get("total_genres", 0)
            if diversity >= 80:
                achievements.append("🌈 **Genre Hopper** - Highly diverse reading")
            elif total_genres >= 20:
                achievements.append("🎭 **Genre Explorer** - 20+ genres explored")
            
            # Speed achievements
            chapters_per_month = velocity.get("chapters_per_month", 0)
            if chapters_per_month >= 500:
                achievements.append("⚡ **Speed Demon** - 500+ chapters/month")
            elif chapters_per_month >= 200:
                achievements.append("🚄 **Fast Reader** - 200+ chapters/month")
            
            # Special achievements
            drop_rate = patterns.get("drop_rate", 0)
            if drop_rate <= 5:
                achievements.append("💪 **Never Give Up** - <5% drop rate")
            
            status_breakdown = patterns.get("status_breakdown", {})
            if status_breakdown.get("PLANNING", {}).get("count", 0) >= 100:
                achievements.append("📚 **List Builder** - 100+ planned entries")
            
            # Display achievements
            if achievements:
                # Split into groups of 5 for better formatting
                for i in range(0, len(achievements), 5):
                    group = achievements[i:i+5]
                    field_name = "🏅 Unlocked Achievements" if i == 0 else "More Achievements"
                    embed.add_field(
                        name=field_name,
                        value="\n".join(group),
                        inline=False
                    )
            else:
                embed.add_field(
                    name="🏅 Achievements",
                    value="Keep reading to unlock achievements!",
                    inline=False
                )
            
            # Progress towards next achievement
            next_achievements = []
            if chapters < 1000:
                needed = 1000 - chapters
                next_achievements.append(f"📖 {needed:,} chapters to **Committed Reader**")
            elif chapters < 5000:
                needed = 5000 - chapters  
                next_achievements.append(f"📖 {needed:,} chapters to **Heavy Reader**")
            elif chapters < 10000:
                needed = 10000 - chapters
                next_achievements.append(f"📖 {needed:,} chapters to **10K Club**")
            
            if completion_rate < 70:
                needed = 70 - completion_rate
                next_achievements.append(f"✅ {needed:.1f}% to **Dedicated** completion")
            
            if next_achievements:
                embed.add_field(
                    name="🎯 Next Milestones",
                    value="\n".join(next_achievements[:3]),  # Top 3
                    inline=False
                )
            
            embed.set_footer(text=f"Achievement system • {len(achievements)} unlocked")
            return embed
            
        except Exception as e:
            logger.error(f"Error building achievements embed: {e}")
            return discord.Embed(title="Error", description="Failed to build achievements", color=discord.Color.red())

    async def build_social_embed(self) -> discord.Embed:
        """Build social comparison embed"""
        try:
            username = self.user_data.get("name", "Unknown User")
            social = self.analytics.get("social", {})
            
            embed = discord.Embed(
                title=f"👥 {username}'s Social Stats",
                description="How do you compare to your server?",
                color=discord.Color.blurple()
            )
            
            if "error" in social:
                embed.add_field(
                    name="⚠️ Limited Data",
                    value=social["error"],
                    inline=False
                )
                return embed
            
            # Guild ranking
            guild_rank = social.get("guild_rank", "Unknown")
            percentile = social.get("chapters_percentile", 0)
            total_members = social.get("total_members", 0)
            activity_level = social.get("activity_level", "Average")
            
            embed.add_field(
                name="🏆 Guild Ranking",
                value=f"**{guild_rank}**\nTop {100-percentile}% in server",
                inline=True
            )
            
            embed.add_field(
                name="📊 Activity Level", 
                value=f"**{activity_level}**\nAmong {total_members} members",
                inline=True
            )
            
            embed.add_field(
                name="📈 Percentile",
                value=f"**{percentile}th** percentile\nBetter than {percentile}% of server",
                inline=True
            )
            
            # Social insights
            insights = []
            if percentile >= 90:
                insights.append("🌟 You're a top reader in this server!")
            elif percentile >= 75:
                insights.append("📚 You're very active compared to others")
            elif percentile >= 50:
                insights.append("📖 You're an average reader in this server")
            else:
                insights.append("🌱 Room to grow compared to server members")
            
            if activity_level == "Very High":
                insights.append("⚡ Your activity level is exceptional")
            
            if insights:
                embed.add_field(
                    name="💡 Social Insights",
                    value="\n".join(insights),
                    inline=False
                )
            
            embed.add_field(
                name="🎯 Social Goals",
                value="• Share recommendations with server\n• Join reading discussions\n• Compete in reading challenges",
                inline=False
            )
            
            embed.set_footer(text="Social comparison • Based on linked AniList accounts")
            return embed
            
        except Exception as e:
            logger.error(f"Error building social embed: {e}")
            return discord.Embed(title="Error", description="Failed to build social comparison", color=discord.Color.red())

    async def build_predictions_embed(self) -> discord.Embed:
        """Build reading predictions embed"""
        try:
            username = self.user_data.get("name", "Unknown User")
            predictions = self.analytics.get("predictions", {})
            velocity = self.analytics.get("velocity", {})
            
            embed = discord.Embed(
                title=f"🔮 {username}'s Reading Predictions",
                description="AI-powered insights into your reading future",
                color=discord.Color.purple()
            )
            
            # Velocity trend
            trend = predictions.get("velocity_trend", "stable")
            trend_descriptions = {
                "rapidly_increasing": "📈 **Rapidly Accelerating** - You're reading much more lately",
                "increasing": "📈 **Growing** - Your reading pace is picking up",
                "stable": "➡️ **Consistent** - You maintain a steady reading pace", 
                "decreasing": "📉 **Slowing** - Your reading pace has decreased"
            }
            
            embed.add_field(
                name="📊 Velocity Trend",
                value=trend_descriptions.get(trend, "➡️ Stable trend"),
                inline=False
            )
            
            # Predictions for next year
            predicted_chapters = predictions.get("predicted_2024_chapters", 0)
            current_chapters = velocity.get("total_chapters", 0)
            
            if predicted_chapters > 0:
                embed.add_field(
                    name="🎯 2024 Prediction",
                    value=f"**~{predicted_chapters:,}** chapters predicted\nBased on current trends",
                    inline=True
                )
            
            # Consistency analysis
            consistency = predictions.get("reading_consistency", "moderate")
            consistency_descriptions = {
                "high": "🎯 **Very Consistent** - You read regularly",
                "moderate": "📊 **Moderately Consistent** - Some variation in reading",
                "low": "🔄 **Variable** - Your reading comes in bursts"
            }
            
            embed.add_field(
                name="📈 Consistency",
                value=consistency_descriptions.get(consistency, "📊 Moderate"),
                inline=True
            )
            
            # Burnout risk
            burnout_risk = predictions.get("burn_out_risk", "low")
            burnout_colors = {"low": "🟢", "medium": "🟡", "high": "🔴"}
            burnout_desc = {
                "low": "Low risk - Sustainable pace",
                "medium": "Medium risk - Consider taking breaks",
                "high": "High risk - Slow down to avoid burnout"
            }
            
            embed.add_field(
                name="⚠️ Burnout Risk",
                value=f"{burnout_colors.get(burnout_risk, '🟢')} **{burnout_risk.title()}**\n{burnout_desc.get(burnout_risk, 'Normal risk')}",
                inline=True
            )
            
            # Recommendations based on predictions
            recommendations = []
            if trend == "rapidly_increasing":
                recommendations.append("💡 Consider diversifying genres to maintain interest")
                recommendations.append("⏰ Schedule regular breaks to prevent burnout")
            elif trend == "decreasing":
                recommendations.append("🎯 Set small daily reading goals to rebuild momentum")
                recommendations.append("📚 Try shorter series to regain reading confidence")
            elif trend == "stable":
                recommendations.append("🌟 Your reading pace is healthy and sustainable")
                recommendations.append("🎭 Explore new genres to keep things fresh")
            
            if burnout_risk == "medium":
                recommendations.append("🛑 Consider reducing reading pace temporarily")
            
            if recommendations:
                embed.add_field(
                    name="💭 AI Recommendations",
                    value="\n".join(recommendations[:4]),  # Top 4 recommendations
                    inline=False
                )
            
            # Future milestones
            milestones = []
            current_monthly = velocity.get("chapters_per_month", 0)
            if current_monthly > 0:
                months_to_next_1k = max(1, int(1000 / current_monthly))
                if months_to_next_1k <= 12:
                    milestones.append(f"📅 ~{months_to_next_1k} months to next 1,000 chapters")
            
            if predicted_chapters > current_chapters:
                growth = predicted_chapters - current_chapters
                milestones.append(f"📈 Projected +{growth:,} chapters this year")
            
            if milestones:
                embed.add_field(
                    name="🎯 Future Milestones",
                    value="\n".join(milestones),
                    inline=False
                )
            
            embed.set_footer(text="Predictions • Based on machine learning analysis of your patterns")
            return embed
            
        except Exception as e:
            logger.error(f"Error building predictions embed: {e}")
            return discord.Embed(title="Error", description="Failed to build predictions", color=discord.Color.red())