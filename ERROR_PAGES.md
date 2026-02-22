# Error Pages Implementation

This document describes the custom error pages implemented for the Ollama Dashboard Django application.

## Overview

Custom error pages have been implemented for the following HTTP error codes:

- **400** - Bad Request
- **403** - Forbidden/Access Denied
- **404** - Page Not Found
- **500** - Internal Server Error

## Files Created

### Template Files

1. `console/templates/console/400.html` - Bad Request error page
2. `console/templates/console/403.html` - Forbidden/Access Denied error page
3. `console/templates/console/404.html` - Page Not Found error page
4. `console/templates/console/500.html` - Internal Server Error error page
5. `console/templates/console/test_errors.html` - Test page for error pages (DEBUG mode only)

### CSS Updates

Added error page styles to `assets/css/app.css`:
- `.error-page` - Container for error pages
- `.error-content` - Content wrapper for error messages
- `.error-code` - Large error code display (400, 403, 404, 500)
- `.error-title` - Error title
- `.error-message` - Descriptive error message
- `.error-actions` - Action buttons container
- `.error-help` - Help text

### Code Updates

1. **`console/views.py`** - Added error handler functions:
   - `handler400()` - Custom 400 error handler
   - `handler403()` - Custom 403 error handler
   - `handler404()` - Custom 404 error handler
   - `handler500()` - Custom 500 error handler
   - Test views (only available in DEBUG mode)

2. **`ollama_dashboard/urls.py`** - Configured error handlers for the project

3. **`console/urls.py`** - Added test error URLs (DEBUG mode only)

## How Error Pages Work

### In Production (DEBUG=False)

When `DEBUG = False` in settings:
1. Django will use the custom error handlers defined in `views.py`
2. Users will see the styled error pages instead of technical error messages
3. The test error pages are not accessible

### In Development (DEBUG=True)

When `DEBUG = True` in settings:
1. Django shows detailed error pages by default
2. To test custom error pages, visit `/test-errors/`
3. The test page provides links to trigger each error type

## Testing Error Pages

### In Development Mode

1. Ensure `DEBUG = True` in your `.env` file or settings
2. Start the development server
3. Visit `http://localhost:8000/test-errors/`
4. Click on the test links to see each error page

### Testing in Production Mode

To test in production mode:

1. Set `DEBUG = False` in your `.env` file:
   ```
   DEBUG=False
   ```

2. Visit a non-existent page to see the 404 error page
3. Trigger a server error to see the 500 error page

## Customization

### Modifying Error Pages

To modify the error pages:

1. Edit the corresponding HTML template in `console/templates/console/`
2. Update the CSS styles in `assets/css/app.css` under the "Error page styles" section

### Adding New Error Pages

To add a new error page (e.g., 401 Unauthorized):

1. Create a template file: `console/templates/console/401.html`
2. Add a handler function in `views.py`:
   ```python
   def handler401(request: HttpRequest, exception=None) -> HttpResponse:
       return render(request, 'console/401.html', status=401)
   ```
3. Configure the handler in `ollama_dashboard/urls.py`:
   ```python
   handler401 = console_views.handler401
   ```

## Security Considerations

1. Error pages should not reveal sensitive information about the application
2. In production, ensure `DEBUG = False` to prevent exposure of stack traces
3. The test error pages are only accessible when `DEBUG = True`

## Notes

- The error pages use the same base template (`console/base.html`) as the rest of the application
- All error pages include navigation back to the main dashboard and chat pages
- The design is consistent with the overall application theme
- Error pages are responsive and work on mobile devices
