# 🌐 MAKING YOUR BOT PUBLIC: MULTI-GUILD DATABASE ARCHITECTURE

## 📊 CURRENT SITUATION ANALYSIS

Your bot is currently **25% ready** for multi-guild deployment. Here's what needs to change:

### ✅ Already Guild-Aware (5 tables):
- `invites`, `invite_uses`, `recruitment_stats`, `user_leaves`, `invite_tracker_settings`

### ❌ Need Guild-Awareness (15 tables):
- All user data, challenges, achievements, stats, etc.

## 🔧 REQUIRED CHANGES FOR PUBLIC BOT

### 1. DATABASE ARCHITECTURE OVERHAUL

#### A) Add Guild Context to All User Tables

**Current Problem:**
```sql
-- Current: One user across all servers
users (discord_id INTEGER PRIMARY KEY, username TEXT, ...)
```

**Solution:**
```sql
-- New: User per server relationship
users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    anilist_username TEXT,
    anilist_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(discord_id, guild_id)  -- One user record per server
)
```

#### B) Migrate Critical Tables

**Tables requiring guild_id addition:**
1. `users` - Core user data per server
2. `user_manga_progress` - Reading progress per server
3. `achievements` - Achievements per server
4. `cached_stats` - Stats per server
5. `challenges` - Server-specific challenges
6. `user_progress` - Challenge progress per server
7. `steam_users` - Steam linking per server

### 2. DATA MIGRATION STRATEGY

#### Option A: Clean Slate (Recommended for new public bot)
```python
async def migrate_to_multi_guild_v2():
    """Fresh start with multi-guild architecture"""
    
    # 1. Backup current database
    backup_path = f"database_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy("database.db", backup_path)
    
    # 2. Create new guild-aware tables
    await create_multi_guild_tables()
    
    # 3. Import existing data with default guild_id
    default_guild = 897814031346319382  # Your current server
    await migrate_existing_data(default_guild)
```

#### Option B: Gradual Migration (For existing data preservation)
```python
async def migrate_existing_tables():
    """Add guild_id to existing tables"""
    
    tables_to_migrate = [
        "users", "user_manga_progress", "achievements", 
        "cached_stats", "user_progress", "steam_users"
    ]
    
    for table in tables_to_migrate:
        # Add guild_id column
        await execute_db_operation(
            f"add guild_id to {table}",
            f"ALTER TABLE {table} ADD COLUMN guild_id INTEGER DEFAULT {CURRENT_GUILD_ID}"
        )
        
        # Update primary key constraints
        await recreate_table_with_guild_pk(table)
```

### 3. CODE CHANGES REQUIRED

#### A) Update Database Operations
```python
# Old: Global user lookup
async def get_user_data(discord_id: int):
    return await execute_db_operation(
        "get user", 
        "SELECT * FROM users WHERE discord_id = ?", 
        (discord_id,)
    )

# New: Guild-specific user lookup
async def get_user_data(discord_id: int, guild_id: int):
    return await execute_db_operation(
        "get user", 
        "SELECT * FROM users WHERE discord_id = ? AND guild_id = ?", 
        (discord_id, guild_id)
    )
```

#### B) Update All Cogs
Every command must include guild context:
```python
@app_commands.command()
async def profile(self, interaction: discord.Interaction):
    guild_id = interaction.guild.id  # Always include this
    user_id = interaction.user.id
    
    user_data = await get_user_data(user_id, guild_id)
    # ... rest of command
```

### 4. STORAGE SCALING OPTIONS

#### Option A: Single Database with Guild Partitioning (Current + Recommended)
```
Pros:
- Simpler management
- Cross-server analytics possible
- Easier backups

Cons:
- Single point of failure
- Large database over time
```

#### Option B: Database Per Guild (Advanced)
```python
class DatabaseManager:
    def __init__(self):
        self.connections = {}
    
    async def get_guild_db(self, guild_id: int):
        if guild_id not in self.connections:
            db_path = f"guild_{guild_id}.db"
            self.connections[guild_id] = await aiosqlite.connect(db_path)
        return self.connections[guild_id]
```

#### Option C: External Database (Production Scale)
```
PostgreSQL/MySQL with proper indexing:
- Better performance
- Professional backup solutions
- Multi-server deployment ready
```

### 5. IMPLEMENTATION PRIORITY

#### Phase 1: Critical Systems (MUST DO)
1. ✅ Invite tracker (already done)
2. 🔄 User registration system
3. 🔄 Profile/stats system
4. 🔄 Achievement system

#### Phase 2: Feature Systems (SHOULD DO)
1. Challenge system
2. Manga progress tracking
3. Steam integration
4. Recommendation system

#### Phase 3: Optional (NICE TO HAVE)
1. Cross-server statistics
2. Global leaderboards
3. Server comparison features

### 6. DEPLOYMENT CONSIDERATIONS

#### A) Bot Permissions
- Must request permissions per server
- Cannot assume admin access
- Handle permission failures gracefully

#### B) Rate Limiting
- Discord API limits per bot token
- Implement proper rate limiting
- Consider sharding for 2500+ servers

#### C) Resource Management
```python
# Monitor database size
async def check_db_health():
    db_size = os.path.getsize(DB_PATH)
    if db_size > 100 * 1024 * 1024:  # 100MB
        logger.warning(f"Database size: {db_size/1024/1024:.1f}MB")
        # Consider archiving old data
```

### 7. TESTING STRATEGY

1. **Create test servers** with different configurations
2. **Test data isolation** between servers
3. **Verify migration scripts** don't corrupt data
4. **Load test** with multiple concurrent servers
5. **Test server leave/join** scenarios

## 🚀 RECOMMENDED IMPLEMENTATION STEPS

### Step 1: Database Migration Script
Create `migrate_to_public.py` that:
- Backs up current database
- Creates new guild-aware schema
- Migrates existing data to your current guild
- Validates data integrity

### Step 2: Update Core Systems
Modify these files to include `guild_id`:
- `database.py` - All database operations
- `cogs/login.py` - User registration
- `cogs/profile.py` - User profiles
- `cogs/stats.py` - Statistics

### Step 3: Test Deployment
- Deploy to test servers
- Verify data isolation
- Test all commands work per-server

### Step 4: Production Deployment
- Update bot permissions
- Deploy with monitoring
- Monitor database growth
- Set up backup procedures

## ⚠️ CRITICAL CONSIDERATIONS

1. **Data Loss Risk**: Backup everything before migration
2. **Downtime**: Plan for maintenance window
3. **Bot Verification**: May need Discord verification for 100+ servers
4. **Privacy**: Consider GDPR compliance for user data
5. **Monitoring**: Set up logging and alerting for issues

Would you like me to create the specific migration scripts for your bot?