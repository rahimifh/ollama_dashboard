# Production Deployment Guide

## Security Checklist

### 1. Environment Configuration

**Before deploying to production, ensure you have:**

1. **Generated a strong secret key:**
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(50))"
   ```
   Add this to your `.env` file as `DJANGO_SECRET_KEY`.

2. **Disabled debug mode:**
   ```env
   DEBUG=False
   ```

3. **Set proper allowed hosts:**
   ```env
   ALLOWED_HOSTS=your-domain.com,www.your-domain.com,server-ip-address
   ```

4. **Configured CSRF trusted origins:**
   ```env
   CSRF_TRUSTED_ORIGINS=https://your-domain.com,https://www.your-domain.com
   ```

### 2. Security Settings (for HTTPS)

If using HTTPS (which you should in production), add these to your `.env`:

```env
# HTTPS Settings
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_BROWSER_XSS_FILTER=True
SECURE_CONTENT_TYPE_NOSNIFF=True
X_FRAME_OPTIONS=DENY
```

### 3. Database Security

If using SQLite in production (not recommended for high traffic):
- Ensure the database file has proper permissions
- Consider migrating to PostgreSQL for better performance and security

For PostgreSQL, update your `.env`:
```env
DATABASE_URL=postgresql://user:password@localhost/dbname
```

And update `settings.py` to use `django-environ` or similar for parsing.

### 4. Ollama Configuration

Ensure Ollama is properly secured:
```env
# If Ollama is on a different server or port
OLLAMA_BASE_URL=http://your-ollama-server:11434

# Increase timeout for production
OLLAMA_REQUEST_TIMEOUT_SECONDS=120
```

### 5. Web Server Configuration

#### For Nginx:
```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;
    
    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;
    
    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /static/ {
        alias /path/to/your/static/files/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

#### For Apache:
```apache
<VirtualHost *:80>
    ServerName your-domain.com
    ServerAlias www.your-domain.com
    Redirect permanent / https://your-domain.com/
</VirtualHost>

<VirtualHost *:443>
    ServerName your-domain.com
    ServerAlias www.your-domain.com
    
    SSLEngine on
    SSLCertificateFile /path/to/certificate.crt
    SSLCertificateKeyFile /path/to/private.key
    
    # Security headers
    Header always set X-Frame-Options "DENY"
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-XSS-Protection "1; mode=block"
    
    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:8000/
    ProxyPassReverse / http://127.0.0.1:8000/
    
    Alias /static /path/to/your/static/files
    <Directory /path/to/your/static/files>
        Require all granted
    </Directory>
</VirtualHost>
```

### 6. Django Production Settings

Update your `settings.py` or create a `production.py` settings file:

```python
# At the end of settings.py or in a separate production.py
from .settings import *

# Override production settings
DEBUG = False

# Security settings
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Use a separate static file directory for production
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Use WhiteNoise for static files
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
```

### 7. Process Management

Use Gunicorn with systemd:

**Gunicorn config (`gunicorn_config.py`):**
```python
bind = "127.0.0.1:8000"
workers = 3
worker_class = "sync"
timeout = 120
keepalive = 5
```

**Systemd service (`/etc/systemd/system/ollama-dashboard.service`):**
```ini
[Unit]
Description=Ollama Dashboard Gunicorn
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/your/project
Environment="PATH=/path/to/venv/bin"
Environment="DJANGO_SETTINGS_MODULE=ollama_dashboard.settings"
ExecStart=/path/to/venv/bin/gunicorn --config gunicorn_config.py ollama_dashboard.wsgi:application

[Install]
WantedBy=multi-user.target
```

### 8. Monitoring and Logging

Enable Django logging in production:

```python
# In settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'console': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

### 9. Regular Maintenance

1. **Keep dependencies updated:**
   ```bash
   pip list --outdated
   pip install --upgrade -r requirements.txt
   ```

2. **Backup database regularly:**
   ```bash
   # For SQLite
   cp db.sqlite3 db.sqlite3.backup.$(date +%Y%m%d)
   
   # For PostgreSQL
   pg_dump dbname > backup.$(date +%Y%m%d).sql
   ```

3. **Monitor logs:**
   ```bash
   tail -f logs/django.log
   journalctl -u ollama-dashboard.service -f
   ```

### 10. Emergency Response

If you suspect a security breach:
1. **Immediately** change all passwords (Django admin, database, server)
2. **Rotate** the Django secret key
3. **Check** logs for suspicious activity
4. **Update** all dependencies to latest versions
5. **Review** access logs for unusual patterns

---

## Quick Start for Production

1. Generate a secure secret key
2. Set `DEBUG=False` in `.env`
3. Configure `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`
4. Set up HTTPS with a valid certificate
5. Enable all security settings in `.env`
6. Use Gunicorn + Nginx/Apache
7. Set up logging and monitoring
8. Regular backups and updates

Remember: Security is an ongoing process, not a one-time setup!