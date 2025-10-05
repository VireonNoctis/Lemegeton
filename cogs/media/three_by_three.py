import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import logging
from typing import Optional, List, Dict, Tuple
import io
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
import database

# Image processing
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Setup logging
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "three_by_three.log"

logger = logging.getLogger("ThreeByThree")
logger.setLevel(logging.INFO)

if not logger.handlers:
    try:
        file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Failed to setup file logging for 3x3 generator: {e}")

# AniList API
API_URL = "https://graphql.anilist.co"

# Cache and data directories
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
COVER_CACHE_DIR = DATA_DIR / "cover_cache"
COVER_CACHE_DIR.mkdir(exist_ok=True)
CACHE_INDEX_FILE = DATA_DIR / "cover_cache_index.json"
PRESETS_FILE = DATA_DIR / "3x3_presets.json"

# Cache TTL: 30 days
CACHE_TTL_DAYS = 30

# Built-in templates
TEMPLATES = {
    "action": {
        "name": "Action Anime",
        "genre": "Action",
        "media_type": "anime",
        "description": "Top action-packed anime"
    },
    "romance": {
        "name": "Romance Anime",
        "genre": "Romance",
        "media_type": "anime",
        "description": "Best romance anime"
    },
    "shounen": {
        "name": "Shounen Classics",
        "genre": "Shounen",
        "media_type": "manga",
        "description": "Classic shounen manga"
    },
    "80s": {
        "name": "80s Classics",
        "decade": 1980,
        "media_type": "anime",
        "description": "Best anime from the 1980s"
    },
    "90s": {
        "name": "90s Classics",
        "decade": 1990,
        "media_type": "anime",
        "description": "Best anime from the 1990s"
    },
    "2000s": {
        "name": "2000s Classics",
        "decade": 2000,
        "media_type": "anime",
        "description": "Best anime from the 2000s"
    },
    "2010s": {
        "name": "2010s Hits",
        "decade": 2010,
        "media_type": "anime",
        "description": "Popular anime from the 2010s"
    },
    "thriller": {
        "name": "Psychological Thrillers",
        "genre": "Thriller",
        "media_type": "anime",
        "description": "Mind-bending psychological anime"
    },
    "comedy": {
        "name": "Comedy Gold",
        "genre": "Comedy",
        "media_type": "anime",
        "description": "Funniest anime series"
    },
    "fantasy": {
        "name": "Fantasy Worlds",
        "genre": "Fantasy",
        "media_type": "anime",
        "description": "Epic fantasy anime"
    }
}


