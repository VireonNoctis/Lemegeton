# Contributing to Lemegeton Discord Bot

We welcome contributions from the community! This document provides guidelines for contributing to the Lemegeton Discord Bot project.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Submitting Changes](#submitting-changes)
- [Code Style Guidelines](#code-style-guidelines)
- [Testing](#testing)
- [Documentation](#documentation)

## 🤝 Code of Conduct

This project adheres to a code of conduct that we expect all contributors to follow. Please be respectful and inclusive in all interactions.

### Our Standards

- Use welcoming and inclusive language
- Be respectful of differing viewpoints and experiences
- Gracefully accept constructive criticism
- Focus on what is best for the community
- Show empathy towards other community members

## 🚀 Getting Started

### Prerequisites

- Python 3.9 or higher
- Git
- Discord Bot Token (for testing)
- Basic knowledge of discord.py

### Development Setup

1. **Fork the repository**
   ```bash
   git clone https://github.com/yourusername/lemegeton-test.git
   cd lemegeton-test
   ```

2. **Set up virtual environment**
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # Linux/Mac
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your test bot token
   ```

5. **Run the bot**
   ```bash
   python bot.py
   ```

## 🛠️ Making Changes

### Branch Naming Convention

Use descriptive branch names with the following prefixes:
- `feature/` - New features
- `bugfix/` - Bug fixes
- `docs/` - Documentation changes
- `refactor/` - Code refactoring
- `test/` - Adding or updating tests

Example: `feature/steam-game-recommendations`

### Commit Messages

Use clear, descriptive commit messages:
- Use the present tense ("Add feature" not "Added feature")
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit the first line to 72 characters or less
- Reference issues and pull requests when applicable

Example:
```
Add Steam game recommendation feature

- Implement recommendation algorithm based on user library
- Add new command /steam recommendations
- Include unit tests for recommendation logic

Closes #123
```

## 📝 Submitting Changes

### Pull Request Process

1. **Create a new branch** from `main`
2. **Make your changes** following the code style guidelines
3. **Test your changes** thoroughly
4. **Update documentation** if necessary
5. **Submit a pull request** with a clear description

### Pull Request Template

```markdown
## Description
Brief description of changes made.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] I have tested this change locally
- [ ] I have added/updated tests as necessary
- [ ] All existing tests pass

## Checklist
- [ ] My code follows the style guidelines
- [ ] I have performed a self-review of my code
- [ ] I have commented my code, particularly hard-to-understand areas
- [ ] I have updated the documentation accordingly
```

## 🎨 Code Style Guidelines

### Python Style

We follow PEP 8 with some modifications:
- Maximum line length: 120 characters
- Use double quotes for strings
- Use type hints where appropriate
- Use descriptive variable names

### Discord.py Specific Guidelines

- Use `app_commands` for slash commands
- Follow the cog pattern for organizing commands
- Use proper error handling with try-catch blocks
- Add logging for important operations
- Use embeds for rich message formatting

### Example Code Structure

```python
import discord
from discord.ext import commands
from discord import app_commands

class ExampleCog(commands.Cog):
    """Example cog demonstrating best practices."""
    
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="example", description="Example command")
    @app_commands.guild_only()
    async def example_command(self, interaction: discord.Interaction, user: discord.Member):
        """Example command with proper error handling."""
        try:
            embed = discord.Embed(
                title="Example Response",
                description=f"Hello {user.mention}!",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"Error in example command: {e}")
            await interaction.response.send_message(
                "An error occurred while processing your request.", 
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ExampleCog(bot))
```

## 🧪 Testing

### Running Tests

```bash
python -m pytest tests/
```

### Writing Tests

- Write unit tests for new features
- Test both success and failure cases
- Mock external API calls
- Use descriptive test function names

### Test Example

```python
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.mark.asyncio
async def test_example_command_success():
    """Test that example command works correctly."""
    # Arrange
    bot = Mock()
    cog = ExampleCog(bot)
    interaction = AsyncMock()
    user = Mock()
    user.mention = "@testuser"
    
    # Act
    await cog.example_command(interaction, user)
    
    # Assert
    interaction.response.send_message.assert_called_once()
```

## 📚 Documentation

### Code Documentation

- Use docstrings for all functions, classes, and modules
- Follow Google-style docstrings
- Document parameters and return values
- Include usage examples for complex functions

### Documentation Updates

When adding new features:
1. Update the README.md
2. Add command documentation
3. Update API documentation if applicable
4. Add examples and usage instructions

## 🏗️ Project Structure

Understanding the project structure will help you navigate and contribute effectively:

```
├── bot.py                 # Main bot entry point
├── config.py             # Configuration management
├── database.py           # Database utilities
├── cogs/                 # Command modules (organized by category)
│   ├── anilist/          # AniList integration commands
│   ├── gaming/           # Gaming-related commands
│   ├── utilities/        # Utility commands
│   ├── server_management/# Server management tools
│   └── challenges/       # Challenge system
├── helpers/              # Utility functions and classes
├── docs/                 # Documentation
├── tests/                # Test files
└── data/                 # Database and cache files
```

### Adding New Cogs

When creating a new cog:
1. Place it in the appropriate category folder under `cogs/`
2. Follow the existing naming convention
3. Include proper error handling and logging
4. Add unit tests in the `tests/` directory
5. Update documentation

## 🤔 Questions?

If you have questions or need help:
- Check existing issues and discussions
- Create a new issue with the "question" label
- Join our Discord server for real-time help

## 🎉 Recognition

Contributors will be recognized in:
- The project README
- Release notes for their contributions
- Special contributor role in our Discord server

Thank you for contributing to Lemegeton! 🙏