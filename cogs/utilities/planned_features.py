import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, Dict, List
import json
import os
import logging
from datetime import datetime

# Set up logging
logger = logging.getLogger('planned_features')

class PlannedFeatures(commands.Cog):
    """Planned features management system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data_file = "data/planned_features.json"
        self.features_data = self.load_features()
    
    def load_features(self) -> Dict:
        """Load features data from JSON file"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"Loaded planned features data: {len(data.get('planned', []))} planned features")
                return data
            else:
                logger.info("No planned features data file found, creating default structure")
                return {
                    "planned": [],
                    "last_updated": datetime.now().isoformat()
                }
        except Exception as e:
            logger.error(f"Error loading planned features data: {e}")
            return {
                "planned": [],
                "last_updated": datetime.now().isoformat()
            }
    
    def save_features(self) -> bool:
        """Save features data to JSON file"""
        try:
            # Ensure data directory exists
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            
            # Update last modified timestamp
            self.features_data["last_updated"] = datetime.now().isoformat()
            
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.features_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Planned features data saved successfully to {self.data_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving planned features data: {e}")
            return False
    
    def has_mod_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if user has moderator permissions"""
        try:
            import config
            mod_role_id = config.MOD_ROLE_ID
            
            # Check if user has the mod role
            if hasattr(interaction.user, 'roles') and mod_role_id:
                for role in interaction.user.roles:
                    if role.id == mod_role_id:
                        return True
            
            # Check if user is guild owner
            if interaction.guild and interaction.user.id == interaction.guild.owner_id:
                return True
                
            return False
        except Exception as e:
            logger.error(f"Error checking mod permissions: {e}")
            return False
    
    def create_features_embed(self, page: int = 1) -> discord.Embed:
        """Create an embed displaying planned features"""
        features = self.features_data.get("planned", [])
        
        # Pagination settings
        features_per_page = 1
        total_pages = max(1, (len(features) + features_per_page - 1) // features_per_page)
        start_idx = (page - 1) * features_per_page
        end_idx = start_idx + features_per_page
        page_features = features[start_idx:end_idx]
        
        # Create embed
        embed = discord.Embed(
            title="🚀 Planned Features",
            description=f"Page {page}/{total_pages} • Total: {len(features)} features",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        # Add features to embed
        if page_features:
            for i, feature in enumerate(page_features, start=start_idx + 1):
                name = feature.get('name', 'Unknown Feature')
                description = feature.get('description', 'No description available')
                added_date = feature.get('added_date', 'Unknown')
                
                # No truncation - display full description
                # if len(description) > 1000:
                #     description = description[:997] + "..."
                
                embed.add_field(
                    name=f"{i}. {name}",
                    value=f"{description}\n*Added: {added_date[:10] if len(added_date) >= 10 else added_date}*",
                    inline=False
                )
        else:
            embed.add_field(
                name="No Features",
                value="No planned features have been added yet.",
                inline=False
            )
        
        # Add footer with last updated info
        last_updated = self.features_data.get('last_updated', 'Unknown')
        embed.set_footer(text=f"Last updated: {last_updated[:19] if len(last_updated) >= 19 else last_updated}")
        
        return embed

    class FeatureView(discord.ui.View):
        """View for navigating between feature pages"""
        
        def __init__(self, cog, current_page: int = 1):
            super().__init__(timeout=300)
            self.cog = cog
            self.current_page = current_page
            self.update_buttons()
        
        def update_buttons(self):
            """Update button states based on current page"""
            features = self.cog.features_data.get("planned", [])
            features_per_page = 1
            total_pages = max(1, (len(features) + features_per_page - 1) // features_per_page)
            
            # Update button states
            self.previous_page.disabled = self.current_page <= 1
            self.next_page.disabled = self.current_page >= total_pages
            
            # Update button labels
            self.page_info.label = f"Page {self.current_page}/{total_pages}"
        
        @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary)
        async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.current_page > 1:
                self.current_page -= 1
                self.update_buttons()
                embed = self.cog.create_features_embed(self.current_page)
                await interaction.response.edit_message(embed=embed, view=self)
        
        @discord.ui.button(label="Page 1/1", style=discord.ButtonStyle.primary, disabled=True)
        async def page_info(self, interaction: discord.Interaction, button: discord.ui.Button):
            # This button is just for display
            await interaction.response.defer()
        
        @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
        async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            features = self.cog.features_data.get("planned", [])
            features_per_page = 1
            total_pages = max(1, (len(features) + features_per_page - 1) // features_per_page)
            
            if self.current_page < total_pages:
                self.current_page += 1
                self.update_buttons()
                embed = self.cog.create_features_embed(self.current_page)
                await interaction.response.edit_message(embed=embed, view=self)
        
        @discord.ui.button(label="➕ Add Feature", style=discord.ButtonStyle.green, row=1)
        async def add_feature(self, interaction: discord.Interaction, button: discord.ui.Button):
            # Check permissions
            if not self.cog.has_mod_permissions(interaction):
                await interaction.response.send_message(
                    "❌ **Permission Denied**\n\nYou need moderator permissions to add features.",
                    ephemeral=True
                )
                return
            
            # Show add feature modal
            modal = self.cog.AddFeatureModal(self.cog)
            await interaction.response.send_modal(modal)
        
        @discord.ui.button(label="✏️ Edit Feature", style=discord.ButtonStyle.blurple, row=1)
        async def edit_feature(self, interaction: discord.Interaction, button: discord.ui.Button):
            # Check permissions
            if not self.cog.has_mod_permissions(interaction):
                await interaction.response.send_message(
                    "❌ **Permission Denied**\n\nYou need moderator permissions to edit features.",
                    ephemeral=True
                )
                return
            
            features = self.cog.features_data.get("planned", [])
            if not features:
                await interaction.response.send_message(
                    "❌ **No Features to Edit**\n\nThere are no planned features to edit.",
                    ephemeral=True
                )
                return
            
            # Show edit feature selection
            view = self.cog.EditFeatureView(self.cog, self.current_page)
            await interaction.response.send_message(
                "✏️ **Edit Planned Feature**\n\nSelect a feature to edit:",
                view=view,
                ephemeral=True
            )

        @discord.ui.button(label="🗑️ Remove Feature", style=discord.ButtonStyle.red, row=1)
        async def remove_feature(self, interaction: discord.Interaction, button: discord.ui.Button):
            # Check permissions
            if not self.cog.has_mod_permissions(interaction):
                await interaction.response.send_message(
                    "❌ **Permission Denied**\n\nYou need moderator permissions to remove features.",
                    ephemeral=True
                )
                return
            
            features = self.cog.features_data.get("planned", [])
            if not features:
                await interaction.response.send_message(
                    "❌ **No Features to Remove**\n\nThere are no planned features to remove.",
                    ephemeral=True
                )
                return
            
            # Show remove feature selection
            view = self.cog.RemoveFeatureView(self.cog, self.current_page)
            await interaction.response.send_message(
                "🗑️ **Remove Planned Feature**\n\nSelect a feature to remove:",
                view=view,
                ephemeral=True
            )

    class AddFeatureModal(discord.ui.Modal):
        """Modal for adding a new planned feature"""
        
        def __init__(self, cog):
            super().__init__(title="Add Planned Feature")
            self.cog = cog
        
        name = discord.ui.TextInput(
            label="Feature Name",
            placeholder="Enter the name of the planned feature...",
            max_length=100,
            required=True
        )
        
        description = discord.ui.TextInput(
            label="Feature Description",
            placeholder="Describe what this planned feature will do...",
            style=discord.TextStyle.paragraph,
            required=True
        )
        
        async def on_submit(self, interaction: discord.Interaction):
            # Validate inputs
            if len(self.name.value.strip()) == 0:
                await interaction.response.send_message(
                    "❌ **Invalid Name**\n\nFeature name cannot be empty.",
                    ephemeral=True
                )
                return
            
            if len(self.description.value.strip()) == 0:
                await interaction.response.send_message(
                    "❌ **Invalid Description**\n\nFeature description cannot be empty.",
                    ephemeral=True
                )
                return
            
            # Create feature object
            feature = {
                "name": self.name.value.strip(),
                "description": self.description.value.strip(),
                "added_date": datetime.now().isoformat(),
                "added_by": str(interaction.user.id)
            }
            
            # Add to planned features list
            if "planned" not in self.cog.features_data:
                self.cog.features_data["planned"] = []
            
            self.cog.features_data["planned"].append(feature)
            
            # Save to file
            if self.cog.save_features():
                # Create success embed
                embed = discord.Embed(
                    title="✅ Planned Feature Added Successfully",
                    description="Added to **Planned Features**",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                
                embed.add_field(
                    name="Feature Name",
                    value=self.name.value,
                    inline=False
                )
                
                embed.add_field(
                    name="Description",
                    value=self.description.value,
                    inline=False
                )
                
                embed.add_field(
                    name="Added By",
                    value=interaction.user.mention,
                    inline=True
                )
                
                total_count = len(self.cog.features_data["planned"])
                embed.set_footer(text=f"Total planned features: {total_count}")
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                logger.info(f"User {interaction.user.id} ({interaction.user.display_name}) added planned feature: {self.name.value}")
            else:
                await interaction.response.send_message(
                    "❌ **Error Saving Feature**\n\nFailed to save the feature to the database. Please try again.",
                    ephemeral=True
                )
    
    class EditFeatureView(discord.ui.View):
        """View for selecting a planned feature to edit"""
        
        def __init__(self, cog, current_page: int = 1):
            super().__init__(timeout=300)
            self.cog = cog
            self.current_page = current_page
            self.add_feature_options()
        
        def add_feature_options(self):
            """Add select menu with feature options"""
            features = self.cog.features_data.get("planned", [])
            
            if not features:
                return
            
            # Create options for select menu (max 25 options)
            options = []
            for i, feature in enumerate(features[:25], 1):
                name = feature.get('name', 'Unknown Feature').strip()
                description = feature.get('description', 'No description').strip()
                
                # Ensure name is not empty
                if not name:
                    name = f"Feature {i}"
                
                # Calculate space for index prefix (e.g., "1. " = 3 chars for single digit, more for double digit)
                index_prefix = f"{i}. "
                max_name_length = 100 - len(index_prefix)
                
                # Truncate name to fit within label limit
                if len(name) > max_name_length:
                    name = name[:max_name_length-3] + "..."
                
                # Truncate description for select option (description field limit is 100)
                if len(description) > 100:
                    description = description[:97] + "..."
                
                # Ensure description is not empty
                if not description:
                    description = "No description available"
                
                label = f"{index_prefix}{name}"
                
                # Double check label length (should not happen but safety check)
                if len(label) > 100:
                    # Emergency fallback - use just the index
                    label = f"Feature {i}"
                
                options.append(discord.SelectOption(
                    label=label,
                    description=description,
                    value=str(i-1)  # Use 0-based index
                ))
            
            if options:
                select = discord.ui.Select(
                    placeholder="Choose a planned feature to edit...",
                    options=options,
                    custom_id="edit_feature_select"
                )
                select.callback = self.feature_selected
                self.add_item(select)
        
        async def feature_selected(self, interaction: discord.Interaction):
            """Handle feature selection for editing"""
            try:
                feature_index = int(interaction.data['values'][0])
                features = self.cog.features_data.get("planned", [])
                
                if feature_index < 0 or feature_index >= len(features):
                    await interaction.response.send_message(
                        "❌ **Invalid Selection**\n\nSelected feature no longer exists.",
                        ephemeral=True
                    )
                    return
                
                # Get the feature to edit
                feature = features[feature_index]
                
                # Show edit modal with current values
                modal = self.cog.EditFeatureModal(self.cog, feature_index, feature)
                await interaction.response.send_modal(modal)
                
            except Exception as e:
                logger.error(f"Error selecting feature for edit: {e}")
                await interaction.response.send_message(
                    "❌ **Error**\n\nAn error occurred while selecting the feature.",
                    ephemeral=True
                )
    
    class EditFeatureModal(discord.ui.Modal):
        """Modal for editing an existing planned feature"""
        
        def __init__(self, cog, feature_index: int, feature: dict):
            super().__init__(title="Edit Planned Feature")
            self.cog = cog
            self.feature_index = feature_index
            self.original_feature = feature.copy()
            
            # Create text inputs with current values
            self.name = discord.ui.TextInput(
                label="Feature Name",
                placeholder="Enter the name of the planned feature...",
                max_length=100,
                required=True,
                default=feature.get('name', '')
            )
            
            self.description = discord.ui.TextInput(
                label="Feature Description",
                placeholder="Describe what this planned feature will do...",
                style=discord.TextStyle.paragraph,
                required=True,
                default=feature.get('description', '')
            )
            
            # Add the text inputs to the modal
            self.add_item(self.name)
            self.add_item(self.description)
        
        async def on_submit(self, interaction: discord.Interaction):
            # Validate inputs
            if len(self.name.value.strip()) == 0:
                await interaction.response.send_message(
                    "❌ **Invalid Name**\n\nFeature name cannot be empty.",
                    ephemeral=True
                )
                return
            
            if len(self.description.value.strip()) == 0:
                await interaction.response.send_message(
                    "❌ **Invalid Description**\n\nFeature description cannot be empty.",
                    ephemeral=True
                )
                return
            
            # Update feature object
            features = self.cog.features_data.get("planned", [])
            if self.feature_index < 0 or self.feature_index >= len(features):
                await interaction.response.send_message(
                    "❌ **Feature Not Found**\n\nThe feature no longer exists.",
                    ephemeral=True
                )
                return
            
            # Update the feature
            features[self.feature_index].update({
                "name": self.name.value.strip(),
                "description": self.description.value.strip(),
                "last_edited": datetime.now().isoformat(),
                "last_edited_by": str(interaction.user.id)
            })
            
            # Save to file
            if self.cog.save_features():
                # Create success embed
                embed = discord.Embed(
                    title="✅ Planned Feature Updated Successfully",
                    description="Updated in **Planned Features**",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                
                embed.add_field(
                    name="Feature Name",
                    value=self.name.value,
                    inline=False
                )
                
                embed.add_field(
                    name="Description",
                    value=self.description.value,
                    inline=False
                )
                
                embed.add_field(
                    name="Edited By",
                    value=interaction.user.mention,
                    inline=True
                )
                
                total_count = len(self.cog.features_data["planned"])
                embed.set_footer(text=f"Total planned features: {total_count}")
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                logger.info(f"User {interaction.user.id} ({interaction.user.display_name}) edited planned feature: {self.name.value}")
            else:
                # Restore original feature if save failed
                features[self.feature_index] = self.original_feature
                await interaction.response.send_message(
                    "❌ **Error Saving Changes**\n\nFailed to save the updated feature. Please try again.",
                    ephemeral=True
                )
    
    class RemoveFeatureView(discord.ui.View):
        """View for selecting a planned feature to remove"""
        
        def __init__(self, cog, current_page: int = 1):
            super().__init__(timeout=300)
            self.cog = cog
            self.current_page = current_page
            self.add_feature_options()
        
        def add_feature_options(self):
            """Add select menu with feature options"""
            features = self.cog.features_data.get("planned", [])
            
            if not features:
                return
            
            # Create options for select menu (max 25 options)
            options = []
            for i, feature in enumerate(features[:25], 1):
                name = feature.get('name', 'Unknown Feature').strip()
                description = feature.get('description', 'No description').strip()
                
                # Ensure name is not empty
                if not name:
                    name = f"Feature {i}"
                
                # Calculate space for index prefix (e.g., "1. " = 3 chars for single digit, more for double digit)
                index_prefix = f"{i}. "
                max_name_length = 100 - len(index_prefix)
                
                # Truncate name to fit within label limit
                if len(name) > max_name_length:
                    name = name[:max_name_length-3] + "..."
                
                # Truncate description for select option (description field limit is 100)
                if len(description) > 100:
                    description = description[:97] + "..."
                
                # Ensure description is not empty
                if not description:
                    description = "No description available"
                
                label = f"{index_prefix}{name}"
                
                # Double check label length (should not happen but safety check)
                if len(label) > 100:
                    # Emergency fallback - use just the index
                    label = f"Feature {i}"
                
                options.append(discord.SelectOption(
                    label=label,
                    description=description,
                    value=str(i-1)  # Use 0-based index
                ))
            
            if options:
                select = discord.ui.Select(
                    placeholder="Choose a planned feature to remove...",
                    options=options,
                    custom_id="feature_select"
                )
                select.callback = self.feature_selected
                self.add_item(select)
        
        async def feature_selected(self, interaction: discord.Interaction):
            """Handle feature selection for removal"""
            try:
                feature_index = int(interaction.data['values'][0])
                features = self.cog.features_data.get("planned", [])
                
                if feature_index < 0 or feature_index >= len(features):
                    await interaction.response.send_message(
                        "❌ **Invalid Selection**\n\nSelected feature no longer exists.",
                        ephemeral=True
                    )
                    return
                
                # Remove the feature
                removed_feature = features.pop(feature_index)
                
                # Save to file
                if self.cog.save_features():
                    # Create success embed
                    embed = discord.Embed(
                        title="✅ Planned Feature Removed Successfully",
                        description="Removed from **Planned Features**",
                        color=discord.Color.red(),
                        timestamp=datetime.now()
                    )
                    
                    embed.add_field(
                        name="Removed Feature",
                        value=removed_feature.get('name', 'Unknown'),
                        inline=False
                    )
                    
                    embed.add_field(
                        name="Description",
                        value=removed_feature.get('description', 'No description'),
                        inline=False
                    )
                    
                    embed.add_field(
                        name="Removed By",
                        value=interaction.user.mention,
                        inline=True
                    )
                    
                    remaining_count = len(features)
                    embed.set_footer(text=f"Remaining planned features: {remaining_count}")
                    
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    logger.info(f"User {interaction.user.id} ({interaction.user.display_name}) removed planned feature: {removed_feature.get('name')}")
                else:
                    # Restore the feature if save failed
                    features.insert(feature_index, removed_feature)
                    await interaction.response.send_message(
                        "❌ **Error Removing Feature**\n\nFailed to save changes. Please try again.",
                        ephemeral=True
                    )
            
            except Exception as e:
                logger.error(f"Error removing planned feature: {e}")
                await interaction.response.send_message(
                    "❌ **Error**\n\nAn error occurred while removing the feature.",
                    ephemeral=True
                )

    @app_commands.command(name="planned-features", description="View and manage planned features")
    @app_commands.describe(page="Page number to display")
    async def planned_features(self, interaction: discord.Interaction, page: int = 1):
        """Display the planned features list with pagination"""
        
        # Validate page number
        if page < 1:
            page = 1
        
        # Create embed and view
        embed = self.create_features_embed(page)
        view = self.FeatureView(self, page)
        
        await interaction.response.send_message(embed=embed, view=view)
        logger.info(f"User {interaction.user.id} ({interaction.user.display_name}) viewed planned features page {page}")

    @app_commands.command(name="planned-updates-upload", description="Upload planned features from a txt file")
    @app_commands.describe(file="Text file containing planned features (one per line or separated by blank lines)")
    async def planned_updates_upload(self, interaction: discord.Interaction, file: discord.Attachment):
        """Upload planned features from a text file"""
        
        # Check permissions
        if not self.has_mod_permissions(interaction):
            await interaction.response.send_message(
                "❌ **Permission Denied**\n\nYou need moderator permissions to upload planned features.",
                ephemeral=True
            )
            return
        
        # Validate file type
        if not file.filename.lower().endswith('.txt'):
            await interaction.response.send_message(
                "❌ **Invalid File Type**\n\nPlease upload a .txt file.",
                ephemeral=True
            )
            return
        
        # Check file size (Discord limit is 25MB, but we'll be more conservative)
        if file.size > 10 * 1024 * 1024:  # 10MB limit
            await interaction.response.send_message(
                "❌ **File Too Large**\n\nFile must be smaller than 10MB.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Read file content
            file_content = await file.read()
            text_content = file_content.decode('utf-8')
            
            # Parse features from text
            features_added = []
            
            # Split by double newlines first (for paragraph-separated features)
            sections = text_content.split('\n\n')
            
            for section in sections:
                section = section.strip()
                if not section:
                    continue
                
                lines = section.split('\n')
                if len(lines) >= 2:
                    # First line is name, rest is description
                    name = lines[0].strip()
                    description = '\n'.join(lines[1:]).strip()
                elif len(lines) == 1:
                    # Single line - treat as name with empty description
                    name = lines[0].strip()
                    description = "No description provided"
                else:
                    continue
                
                # Skip empty names
                if not name:
                    continue
                
                # Create feature object
                feature = {
                    "name": name,
                    "description": description,
                    "added_date": datetime.now().isoformat(),
                    "added_by": str(interaction.user.id),
                    "uploaded_from_file": file.filename
                }
                
                features_added.append(feature)
            
            # If no features found with double newlines, try single line parsing
            if not features_added:
                lines = text_content.split('\n')
                for line in lines:
                    line = line.strip()
                    if line:
                        feature = {
                            "name": line,
                            "description": "No description provided",
                            "added_date": datetime.now().isoformat(),
                            "added_by": str(interaction.user.id),
                            "uploaded_from_file": file.filename
                        }
                        features_added.append(feature)
            
            if not features_added:
                await interaction.followup.send(
                    "❌ **No Features Found**\n\nNo valid features were found in the uploaded file.",
                    ephemeral=True
                )
                return
            
            # Add features to the list
            if "planned" not in self.features_data:
                self.features_data["planned"] = []
            
            self.features_data["planned"].extend(features_added)
            
            # Save to file
            if self.save_features():
                # Create success embed
                embed = discord.Embed(
                    title="✅ Planned Features Uploaded Successfully",
                    description=f"Added **{len(features_added)}** features from `{file.filename}`",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                
                # Show first few features as preview
                preview_features = features_added[:3]
                for i, feature in enumerate(preview_features, 1):
                    embed.add_field(
                        name=f"{i}. {feature['name']}",
                        value=feature['description'][:100] + ("..." if len(feature['description']) > 100 else ""),
                        inline=False
                    )
                
                if len(features_added) > 3:
                    embed.add_field(
                        name="And more...",
                        value=f"Plus {len(features_added) - 3} additional features",
                        inline=False
                    )
                
                embed.add_field(
                    name="Uploaded By",
                    value=interaction.user.mention,
                    inline=True
                )
                
                embed.add_field(
                    name="File",
                    value=file.filename,
                    inline=True
                )
                
                total_count = len(self.features_data["planned"])
                embed.set_footer(text=f"Total planned features: {total_count}")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.info(f"User {interaction.user.id} ({interaction.user.display_name}) uploaded {len(features_added)} planned features from {file.filename}")
            else:
                # Remove added features if save failed
                for _ in range(len(features_added)):
                    self.features_data["planned"].pop()
                
                await interaction.followup.send(
                    "❌ **Error Saving Features**\n\nFailed to save the features to the database. Please try again.",
                    ephemeral=True
                )
        
        except UnicodeDecodeError:
            await interaction.followup.send(
                "❌ **File Encoding Error**\n\nPlease ensure the file is saved as UTF-8 text.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error uploading planned features: {e}")
            await interaction.followup.send(
                "❌ **Upload Error**\n\nAn error occurred while processing the file. Please check the file format and try again.",
                ephemeral=True
            )

    @app_commands.command(name="planned-updates-upload", description="Upload planned features from a txt file")
    @app_commands.describe(file="Text file containing planned features (one per line or separated by blank lines)")
    async def planned_updates_upload(self, interaction: discord.Interaction, file: discord.Attachment):
        """Upload planned features from a text file"""
        
        # Check permissions
        if not self.has_mod_permissions(interaction):
            await interaction.response.send_message(
                "❌ **Permission Denied**\n\nYou need moderator permissions to upload planned features.",
                ephemeral=True
            )
            return
        
        # Validate file type
        if not file.filename.lower().endswith('.txt'):
            await interaction.response.send_message(
                "❌ **Invalid File Type**\n\nPlease upload a .txt file.",
                ephemeral=True
            )
            return
        
        # Check file size (Discord limit is 25MB, but we'll be more conservative)
        if file.size > 10 * 1024 * 1024:  # 10MB limit
            await interaction.response.send_message(
                "❌ **File Too Large**\n\nFile must be smaller than 10MB.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Read file content
            file_content = await file.read()
            text_content = file_content.decode('utf-8')
            
            # Parse features from text
            features_added = []
            
            # Split by double newlines first (for paragraph-separated features)
            sections = text_content.split('\n\n')
            
            for section in sections:
                section = section.strip()
                if not section:
                    continue
                
                lines = section.split('\n')
                if len(lines) >= 2:
                    # First line is name, rest is description
                    name = lines[0].strip()
                    description = '\n'.join(lines[1:]).strip()
                elif len(lines) == 1:
                    # Single line - treat as name with empty description
                    name = lines[0].strip()
                    description = "No description provided"
                else:
                    continue
                
                # Skip empty names
                if not name:
                    continue
                
                # Create feature object
                feature = {
                    "name": name,
                    "description": description,
                    "added_date": datetime.now().isoformat(),
                    "added_by": str(interaction.user.id),
                    "uploaded_from_file": file.filename
                }
                
                features_added.append(feature)
            
            # If no features found with double newlines, try single line parsing
            if not features_added:
                lines = text_content.split('\n')
                for line in lines:
                    line = line.strip()
                    if line:
                        feature = {
                            "name": line,
                            "description": "No description provided",
                            "added_date": datetime.now().isoformat(),
                            "added_by": str(interaction.user.id),
                            "uploaded_from_file": file.filename
                        }
                        features_added.append(feature)
            
            if not features_added:
                await interaction.followup.send(
                    "❌ **No Features Found**\n\nNo valid features were found in the uploaded file.",
                    ephemeral=True
                )
                return
            
            # Add features to the list
            if "planned" not in self.features_data:
                self.features_data["planned"] = []
            
            self.features_data["planned"].extend(features_added)
            
            # Save to file
            if self.save_features():
                # Create success embed
                embed = discord.Embed(
                    title="✅ Planned Features Uploaded Successfully",
                    description=f"Added **{len(features_added)}** features from `{file.filename}`",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                
                # Show first few features as preview
                preview_features = features_added[:3]
                for i, feature in enumerate(preview_features, 1):
                    embed.add_field(
                        name=f"{i}. {feature['name']}",
                        value=feature['description'][:100] + ("..." if len(feature['description']) > 100 else ""),
                        inline=False
                    )
                
                if len(features_added) > 3:
                    embed.add_field(
                        name="And more...",
                        value=f"Plus {len(features_added) - 3} additional features",
                        inline=False
                    )
                
                embed.add_field(
                    name="Uploaded By",
                    value=interaction.user.mention,
                    inline=True
                )
                
                embed.add_field(
                    name="File",
                    value=file.filename,
                    inline=True
                )
                
                total_count = len(self.features_data["planned"])
                embed.set_footer(text=f"Total planned features: {total_count}")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.info(f"User {interaction.user.id} ({interaction.user.display_name}) uploaded {len(features_added)} planned features from {file.filename}")
            else:
                # Remove added features if save failed
                for _ in range(len(features_added)):
                    self.features_data["planned"].pop()
                
                await interaction.followup.send(
                    "❌ **Error Saving Features**\n\nFailed to save the features to the database. Please try again.",
                    ephemeral=True
                )
        
        except UnicodeDecodeError:
            await interaction.followup.send(
                "❌ **File Encoding Error**\n\nPlease ensure the file is saved as UTF-8 text.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error uploading planned features: {e}")
            await interaction.followup.send(
                "❌ **Upload Error**\n\nAn error occurred while processing the file. Please check the file format and try again.",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(PlannedFeatures(bot))
    logger.info("PlannedFeatures cog loaded successfully")