class CoverCache:
    """Manage cover image caching"""
    
    def __init__(self):
        self.index = self._load_index()
    
    def _load_index(self) -> Dict:
        """Load cache index from disk"""
        if CACHE_INDEX_FILE.exists():
            try:
                with open(CACHE_INDEX_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading cache index: {e}")
        return {}
    
    def _save_index(self):
        """Save cache index to disk"""
        try:
            with open(CACHE_INDEX_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.index, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving cache index: {e}")
    
    def _get_cache_key(self, title: str, media_type: str) -> str:
        """Generate cache key from title and media type"""
        key_str = f"{title.lower()}_{media_type.lower()}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, title: str, media_type: str) -> Optional[Dict]:
        """Get cached cover data"""
        key = self._get_cache_key(title, media_type)
        
        if key in self.index:
            entry = self.index[key]
            cache_time = datetime.fromisoformat(entry["cached_at"])
            
            # Check if cache is expired
            if datetime.utcnow() - cache_time > timedelta(days=CACHE_TTL_DAYS):
                logger.debug(f"Cache expired for {title}")
                return None
            
            # Load cover bytes from file
            cache_file = COVER_CACHE_DIR / f"{key}.png"
            if cache_file.exists():
                try:
                    with open(cache_file, 'rb') as f:
                        cover_bytes = f.read()
                    
                    logger.info(f"Cache HIT for {title}")
                    return {
                        "title": entry["title"],
                        "cover_url": entry["cover_url"],
                        "cover_bytes": cover_bytes
                    }
                except Exception as e:
                    logger.error(f"Error reading cached cover: {e}")
        
        logger.debug(f"Cache MISS for {title}")
        return None
    
    def set(self, title: str, media_type: str, data: Dict):
        """Cache cover data"""
        key = self._get_cache_key(title, media_type)
        
        try:
            # Save cover bytes to file
            cache_file = COVER_CACHE_DIR / f"{key}.png"
            with open(cache_file, 'wb') as f:
                f.write(data["cover_bytes"])
            
            # Update index
            self.index[key] = {
                "title": data["title"],
                "cover_url": data["cover_url"],
                "cached_at": datetime.utcnow().isoformat(),
                "search_title": title.lower()
            }
            self._save_index()
            
            logger.info(f"Cached cover for {title}")
        except Exception as e:
            logger.error(f"Error caching cover: {e}")
    
    def cleanup_old_cache(self):
        """Remove expired cache entries"""
        expired_keys = []
        cutoff_date = datetime.utcnow() - timedelta(days=CACHE_TTL_DAYS)
        
        for key, entry in self.index.items():
            cache_time = datetime.fromisoformat(entry["cached_at"])
            if cache_time < cutoff_date:
                expired_keys.append(key)
        
        for key in expired_keys:
            cache_file = COVER_CACHE_DIR / f"{key}.png"
            if cache_file.exists():
                cache_file.unlink()
            del self.index[key]
        
        if expired_keys:
            self._save_index()
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")


class PresetManager:
    """Manage user 3x3 presets"""
    
    def __init__(self):
        self.presets = self._load_presets()
    
    def _load_presets(self) -> Dict:
        """Load presets from disk"""
        if PRESETS_FILE.exists():
            try:
                with open(PRESETS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading presets: {e}")
        return {}
    
    def _save_presets(self):
        """Save presets to disk"""
        try:
            with open(PRESETS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.presets, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving presets: {e}")
    
    def save_preset(self, user_id: int, preset_name: str, titles: List[str], media_type: str):
        """Save a user preset"""
        user_key = str(user_id)
        
        if user_key not in self.presets:
            self.presets[user_key] = {}
        
        self.presets[user_key][preset_name] = {
            "titles": titles,
            "media_type": media_type,
            "created_at": datetime.utcnow().isoformat()
        }
        
        self._save_presets()
        logger.info(f"Saved preset '{preset_name}' for user {user_id}")
    
    def get_preset(self, user_id: int, preset_name: str) -> Optional[Dict]:
        """Get a user preset"""
        user_key = str(user_id)
        
        if user_key in self.presets and preset_name in self.presets[user_key]:
            return self.presets[user_key][preset_name]
        
        return None
    
    def list_presets(self, user_id: int) -> List[str]:
        """List all presets for a user"""
        user_key = str(user_id)
        
        if user_key in self.presets:
            return list(self.presets[user_key].keys())
        
        return []
    
    def delete_preset(self, user_id: int, preset_name: str) -> bool:
        """Delete a user preset"""
        user_key = str(user_id)
        
        if user_key in self.presets and preset_name in self.presets[user_key]:
            del self.presets[user_key][preset_name]
            self._save_presets()
            logger.info(f"Deleted preset '{preset_name}' for user {user_id}")
            return True
        
        return False


class ThreeByThreeModal(discord.ui.Modal):
    """Modal for collecting 9 anime/manga titles"""
    
    def __init__(self, media_type: str, cog, preset_name: Optional[str] = None):
        super().__init__(title=f"Create Your 3x3 {media_type.title()} Grid")
        self.media_type = media_type
        self.cog = cog
        self.preset_name = preset_name
        
        # Create 9 input fields (3 rows)
        self.title1 = discord.ui.TextInput(
            label="Row 1 - Title 1",
            placeholder="Enter anime/manga title",
            required=True,
            max_length=100
        )
        self.title2 = discord.ui.TextInput(
            label="Row 1 - Title 2",
            placeholder="Enter anime/manga title",
            required=True,
            max_length=100
        )
        self.title3 = discord.ui.TextInput(
            label="Row 1 - Title 3",
            placeholder="Enter anime/manga title",
            required=True,
            max_length=100
        )
        self.title4 = discord.ui.TextInput(
            label="Row 2 - Title 1",
            placeholder="Enter anime/manga title",
            required=True,
            max_length=100
        )
        self.title5 = discord.ui.TextInput(
            label="Row 2 - Title 2",
            placeholder="Enter anime/manga title",
            required=True,
            max_length=100
        )
        
        # Add all fields
        self.add_item(self.title1)
        self.add_item(self.title2)
        self.add_item(self.title3)
        self.add_item(self.title4)
        self.add_item(self.title5)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission - collect first 5 titles"""
        await interaction.response.defer(ephemeral=True)
        
        # Store first 5 titles
        titles = [
            self.title1.value.strip(),
            self.title2.value.strip(),
            self.title3.value.strip(),
            self.title4.value.strip(),
            self.title5.value.strip()
        ]
        
        # Show second modal for remaining 4 titles
        second_modal = ThreeByThreeModalPart2(self.media_type, titles, self.cog, self.preset_name)
        await interaction.followup.send("Please enter the remaining 4 titles:", ephemeral=True)
        await interaction.followup.send("", view=ContinueView(second_modal), ephemeral=True)


class ThreeByThreeModalPart2(discord.ui.Modal):
    """Second modal for collecting remaining 4 titles"""
    
    def __init__(self, media_type: str, previous_titles: List[str], cog, preset_name: Optional[str] = None):
        super().__init__(title=f"3x3 Grid - Remaining Titles")
        self.media_type = media_type
        self.previous_titles = previous_titles
        self.cog = cog
        self.preset_name = preset_name
        
        # Remaining 4 fields
        self.title6 = discord.ui.TextInput(
            label="Row 2 - Title 3",
            placeholder="Enter anime/manga title",
            required=True,
            max_length=100
        )
        self.title7 = discord.ui.TextInput(
            label="Row 3 - Title 1",
            placeholder="Enter anime/manga title",
            required=True,
            max_length=100
        )
        self.title8 = discord.ui.TextInput(
            label="Row 3 - Title 2",
            placeholder="Enter anime/manga title",
            required=True,
            max_length=100
        )
        self.title9 = discord.ui.TextInput(
            label="Row 3 - Title 3",
            placeholder="Enter anime/manga title",
            required=True,
            max_length=100
        )
        
        self.add_item(self.title6)
        self.add_item(self.title7)
        self.add_item(self.title8)
        self.add_item(self.title9)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle second modal submission and generate 3x3"""
        await interaction.response.defer(ephemeral=False)
        
        # Combine all 9 titles
        all_titles = self.previous_titles + [
            self.title6.value.strip(),
            self.title7.value.strip(),
            self.title8.value.strip(),
            self.title9.value.strip()
        ]
        
        logger.info(f"Generating 3x3 for {interaction.user.name}: {all_titles}")
        
        # Save as preset if name provided
        if self.preset_name:
            self.cog.preset_manager.save_preset(
                interaction.user.id,
                self.preset_name,
                all_titles,
                self.media_type
            )
        
        # Generate the 3x3 grid
        try:
            image_bytes = await self.cog.generate_3x3(all_titles, self.media_type, interaction.user)
            
            if image_bytes:
                file = discord.File(fp=image_bytes, filename=f"3x3_{self.media_type}.png")
                
                embed = discord.Embed(
                    title=f"🎨 {interaction.user.display_name}'s 3x3 {self.media_type.title()} Grid",
                    description=f"Your favorite {self.media_type}!",
                    color=discord.Color.purple()
                )
                embed.set_image(url=f"attachment://3x3_{self.media_type}.png")
                embed.set_footer(text="Generated from AniList covers")
                
                await interaction.followup.send(embed=embed, file=file)
                
                logger.info(f"Successfully generated 3x3 for {interaction.user.name}")
            else:
                await interaction.followup.send(
                    "❌ Failed to generate 3x3 grid. Please check your titles and try again.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error generating 3x3: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ An error occurred while generating your 3x3. Please try again.",
                ephemeral=True
            )


class ContinueView(discord.ui.View):
    """View with a button to show the second modal"""
    
    def __init__(self, modal: discord.ui.Modal):
        super().__init__(timeout=300)
        self.modal = modal
    
    @discord.ui.button(label="Continue →", style=discord.ButtonStyle.primary)
    async def continue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(self.modal)


class ThreeByThree(commands.Cog):
    """Generate 3x3 image grids of anime/manga covers with advanced features"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cover_cache = CoverCache()
        self.preset_manager = PresetManager()
        logger.info("Enhanced 3x3 Generator cog initialized with caching and presets")
        
        if not PIL_AVAILABLE:
            logger.warning("PIL/Pillow not available - 3x3 generation will not work!")
    
    async def fetch_media_cover(self, session: aiohttp.ClientSession, title: str, media_type: str) -> Optional[Dict]:
        """
        Fetch media information and cover image from AniList (with caching)
        
        Args:
            session: aiohttp session
            title: Title to search for
            media_type: 'anime' or 'manga'
            
        Returns:
            Dict with 'title', 'cover_url', 'cover_bytes' or None
        """
        # Check cache first
        cached_data = self.cover_cache.get(title, media_type)
        if cached_data:
            return cached_data
        
        query = """
        query ($search: String, $type: MediaType) {
            Media(search: $search, type: $type) {
                id
                title {
                    romaji
                    english
                }
                coverImage {
                    extraLarge
                    large
                }
            }
        }
        """
        
        variables = {
            "search": title,
            "type": media_type.upper()
        }
        
        try:
            async with session.post(
                API_URL,
                json={"query": query, "variables": variables},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    media = data.get("data", {}).get("Media")
                    
                    if media:
                        cover_url = media["coverImage"].get("extraLarge") or media["coverImage"].get("large")
                        title_obj = media["title"]
                        display_title = title_obj.get("english") or title_obj.get("romaji") or title
                        
                        # Download cover image
                        if cover_url:
                            async with session.get(cover_url, timeout=aiohttp.ClientTimeout(total=30)) as img_response:
                                if img_response.status == 200:
                                    cover_bytes = await img_response.read()
                                    
                                    result = {
                                        "title": display_title,
                                        "cover_url": cover_url,
                                        "cover_bytes": cover_bytes
                                    }
                                    
                                    # Cache the result
                                    self.cover_cache.set(title, media_type, result)
                                    
                                    return result
                
                logger.warning(f"Failed to fetch cover for '{title}': HTTP {response.status}")
                return None
                
        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching cover for '{title}'")
            return None
        except Exception as e:
            logger.error(f"Error fetching cover for '{title}': {e}")
            return None
    
    async def fetch_template_titles(self, template_key: str) -> List[str]:
        """Fetch titles for a template using AniList API"""
        template = TEMPLATES.get(template_key)
        if not template:
            return []
        
        query = """
        query ($genre: String, $startYear: Int, $endYear: Int, $type: MediaType) {
            Page(page: 1, perPage: 9) {
                media(
                    genre: $genre,
                    startDate_greater: $startYear,
                    startDate_lesser: $endYear,
                    type: $type,
                    sort: POPULARITY_DESC
                ) {
                    title {
                        romaji
                        english
                    }
                }
            }
        }
        """
        
        variables = {
            "type": template["media_type"].upper(),
            "genre": template.get("genre"),
        }
        
        if "decade" in template:
            variables["startYear"] = template["decade"] * 10000 + 101  # Jan 1, decade
            variables["endYear"] = (template["decade"] + 10) * 10000 + 1231  # Dec 31, decade+9
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    API_URL,
                    json={"query": query, "variables": variables},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        media_list = data.get("data", {}).get("Page", {}).get("media", [])
                        
                        titles = []
                        for media in media_list[:9]:
                            title = media["title"].get("english") or media["title"].get("romaji")
                            if title:
                                titles.append(title)
                        
                        return titles
        except Exception as e:
            logger.error(f"Error fetching template titles: {e}")
        
        return []
    
    async def generate_3x3(self, titles: List[str], media_type: str, user: discord.User) -> Optional[io.BytesIO]:
        """
        Generate a 3x3 grid image from 9 anime/manga titles
        
        Args:
            titles: List of 9 titles
            media_type: 'anime' or 'manga'
            user: Discord user who requested the grid
            
        Returns:
            BytesIO containing PNG image or None
        """
        if not PIL_AVAILABLE:
            logger.error("PIL not available for 3x3 generation")
            return None
        
        if len(titles) != 9:
            logger.error(f"Expected 9 titles, got {len(titles)}")
            return None
        
        # Fetch all covers (with caching)
        async with aiohttp.ClientSession() as session:
            media_data = []
            
            for title in titles:
                data = await self.fetch_media_cover(session, title, media_type)
                media_data.append(data)
        
        # Check if we got at least some covers
        valid_covers = [m for m in media_data if m is not None]
        if len(valid_covers) < 5:
            logger.warning(f"Only found {len(valid_covers)} valid covers out of 9")
            return None
        
        # Generate image
        try:
            # Image settings - using 2:3 aspect ratio (manga/anime cover proportions)
            cover_width = 200   # Width of each cover
            cover_height = 300  # Height of each cover (2:3 ratio)
            grid_size = 3
            padding = 10
            
            # Calculate total image size
            total_width = (cover_width * grid_size) + (padding * (grid_size + 1))
            total_height = (cover_height * grid_size) + (padding * (grid_size + 1))
            
            # Create base image with portrait-friendly dimensions
            image = Image.new("RGB", (total_width, total_height), (20, 20, 20))
            
            # Place covers in grid
            for idx, data in enumerate(media_data):
                row = idx // grid_size
                col = idx % grid_size
                
                x = padding + (col * (cover_width + padding))
                y = padding + (row * (cover_height + padding))
                
                if data and data.get("cover_bytes"):
                    try:
                        # Load and resize cover
                        cover_img = Image.open(io.BytesIO(data["cover_bytes"]))
                        cover_img = cover_img.convert("RGB")
                        cover_img = cover_img.resize((cover_width, cover_height), Image.Resampling.LANCZOS)
                        
                        # Paste into grid
                        image.paste(cover_img, (x, y))
                    except Exception as e:
                        logger.error(f"Error processing cover {idx}: {e}")
                        # Draw placeholder
                        draw = ImageDraw.Draw(image)
                        draw.rectangle([x, y, x + cover_width, y + cover_height], fill=(60, 60, 60))
                        
                        # Draw "Not Found" text
                        try:
                            font = ImageFont.truetype("arial.ttf", 20)
                        except:
                            font = ImageFont.load_default()
                        
                        text = "Not Found"
                        bbox = draw.textbbox((0, 0), text, font=font)
                        text_width = bbox[2] - bbox[0]
                        text_height = bbox[3] - bbox[1]
                        text_x = x + (cover_width - text_width) // 2
                        text_y = y + (cover_height - text_height) // 2
                        draw.text((text_x, text_y), text, fill=(150, 150, 150), font=font)
                else:
                    # Draw placeholder for missing cover
                    draw = ImageDraw.Draw(image)
                    draw.rectangle([x, y, x + cover_width, y + cover_height], fill=(60, 60, 60))
                    
                    # Draw title text if available
                    title_text = titles[idx][:30] if idx < len(titles) else "Unknown"
                    try:
                        font = ImageFont.truetype("arial.ttf", 16)
                    except:
                        font = ImageFont.load_default()
                    
                    # Multi-line text for long titles
                    words = title_text.split()
                    lines = []
                    current_line = []
                    
                    for word in words:
                        test_line = ' '.join(current_line + [word])
                        bbox = draw.textbbox((0, 0), test_line, font=font)
                        if bbox[2] - bbox[0] < cover_width - 20:
                            current_line.append(word)
                        else:
                            if current_line:
                                lines.append(' '.join(current_line))
                            current_line = [word]
                    
                    if current_line:
                        lines.append(' '.join(current_line))
                    
                    # Draw lines
                    text_y_start = y + (cover_height // 2) - (len(lines) * 10)
                    for i, line in enumerate(lines[:3]):  # Max 3 lines
                        bbox = draw.textbbox((0, 0), line, font=font)
                        text_width = bbox[2] - bbox[0]
                        text_x = x + (cover_width - text_width) // 2
                        text_y = text_y_start + (i * 22)
                        draw.text((text_x, text_y), line, fill=(180, 180, 180), font=font)
            
            # Save to BytesIO
            output = io.BytesIO()
            image.save(output, format="PNG", optimize=True)
            output.seek(0)
            
            logger.info(f"Successfully generated 3x3 grid for {user.name}")
            return output
            
        except Exception as e:
            logger.error(f"Error generating 3x3 image: {e}", exc_info=True)
            return None
    
    @app_commands.command(name="3x3", description="🎨 Create a 3x3 grid of your favorite anime or manga covers")
    @app_commands.describe(media_type="Choose anime or manga")
    @app_commands.choices(media_type=[
        app_commands.Choice(name="Anime", value="anime"),
        app_commands.Choice(name="Manga", value="manga")
    ])
    async def three_by_three(self, interaction: discord.Interaction, media_type: app_commands.Choice[str]):
        """Create a 3x3 grid of anime/manga covers"""
        
        if not PIL_AVAILABLE:
            await interaction.response.send_message(
                "❌ Image generation is not available. Please contact the bot administrator.",
                ephemeral=True
            )
            return
        
        logger.info(f"{interaction.user.name} started 3x3 creation for {media_type.value}")
        
        # Show modal to collect titles
        modal = ThreeByThreeModal(media_type.value, self)
        await interaction.response.send_modal(modal)
    
    @app_commands.command(name="3x3-preset", description="💾 Create a 3x3 from a saved preset or save current as preset")
    @app_commands.describe(
        action="Choose to load or save a preset",
        preset_name="Name of the preset"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Load Preset", value="load"),
        app_commands.Choice(name="Save New Preset", value="save"),
        app_commands.Choice(name="List My Presets", value="list"),
        app_commands.Choice(name="Delete Preset", value="delete")
    ])
    async def three_by_three_preset(self, interaction: discord.Interaction, 
                                    action: app_commands.Choice[str],
                                    preset_name: Optional[str] = None):
        """Manage 3x3 presets"""
        
        if action.value == "list":
            presets = self.preset_manager.list_presets(interaction.user.id)
            
            if not presets:
                await interaction.response.send_message(
                    "📭 You don't have any saved presets yet.\n"
                    "Use `/3x3-preset save <name>` to save your next 3x3!",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title="💾 Your 3x3 Presets",
                description="\n".join([f"• `{p}`" for p in presets]),
                color=discord.Color.blue()
            )
            embed.set_footer(text="Use /3x3-preset load <name> to load a preset")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if not preset_name:
            await interaction.response.send_message(
                "❌ Please provide a preset name!",
                ephemeral=True
            )
            return
        
        if action.value == "load":
            preset = self.preset_manager.get_preset(interaction.user.id, preset_name)
            
            if not preset:
                await interaction.response.send_message(
                    f"❌ Preset '{preset_name}' not found!\n"
                    f"Use `/3x3-preset list` to see your presets.",
                    ephemeral=True
                )
                return
            
            # Generate 3x3 from preset
            await interaction.response.defer(ephemeral=False)
            
            image_bytes = await self.generate_3x3(
                preset["titles"],
                preset["media_type"],
                interaction.user
            )
            
            if image_bytes:
                file = discord.File(fp=image_bytes, filename=f"3x3_{preset['media_type']}.png")
                
                embed = discord.Embed(
                    title=f"💾 {interaction.user.display_name}'s Preset: {preset_name}",
                    description=f"Media Type: {preset['media_type'].title()}",
                    color=discord.Color.green()
                )
                embed.set_image(url=f"attachment://3x3_{preset['media_type']}.png")
                embed.set_footer(text=f"Loaded from preset • Created {preset['created_at'][:10]}")
                
                await interaction.followup.send(embed=embed, file=file)
            else:
                await interaction.followup.send(
                    "❌ Failed to generate 3x3 from preset.",
                    ephemeral=True
                )
        
        elif action.value == "save":
            # Show modal to collect titles for saving
            await interaction.response.send_message(
                f"💾 Creating preset '{preset_name}'...\n"
                f"Please fill out the following forms to save your preset.",
                ephemeral=True
            )
            
            # Ask for media type first
            await interaction.followup.send(
                "What media type for this preset? (Use `/3x3 anime` or `/3x3 manga` and it will be saved)",
                ephemeral=True
            )
        
        elif action.value == "delete":
            success = self.preset_manager.delete_preset(interaction.user.id, preset_name)
            
            if success:
                await interaction.response.send_message(
                    f"✅ Preset '{preset_name}' deleted successfully!",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ Preset '{preset_name}' not found!",
                    ephemeral=True
                )
    
    @app_commands.command(name="3x3-cache", description="🗑️ Clear cover cache (Admin only)")
    async def three_by_three_cache(self, interaction: discord.Interaction):
        """Clear the cover cache"""
        
        # Check if user is admin
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ This command requires Administrator permissions.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Clean up old cache
        self.cover_cache.cleanup_old_cache()
        
        # Get cache stats
        cache_size = len(self.cover_cache.index)
        
        embed = discord.Embed(
            title="🗑️ Cache Management",
            description=f"Cache cleaned successfully!\n\n"
                       f"**Current cache size:** {cache_size} covers",
            color=discord.Color.green()
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def cog_load(self):
        """Called when the cog is loaded"""
        logger.info("Enhanced 3x3 Generator cog loaded successfully")
        # Clean up old cache on startup
        self.cover_cache.cleanup_old_cache()
    
    async def cog_unload(self):
        """Called when the cog is unloaded"""
        logger.info("Enhanced 3x3 Generator cog unloaded")


async def setup(bot: commands.Bot):
    """Setup function for the cog"""
    await bot.add_cog(ThreeByThree(bot))
