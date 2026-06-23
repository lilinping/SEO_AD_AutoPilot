# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in SEO-AD AutoPilot, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please email: [YOUR_SECURITY_EMAIL]

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial assessment**: Within 1 week
- **Fix or mitigation**: Depends on severity, typically 1-4 weeks

## Scope

In-scope:
- Authentication/authorization bypass
- Remote code execution
- SQL injection
- Cross-site scripting (XSS) in the console
- API key/credential exposure
- Path traversal

Out-of-scope:
- Denial of service (DoS)
- Social engineering
- Issues in third-party dependencies (report upstream)

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | ✅ Yes    |

## Security Best Practices

When deploying SEO-AD AutoPilot:

1. **Never use default API keys in production**
2. **Enable HTTPS** for all API endpoints
3. **Restrict CORS** to your console domain
4. **Use environment variables** for all secrets
5. **Regularly update dependencies**
6. **Monitor logs** for suspicious activity
7. **Use Redis AUTH** if exposing Redis externally
8. **Restrict database access** to the application network

## Acknowledgments

We appreciate responsible disclosure and will credit reporters (with permission) in release notes.
