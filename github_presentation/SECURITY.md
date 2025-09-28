# Security Policy

## 🛡️ Security Statement

The security of Lemegeton Discord Bot is a top priority. This document outlines our security practices and how to report security vulnerabilities.

## 📋 Security Practices

### Environment Variables
- All sensitive information (API keys, tokens, database URLs) is stored in environment variables
- Never commit `.env` files to version control
- Use the provided `.env.example` as a template

### API Keys and Tokens
- **Discord Bot Token**: Keep your bot token secret and never share it
- **Steam API Key**: Required for gaming features, obtain from [Steam Dev Portal](https://steamcommunity.com/dev/apikey)
- **Database URLs**: Use secure connection strings with proper authentication

### Database Security
- SQLite databases are stored locally and not accessible remotely by default
- Regular backups are created automatically
- Sensitive user data is minimal and properly handled

### Input Validation
- All user inputs are validated and sanitized
- SQL injection protection through parameterized queries
- Rate limiting implemented to prevent abuse

## 🔍 Security Features

### Authentication & Authorization
- Discord's built-in OAuth2 authentication
- Role-based command access control
- Guild-specific command restrictions where appropriate

### Data Protection
- Minimal data collection (only what's necessary for functionality)
- No storage of sensitive personal information
- Automatic cleanup of temporary data

### Network Security
- HTTPS connections for all external API calls
- Secure WebSocket connections to Discord
- Certificate validation for all HTTPS requests

## 🚨 Reporting Security Vulnerabilities

### Supported Versions

Currently supported versions for security updates:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

### Reporting Process

If you discover a security vulnerability, please follow these steps:

1. **DO NOT** create a public GitHub issue
2. Send an email to the maintainer with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact assessment
   - Suggested fix (if available)

### Response Timeline

- **Initial Response**: Within 48 hours
- **Vulnerability Assessment**: Within 1 week
- **Fix Development**: Varies based on complexity
- **Security Patch Release**: As soon as possible after fix is ready

## 🔧 Security Configuration

### Recommended Setup

1. **Environment Variables**: Always use `.env` files locally and environment variables in production
2. **Permissions**: Follow principle of least privilege for bot permissions
3. **Monitoring**: Enable logging for security-related events
4. **Updates**: Keep dependencies updated regularly

### Bot Permissions

The bot requests only the minimum permissions necessary:

- `Send Messages`: For command responses
- `Embed Links`: For rich message formatting
- `Use Slash Commands`: For modern command interface
- `Read Message History`: For timestamp conversion features
- `Manage Messages`: Only for cleanup commands (if enabled)

### Database Permissions

- SQLite: Local file access only
- No remote database connections required
- Automatic database backups

## 📚 Security Resources

### Dependencies
- Regular security audits of Python dependencies
- Automated dependency updates where safe
- Pinned versions for stability

### Best Practices
- Follow OWASP security guidelines
- Regular security reviews of code changes
- Secure coding practices enforced

### Third-Party Services
- **Discord**: Official API with built-in security measures
- **Steam**: Official Web API with rate limiting
- **AniList**: GraphQL API with query complexity limits
- **Twitter/snscrape**: Read-only access, respects rate limits

## 🔒 Privacy Considerations

### Data Collection
- **User IDs**: Discord user IDs for command tracking
- **Guild IDs**: Server identification for guild-specific features
- **Timestamps**: For timezone conversion preferences
- **No personal messages or content is stored**

### Data Retention
- User preferences: Stored until manually deleted
- Logs: Rotated and cleaned automatically
- Temporary data: Cleaned on bot restart

### Data Access
- Only bot administrators can access stored data
- No third-party data sharing
- Users can request data deletion

## 🛠️ Development Security

### Code Review
- All changes reviewed for security implications
- Automated security scanning (where applicable)
- Dependency vulnerability checks

### Testing
- Security testing for input validation
- Authentication and authorization testing
- API security testing

### Deployment
- Secure deployment practices
- Environment variable validation
- Health checks and monitoring

## 📞 Contact Information

For security-related inquiries:
- **Primary Contact**: Repository maintainer
- **Response Time**: 48 hours maximum
- **Emergency Contact**: Create a security advisory on GitHub

## 🏷️ Acknowledgments

We appreciate responsible disclosure of security vulnerabilities and will acknowledge contributors who help improve the security of Lemegeton Discord Bot.

---

**Last Updated**: January 2025
**Version**: 1.0.0