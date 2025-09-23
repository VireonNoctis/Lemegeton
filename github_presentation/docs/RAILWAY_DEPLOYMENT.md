# 🚀 Railway Deployment Guide

This guide will help you deploy your **multi-guild Discord bot with monitoring** to Railway for **24/7 free hosting**.

## 📋 Prerequisites

1. **GitHub Account** - Your bot code needs to be in a GitHub repository
2. **Discord Bot Token** - From Discord Developer Portal  
3. **Steam API Key** - From Steam Web API
4. **Bot ID** - Your Discord bot user ID

## 🔧 Step 1: Prepare Your Repository

Your repository is already configured with:
- ✅ `railway.json` - Railway deployment configuration
- ✅ `requirements.txt` - Python dependencies with monitoring
- ✅ `.env.template` - Environment variables template
- ✅ **Multi-guild support** - Ready for public bot deployment
- ✅ **Monitoring system** - Dashboard and health checks
- ✅ **Guild isolation** - Complete database separation per server

## 🌐 Step 2: Create Railway Account

1. Go to [railway.app](https://railway.app)
2. Click **"Start a New Project"**
3. Sign up with your **GitHub account**

## 🚂 Step 3: Deploy from GitHub

1. In Railway dashboard, click **"New Project"**
2. Select **"Deploy from GitHub repo"**
3. Choose your bot repository
4. Railway will automatically detect it's a Python project

## ⚙️ Step 4: Set Environment Variables

In Railway project settings, add these variables:

### Required Variables:
```bash
DISCORD_TOKEN=your_discord_bot_token_here
STEAM_API_KEY=your_steam_api_key_here  
BOT_ID=your_bot_user_id_here
```

### **⚠️ IMPORTANT: Multi-Guild Configuration**
**Remove or comment out `GUILD_ID`** for public bot mode:
```bash
# GUILD_ID=your_discord_server_id_here  # Comment this out for multi-guild
```

### Optional Variables:
```bash
DATABASE_PATH=/app/database.db
ENVIRONMENT=production
PORT=8080
```

## 🔑 How to Get Required Values:

### Discord Bot Token:
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Select your bot application
3. Go to **"Bot"** tab
4. Click **"Copy Token"**

### Steam API Key:
1. Go to [Steam Web API Key](https://steamcommunity.com/dev/apikey)
2. Enter a domain name (any website URL works)
3. Copy the generated API key

### Guild ID (Server ID):
1. Enable Developer Mode in Discord (User Settings → Advanced → Developer Mode)
2. Right-click your Discord server
3. Click **"Copy Server ID"**

### Bot ID:
1. In Discord Developer Portal → Your Bot → General Information
2. Copy the **Application ID**

### Channel ID:
1. Right-click any channel in your Discord server
2. Click **"Copy Channel ID"**

## 🚀 Step 5: Deploy!

1. Railway will automatically start building your bot
2. Check the **"Deployments"** tab for build progress
3. Once deployed, your bot will be **online 24/7**!

## 📊 Railway Free Tier Limits:

- **500 execution hours/month** + **$5 monthly credit**
- **1GB RAM** per service
- **1GB storage** (persistent volumes)
- Perfect for Discord bots!

## 🔧 Managing Your Deployment

### View Logs
- Go to Railway project → **"Deployments"** → Click latest deployment

### Update Bot  
- Push code to GitHub → Railway automatically redeploys

### Environment Variables
- Railway project → **"Variables"** tab

## � Monitoring Features

Your bot includes a **built-in monitoring system**:

- **Health Checks**: Railway automatically monitors bot health  
- **Multi-Guild Tracking**: Bot works across unlimited Discord servers
- **Database Status**: All 19/19 tables are guild-isolated and ready
- **System Metrics**: CPU, memory, and uptime tracking

### 🔧 Monitoring Access

**Note**: The monitoring dashboard is designed for local development. In production:

- Health checks run automatically (configured in `railway.json`)
- Bot logs available in Railway dashboard
- Database status tracked internally  
- System metrics handled by Railway platform

## �🛠️ Troubleshooting

### Bot Not Responding
- Check Railway logs for errors
- Verify all environment variables are set correctly
- Ensure Discord bot has proper permissions in servers

### Multi-Guild Configuration
**For public bot (multiple servers)**:
```bash
# ✅ Required variables:
DISCORD_TOKEN=your_token
STEAM_API_KEY=your_key  
BOT_ID=your_bot_id

# ❌ DO NOT set GUILD_ID for multi-guild mode
# GUILD_ID=  # Leave this unset!
```

### Database Issues
- Railway provides **persistent storage**
- Database automatically backed up
- All tables are **guild-isolated** for multi-server support
- 19/19 tables ready for production deployment

### Performance Issues  
- Railway free tier: **512MB RAM, shared CPU**
- Monitor resource usage in Railway dashboard
- Consider upgrading for high-traffic bots

### API Rate Limits
- Steam API has rate limits - bot includes delays
- Discord API limits handled by discord.py library

## 📈 Production Checklist

Before going live:

- ✅ Environment variables set correctly
- ✅ Bot has proper permissions in Discord servers
- ✅ Steam API key is valid  
- ✅ Database schema is guild-ready (19/19 tables)
- ✅ Railway deployment successful
- ✅ Bot responds to commands in test server

## 🎉 Success!

Your **multi-guild Discord bot with monitoring** is now running 24/7 on Railway! 

### What Your Bot Can Do:
- **Steam Integration**: Register profiles, view games, get recommendations
- **Multi-Guild Support**: Works in unlimited Discord servers simultaneously  
- **Guild Isolation**: Each server has separate data and settings
- **Auto-Scaling**: Handles growth from 1 to 1000+ servers
- **Built-in Monitoring**: Health checks and performance tracking

### User Commands Available:
- Register Steam profiles with `/steam register`
- View profiles with `/steam profile` 
- Get personalized game recommendations with `/steam recommendations`
- Browse games with `/browse`
- Create and join challenges with `/challenge` commands
- Track anime/manga with AniList integration
- And much more!

## � Monitoring Your Success

- **Railway Dashboard**: View deployment status, logs, resource usage
- **Discord**: Bot appears online with activity status across all servers
- **Logs**: Check Railway deployment logs for issues
- **Growth Tracking**: Monitor server count and user activity

---

**🎉 Congratulations!** Your multi-guild Discord bot is now deployed and ready to serve unlimited Discord communities!

**Need help?** Check Railway's documentation, Discord's developer resources, or review your deployment logs.