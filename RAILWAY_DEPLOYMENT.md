# 🚀 Railway Deployment Guide

This guide will help you deploy your Discord bot to Railway for **24/7 free hosting**.

## 📋 Prerequisites

1. **GitHub Account** - Your bot code needs to be in a GitHub repository
2. **Discord Bot Token** - From Discord Developer Portal
3. **Steam API Key** - From Steam Web API
4. **Guild ID** - Your Discord server ID

## 🔧 Step 1: Prepare Your Repository

Your repository is already configured with:
- ✅ `railway.json` - Railway deployment configuration
- ✅ `requirements.txt` - Python dependencies  
- ✅ `.env.template` - Environment variables template

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
GUILD_ID=your_discord_server_id_here
BOT_ID=your_bot_user_id_here
CHANNEL_ID=your_channel_id_here
```

### Optional Variables:
```bash
DATABASE_PATH=/app/database.db
ENVIRONMENT=production
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

## 🔧 Managing Your Deployment:

### View Logs:
- Go to Railway project → **"Deployments"** → Click latest deployment

### Update Bot:
- Push code to GitHub → Railway automatically redeploys

### Environment Variables:
- Railway project → **"Variables"** tab

## 🛠️ Troubleshooting:

### Bot Not Responding:
- Check Railway logs for errors
- Verify all environment variables are set correctly
- Ensure Discord bot has proper permissions in your server

### Database Issues:
- Railway provides ephemeral storage by default
- Consider upgrading to persistent volumes if needed
- Database resets on redeploys (normal for free tier)

### API Rate Limits:
- Steam API has rate limits - bot includes delays
- Discord API limits are handled by discord.py library

## 🎉 Success!

Your Discord bot is now running 24/7 on Railway! Users can:
- Register Steam profiles with `/steam register`
- View profiles with `/steam profile`
- Get personalized game recommendations with `/steam recommendations`

## 📈 Monitoring:

- **Railway Dashboard**: View deployment status, logs, resource usage
- **Discord**: Bot appears online with activity status
- **Logs**: Check Railway deployment logs for any issues

---

**Need help?** Check Railway's documentation or Discord's developer resources!