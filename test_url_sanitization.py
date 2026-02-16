#!/usr/bin/env python3
"""Test URL and domain sanitization"""

from app.utils import sanitize_domain, ensure_url_with_protocol


def test_sanitize_domain():
    """Test domain sanitization with various input formats"""

    test_cases = [
        # (input, expected_output)
        ("https://google.co.uk", "google.co.uk"),
        ("http://google.co.uk", "google.co.uk"),
        ("google.co.uk/", "google.co.uk"),
        ("google.co.uk", "google.co.uk"),
        ("www.google.co.uk", "google.co.uk"),
        ("https://www.google.co.uk", "google.co.uk"),
        ("https://www.google.co.uk/", "google.co.uk"),
        ("https://www.example.com/path/to/page", "example.com"),
        ("example.com:8080", "example.com"),
        ("https://example.com:443/path", "example.com"),
        ("HTTPS://GOOGLE.COM", "google.com"),
        ("  google.com  ", "google.com"),
        ("//google.com", "google.com"),
        ("", ""),
    ]

    print("=" * 70)
    print("🧪 DOMAIN SANITIZATION TESTS")
    print("=" * 70)
    print()

    all_passed = True

    for input_val, expected in test_cases:
        result = sanitize_domain(input_val)
        status = "✅" if result == expected else "❌"

        if result != expected:
            all_passed = False
            print(f"{status} FAILED")
            print(f"   Input:    '{input_val}'")
            print(f"   Expected: '{expected}'")
            print(f"   Got:      '{result}'")
        else:
            print(f"{status} '{input_val}' → '{result}'")

    print()
    print("=" * 70)

    if all_passed:
        print("✅ ALL TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED")

    print("=" * 70)
    return all_passed


def test_ensure_url_with_protocol():
    """Test URL protocol ensuring"""

    test_cases = [
        ("google.com", "https://google.com"),
        ("http://google.com", "http://google.com"),
        ("https://google.com", "https://google.com"),
        ("www.example.com", "https://www.example.com"),
        ("", ""),
    ]

    print()
    print("=" * 70)
    print("🧪 URL PROTOCOL TESTS")
    print("=" * 70)
    print()

    all_passed = True

    for input_val, expected in test_cases:
        result = ensure_url_with_protocol(input_val)
        status = "✅" if result == expected else "❌"

        if result != expected:
            all_passed = False
            print(f"{status} FAILED")
            print(f"   Input:    '{input_val}'")
            print(f"   Expected: '{expected}'")
            print(f"   Got:      '{result}'")
        else:
            print(f"{status} '{input_val}' → '{result}'")

    print()
    print("=" * 70)

    if all_passed:
        print("✅ ALL TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED")

    print("=" * 70)
    return all_passed


def test_real_world_scenarios():
    """Test with real-world webhook scenarios"""

    print()
    print("=" * 70)
    print("🌍 REAL-WORLD WEBHOOK SCENARIOS")
    print("=" * 70)
    print()

    scenarios = [
        {
            "name": "Client submits URL with https",
            "input": "https://theoruby.com",
            "expected_clean": "theoruby.com",
            "expected_url": "https://theoruby.com",
        },
        {
            "name": "Client submits domain only",
            "input": "theoruby.com",
            "expected_clean": "theoruby.com",
            "expected_url": "https://theoruby.com",
        },
        {
            "name": "Client submits with www and trailing slash",
            "input": "www.theoruby.com/",
            "expected_clean": "theoruby.com",
            "expected_url": "https://theoruby.com",
        },
        {
            "name": "Client copies from browser (full URL)",
            "input": "https://www.theoruby.com/about",
            "expected_clean": "theoruby.com",
            "expected_url": "https://theoruby.com",
        },
    ]

    for scenario in scenarios:
        print(f"📋 {scenario['name']}")
        print(f"   Input: {scenario['input']}")

        clean = sanitize_domain(scenario['input'])
        url = ensure_url_with_protocol(clean)

        clean_ok = clean == scenario['expected_clean']
        url_ok = url == scenario['expected_url']

        print(f"   {'✅' if clean_ok else '❌'} Clean domain: {clean}")
        print(f"   {'✅' if url_ok else '❌'} Full URL:      {url}")
        print()

    print("=" * 70)


if __name__ == "__main__":
    print()

    passed1 = test_sanitize_domain()
    passed2 = test_ensure_url_with_protocol()
    test_real_world_scenarios()

    print()

    if passed1 and passed2:
        print("🎉 ALL TESTS PASSED!")
        print()
        print("✅ client_id sanitization is working correctly")
        print("✅ Ready to deploy to production")
        exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        exit(1)
