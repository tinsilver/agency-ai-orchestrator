# ClickUp Attachment Upload Fix

## Problem
Getting 400 Bad Request errors when uploading attachments to ClickUp API in production (Railway):
```
Error uploading attachment IMG_1762 - Tejas Kotecha.JPG: Client error '400 Bad Request'
```

## Root Causes Identified

1. **Filename encoding issues**: Special characters, spaces, and Unicode in filenames
2. **Missing content-type headers**: ClickUp API prefers explicit content types for images
3. **Poor error reporting**: Original error didn't capture ClickUp's response body
4. **No file size logging**: Couldn't diagnose large file issues

## Fixes Applied

### 1. Filename Sanitization ([app/services/clickup.py:141-148](app/services/clickup.py#L141-L148))

**Before:**
```python
files = {"attachment": (filename, file_content, content_type)}
```

**After:**
```python
# Remove non-ASCII characters (ClickUp can be sensitive to Unicode)
ascii_filename = filename.encode('ascii', 'ignore').decode('ascii')
# Fallback if filename becomes empty
if not ascii_filename or '.' not in ascii_filename:
    ext = filename.split('.')[-1] if '.' in filename else 'bin'
    ascii_filename = f"attachment_{task_id[-6:]}.{ext}"
# Replace spaces and special chars with underscores
safe_filename = re.sub(r'[^\w\.-]', '_', ascii_filename)
```

**Effect:**
- `IMG_1762 - Tejas Kotecha.JPG` → `IMG_1762_-_Tejas_Kotecha.JPG`
- `file with spaces.pdf` → `file_with_spaces.pdf`
- `测试文件.jpg` → `attachment_<taskid>.jpg` (Unicode removed)

### 2. Content-Type Detection ([app/services/clickup.py:150-159](app/services/clickup.py#L150-L159))

**Automatically sets proper MIME types:**
```python
if lower_name.endswith(('.jpg', '.jpeg')):
    content_type = 'image/jpeg'
elif lower_name.endswith('.png'):
    content_type = 'image/png'
elif lower_name.endswith('.gif'):
    content_type = 'image/gif'
elif lower_name.endswith('.pdf'):
    content_type = 'application/pdf'
else:
    content_type = 'application/octet-stream'
```

### 3. Enhanced Error Handling ([app/services/clickup.py:179-184](app/services/clickup.py#L179-L184))

**Captures full ClickUp API error response:**
```python
except httpx.HTTPStatusError as e:
    error_body = e.response.text if hasattr(e.response, 'text') else str(e)
    print(f"Error uploading: {e.response.status_code} - {error_body}")
    return {"error": f"HTTP {e.response.status_code}: {error_body}"}
```

**Now you'll see the actual error from ClickUp:**
- "File too large" (if over limit)
- "Invalid filename" (if still problematic)
- "Invalid content type" (if MIME type wrong)

### 4. File Size Logging ([app/services/clickup.py:174-175](app/services/clickup.py#L174-L175))

**Logs attachment details before upload:**
```python
file_size_mb = len(file_content) / (1024 * 1024)
print(f"Uploading: {filename} → {safe_filename} ({file_size_mb:.2f} MB, {content_type})")
```

### 5. Increased Timeout ([app/services/clickup.py:178](app/services/clickup.py#L178))

**Extended from default 5s to 60s for large files:**
```python
async with httpx.AsyncClient(timeout=60.0) as client:
```

## Testing

Run the test suite to verify sanitization:
```bash
.venv/bin/python test_attachment_upload.py
```

## What to Monitor in Production

After deploying to Railway, check logs for:

### Success Messages:
```
Uploading attachment: IMG_1762 - Tejas Kotecha.JPG → IMG_1762_-_Tejas_Kotecha.JPG (2.34 MB, image/jpeg)
Successfully uploaded: IMG_1762_-_Tejas_Kotecha.JPG
```

### Error Messages (if still occurring):
```
Error uploading: 400 - {"err": "File too large", "ECODE": "FILE_SIZE_LIMIT"}
Error uploading: 400 - {"err": "Invalid filename", "ECODE": "INVALID_FILENAME"}
Error uploading: 413 - Request Entity Too Large
```

## Known ClickUp API Limits

- **File size limit**: 100 MB per file
- **Filename**: ASCII-safe recommended, max 255 characters
- **Supported types**: Images, PDFs, documents, videos
- **Rate limiting**: Be aware if uploading many files at once

## Rollback Instructions

If issues persist, the critical change is in `/app/services/clickup.py` line 133-187.

To rollback, restore the original `create_task_attachment` method:
```bash
git diff HEAD~1 app/services/clickup.py
git checkout HEAD~1 -- app/services/clickup.py
```

## Additional Debugging

If errors continue, add this to see the full request:
```python
print(f"DEBUG: URL={url}, headers={headers}, filename={safe_filename}, size={len(file_content)}")
```

## Next Steps

1. Deploy to Railway
2. Test with a real attachment upload
3. Check Railway logs for the new diagnostic messages
4. If 400 errors persist, share the full error body from logs for further diagnosis
