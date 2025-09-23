# User Cleanup System

The User Cleanup System is an automated background service that periodically checks if registered users are still present in Discord servers and removes their database entries if they have left.

## Features

### Automatic Cleanup
- **Runs every 24 hours** by default (configurable)
- **Multi-guild support** - handles users across multiple Discord servers
- **Batch processing** - processes users in batches to avoid blocking the bot
- **Comprehensive logging** - detailed logs of all cleanup operations

### Manual Commands (Admin Only)
- `!cleanup_users` - Clean up users for the current server
- `!cleanup_all_guilds` - Clean up users across all servers the bot is in
- `!cleanup_status` - Show cleanup system status and configuration
- `!cleanup_test` - Test the cleanup system without making changes

## How It Works

### Database Schema
The system supports both legacy (single-guild) and modern (multi-guild) database schemas:
- **Legacy mode**: Single `discord_id` per user (backwards compatible)
- **Multi-guild mode**: `(discord_id, guild_id)` unique pairs (allows same user in multiple servers)

### Cleanup Process
1. **Guild Member Fetching**: Retrieves current member list for each guild
2. **Database Comparison**: Compares registered users against current members
3. **Batch Processing**: Processes users in configurable batch sizes (default: 50)
4. **Safe Removal**: Removes database entries for users who have left
5. **Comprehensive Logging**: Records all operations with detailed statistics

### Configuration
```python
CLEANUP_INTERVAL_HOURS = 24      # How often to run cleanup (hours)
CLEANUP_BATCH_SIZE = 50          # Users processed per batch
CLEANUP_DELAY = 1.0              # Delay between batches (seconds)
```

## Database Migration

The system automatically handles migration from single-guild to multi-guild schema:

### Before Migration
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    discord_id INTEGER UNIQUE NOT NULL,  -- Single user per database
    username TEXT NOT NULL,
    -- ...
);
```

### After Migration
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    discord_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    -- ...
    UNIQUE(discord_id, guild_id)  -- Same user can be in multiple guilds
);
```

## Usage Examples

### Check System Status
```
!cleanup_status
```
Shows:
- Task running status
- Next automatic run time
- Configuration settings
- Available commands

### Test Before Cleanup
```
!cleanup_test
```
Shows:
- How many users are registered
- How many have left the server
- Which users would be removed
- Database schema information

### Manual Cleanup
```
!cleanup_users          # Clean current server only
!cleanup_all_guilds     # Clean all servers
```

## Logging

All cleanup operations are logged to `logs/user_cleanup.log`:

```
[2025-09-23 15:45:12] [INFO] [UserCleanup] 🧹 Starting user cleanup for guild: MyServer (ID: 123456789)
[2025-09-23 15:45:13] [INFO] [UserCleanup] 👻 User OldUser (Discord: 987654321) has left guild MyServer
[2025-09-23 15:45:13] [INFO] [UserCleanup] 🗑️ Cleaned up user: OldUser (Discord: 987654321)
[2025-09-23 15:45:14] [INFO] [UserCleanup] 🏁 Cleanup completed for guild MyServer: checked=25, removed=1, errors=0
```

## Safety Features

### Batch Processing
- Processes users in small batches to avoid blocking the bot
- Configurable delays between batches
- Graceful error handling for individual users

### Error Recovery
- Continues processing even if individual operations fail
- Detailed error logging for troubleshooting
- Database transaction safety

### Testing Mode
- `!cleanup_test` shows what would be cleaned without making changes
- Detailed statistics and preview of affected users
- Schema validation and compatibility checks

## Performance

### Optimized Operations
- **Member caching**: Efficiently fetches guild member lists
- **Batch processing**: Prevents blocking operations
- **Smart querying**: Uses appropriate queries for legacy vs. multi-guild schemas
- **Minimal API calls**: Optimized Discord API usage

### Resource Usage
- Memory efficient: Processes users in batches
- CPU friendly: Built-in delays prevent CPU spikes
- Database optimized: Efficient SQL queries and transactions

## Multi-Guild Benefits

### For Bot Operators
- Single database handles multiple Discord servers
- Automatic migration from single-guild setups
- Reduced maintenance overhead
- Centralized user management

### For Users
- Same AniList account works across multiple servers
- Progress tracking per server
- Flexible server management

## Troubleshooting

### Common Issues

**"Column 'guild_id' already exists"**
- Normal during migration - columns are added safely
- Database automatically handles existing schemas

**"UNIQUE constraint failed"**
- Indicates successful migration to multi-guild schema
- System automatically handles constraint updates

**High CPU usage during cleanup**
- Increase `CLEANUP_DELAY` to add more time between batches
- Reduce `CLEANUP_BATCH_SIZE` to process fewer users at once

### Debug Commands
```python
# Check current schema
python scripts/test_user_cleanup.py

# Manual cleanup with detailed logging
!cleanup_test
!cleanup_users
```

## Future Enhancements

### Planned Features
- Configurable cleanup intervals per guild
- User notification before cleanup (opt-in)
- Cleanup statistics dashboard
- Integration with bot monitoring system

### Possible Improvements
- Smart cleanup scheduling based on server activity
- Cleanup history tracking
- Integration with Discord audit logs
- Advanced filtering options