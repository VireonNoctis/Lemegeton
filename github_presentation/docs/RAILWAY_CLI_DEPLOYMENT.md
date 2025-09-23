# 🚂 Railway CLI Deployment Guide

Deploy your multi-guild Discord bot to Railway using the command line interface.

## 🔧 Prerequisites

✅ **Railway CLI installed** (version 4.8.0+)
✅ **GitHub repository** with your bot code
✅ **Discord bot token** and **Steam API key**

## 🚀 Quick Deployment Steps

### 1. Login to Railway

```bash
railway login
```

This will open your browser to authenticate with Railway.

### 2. Initialize Project

```bash
railway login
railway link
```

Choose:
- **"Create new project"** 
- **Connect to GitHub repository** (recommended)

### 3. Set Environment Variables

**For Multi-Guild (Public Bot)**:
```bash
railway variables set DISCORD_TOKEN=your_discord_bot_token_here
railway variables set STEAM_API_KEY=your_steam_api_key_here
railway variables set BOT_ID=your_bot_user_id_here
railway variables set DATABASE_PATH=/app/database.db
railway variables set ENVIRONMENT=production
```

**⚠️ IMPORTANT**: DO NOT set `GUILD_ID` for multi-guild deployment!

### 4. Deploy

```bash
railway up
```

Your bot will be deployed automatically! 🎉

## 🔍 Monitoring Commands

### Check Deployment Status
```bash
railway status
```

### View Logs
```bash
railway logs
```

### Check Variables
```bash
railway variables
```

### Open Railway Dashboard
```bash
railway open
```

## 🛠️ Management Commands

### Update Environment Variables
```bash
railway variables set VARIABLE_NAME=new_value
```

### Redeploy
```bash
railway up --detach
```

### Connect to Database (if needed)
```bash
railway connect
```

## 🔧 Advanced Configuration

### Custom Build Command (optional)
If you need to customize the build process, Railway will automatically detect Python and use:
- **Build**: `pip install -r requirements.txt`
- **Start**: `python bot.py`

Your `railway.json` already configures this properly.

### Environment-Specific Deployment
```bash
# Deploy to specific environment
railway up --environment production

# Set variables for specific environment  
railway variables set DISCORD_TOKEN=token --environment production
```

## 🐛 Troubleshooting

### Authentication Issues
```bash
railway logout
railway login
```

### Project Not Found
```bash
railway link
# Select your existing project or create new
```

### Deployment Fails
```bash
railway logs
# Check logs for specific errors
```

### Variable Issues
```bash
railway variables
# Verify all required variables are set
```

## 📊 Production Checklist

Before deploying:

- ✅ Railway CLI installed and authenticated
- ✅ Environment variables set (except GUILD_ID for multi-guild)
- ✅ Bot token and Steam API key valid
- ✅ Repository linked to Railway project
- ✅ `requirements.txt` includes all dependencies

## 🎯 Post-Deployment

After successful deployment:

1. **Check bot status**: `railway logs`
2. **Verify bot is online** in Discord
3. **Test commands** in a test server
4. **Monitor performance**: `railway open` → Dashboard

## 💡 Pro Tips

- **Use `railway logs -f`** to follow logs in real-time
- **Set up webhooks** for automatic GitHub deployments
- **Use `railway shell`** to debug issues interactively
- **Monitor resource usage** with `railway metrics`

---

**🎉 Your multi-guild Discord bot is now deployed via CLI!**

The bot will automatically:
- ✅ Handle unlimited Discord servers
- ✅ Isolate data per guild (19/19 tables ready)
- ✅ Scale with your community growth
- ✅ Provide built-in monitoring and health checks

Need help? Run `railway help` or check the deployment logs!