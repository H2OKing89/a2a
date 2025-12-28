# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability in A2A, please report it responsibly.

### How to Report

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, please report them via one of the following methods:

1. **GitHub Security Advisories** (Preferred)
   - Go to the [Security tab](https://github.com/H2OKing89/a2a/security/advisories)
   - Click "Report a vulnerability"
   - Provide details about the vulnerability

2. **Email**
   - Send details to the repository owner
   - Include "SECURITY" in the subject line

### What to Include

Please include as much of the following information as possible:

- **Type of vulnerability** (e.g., authentication bypass, injection, etc.)
- **Location** of the vulnerable code (file path, line numbers)
- **Steps to reproduce** the vulnerability
- **Potential impact** of the vulnerability
- **Suggested fix** (if you have one)

### Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Resolution Target**: Within 30 days (depending on complexity)

### What to Expect

1. **Acknowledgment**: We'll confirm receipt of your report
2. **Assessment**: We'll investigate and assess the severity
3. **Updates**: We'll keep you informed of our progress
4. **Resolution**: We'll work on a fix and coordinate disclosure
5. **Credit**: With your permission, we'll credit you in the release notes

## Security Best Practices

When using A2A, please follow these security practices:

### Configuration

- **Never commit credentials** to version control
- Use **environment variables** or a **`.env` file** for sensitive data
- Keep your **API keys** and **tokens** secure
- Use **read-only API tokens** when possible

### Audible Authentication

- The `audible_auth.json` file contains sensitive authentication data
- Store it in the `data/` directory (which is gitignored)
- Don't share authentication files
- Regularly rotate your credentials

### File Permissions

```bash
# Recommended permissions for sensitive files
chmod 600 .env
chmod 600 data/audible_auth.json
chmod 700 data/
```

### Network Security

- Use HTTPS for your Audiobookshelf server when possible
- Be cautious when using the tool on shared networks
- Consider using a VPN for remote access

## Dependencies

We use the following tools to maintain security:

- **Bandit**: Python security linter (runs in CI)
- **Dependabot**: Automated dependency updates
- **Dependency Review**: Reviews PRs for vulnerable dependencies
- **Pre-commit hooks**: Security checks before commits

### Running Security Checks Locally

```bash
# Run Bandit security scanner
make lint

# Or directly
bandit -r src/ -c pyproject.toml
```

## Known Security Considerations

### API Tokens

- ABS API tokens have full access to your Audiobookshelf server
- Treat them with the same care as passwords

### Caching

- The SQLite cache may contain metadata from your library
- Cache files are stored in `data/cache/` (gitignored)
- Clear cache if sharing the project directory

### Logging

- Logs may contain file paths and metadata
- Debug logging may reveal sensitive information
- Review logs before sharing for troubleshooting

## Security Updates

Security updates will be released as patch versions and announced via:

- GitHub Releases
- CHANGELOG.md
- Security Advisories (for critical issues)

---

Thank you for helping keep A2A secure! 🔒
