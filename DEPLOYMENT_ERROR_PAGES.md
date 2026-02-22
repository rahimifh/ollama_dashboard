# Production Deployment Checklist for Error Pages

## Critical Settings for Production

### 1. Environment Variables
Ensure your `.env` file or production environment has:
```
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
```

### 2. Security Headers
When `DEBUG=False`, the following security headers are automatically enabled:
- `SECURE_SSL_REDIRECT` (if configured)
- `SESSION_COOKIE_SECURE=True`
- `CSRF_COOKIE_SECURE=True`
- `SECURE_BROWSER_XSS_FILTER=True`
- `SECURE_CONTENT_TYPE_NOSNIFF=True`
- `X_FRAME_OPTIONS='DENY'`

### 3. Static Files
Make sure to collect static files before deployment:
```bash
python manage.py collectstatic
```

## Testing Error Pages in Production

### Manual Testing
1. Set `DEBUG=False` in your environment
2. Restart your application server
3. Test error pages:
   - Visit a non-existent URL to test 404
   - Trigger a server error to test 500
   - Test permission errors for 403
   - Test malformed requests for 400

### Automated Testing
Consider adding tests for error pages:
```python
# In your tests.py
from django.test import TestCase
from django.urls import reverse

class ErrorPageTests(TestCase):
    def test_404_page(self):
        response = self.client.get('/non-existent-page/')
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, 'console/404.html')
    
    def test_500_page(self):
        # Test 500 by triggering an error
        with self.settings(DEBUG=False):
            response = self.client.get(reverse('console:test_500'))
            self.assertEqual(response.status_code, 500)
            self.assertTemplateUsed(response, 'console/500.html')
```

## Monitoring and Logging

### Error Monitoring
Consider integrating error monitoring tools:
- Sentry
- Rollbar
- Django's built-in error logging

### Logging Configuration
Configure Django logging to capture errors:
```python
# In settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': '/var/log/django/errors.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': True,
        },
    },
}
```

## Customization Options

### 1. Branding Error Pages
To customize error pages with your branding:
1. Edit the templates in `console/templates/console/`
2. Update the CSS in `assets/css/app.css`
3. Add your logo or custom messages

### 2. Internationalization
To translate error pages:
1. Wrap text in templates with `{% trans %}` tags
2. Run `python manage.py makemessages`
3. Translate the generated `.po` files

### 3. Custom Error Context
To add custom context to error pages:
```python
# In views.py
def handler404(request, exception):
    context = {
        'exception': str(exception),
        'request_path': request.path,
        'support_email': 'support@example.com',
    }
    return render(request, 'console/404.html', context, status=404)
```

## Troubleshooting

### Common Issues

1. **Error pages not showing in production**
   - Check that `DEBUG=False`
   - Verify `ALLOWED_HOSTS` is configured
   - Ensure static files are collected

2. **Template not found errors**
   - Check template paths are correct
   - Verify `APP_DIRS=True` in TEMPLATES settings
   - Ensure templates are in `console/templates/console/`

3. **CSS/JS not loading on error pages**
   - Check static file configuration
   - Verify `STATIC_URL` and `STATICFILES_DIRS`
   - Test with `DEBUG=True` first

### Debugging Tips

1. Test with `DEBUG=True` first to see if templates render
2. Check Django logs for template errors
3. Use browser developer tools to check network requests
4. Verify the error handlers are registered in `urls.py`

## Performance Considerations

1. Error pages should be lightweight and fast
2. Minimize external dependencies on error pages
3. Consider caching error pages (with appropriate cache headers)
4. Ensure error pages don't trigger additional errors

## Security Best Practices

1. Never expose stack traces or sensitive information
2. Use generic error messages
3. Log detailed errors server-side, not client-side
4. Sanitize any user input displayed in error messages
5. Implement rate limiting on error endpoints
```