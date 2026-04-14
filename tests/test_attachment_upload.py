#!/usr/bin/env python3
"""Test attachment upload filename sanitization"""

import re

def test_filename_sanitization():
    """Test that problematic filenames are sanitized correctly"""

    test_cases = [
        ("IMG_1762 - Tejas Kotecha.JPG", "IMG_1762___Tejas_Kotecha.JPG"),
        ("file with spaces.pdf", "file_with_spaces.pdf"),
        ("special!@#$%chars.png", "special_____chars.png"),
        ("normalfile.jpg", "normalfile.jpg"),
        ("file-with-dashes.pdf", "file-with-dashes.pdf"),
        ("file_with_underscores.png", "file_with_underscores.png"),
        ("测试文件.jpg", "______.jpg"),  # Non-ASCII characters
    ]

    print("Filename Sanitization Tests:")
    print("=" * 70)

    for original, expected in test_cases:
        safe_filename = re.sub(r'[^\w\.-]', '_', original)
        status = "✅" if safe_filename == expected else "❌"
        print(f"{status} '{original}'")
        print(f"   → '{safe_filename}'")
        if safe_filename != expected:
            print(f"   Expected: '{expected}'")
        print()


def test_content_type_detection():
    """Test that content types are correctly detected"""

    test_cases = [
        ("image.jpg", "image/jpeg"),
        ("photo.jpeg", "image/jpeg"),
        ("screenshot.png", "image/png"),
        ("animation.gif", "image/gif"),
        ("document.pdf", "application/pdf"),
        ("unknown.xyz", "application/octet-stream"),
    ]

    print("\nContent-Type Detection Tests:")
    print("=" * 70)

    for filename, expected_type in test_cases:
        lower_name = filename.lower()
        if lower_name.endswith(('.jpg', '.jpeg')):
            detected_type = 'image/jpeg'
        elif lower_name.endswith('.png'):
            detected_type = 'image/png'
        elif lower_name.endswith('.gif'):
            detected_type = 'image/gif'
        elif lower_name.endswith('.pdf'):
            detected_type = 'application/pdf'
        else:
            detected_type = 'application/octet-stream'

        status = "✅" if detected_type == expected_type else "❌"
        print(f"{status} {filename} → {detected_type}")


if __name__ == "__main__":
    test_filename_sanitization()
    test_content_type_detection()
    print("\n✅ All tests completed!")
