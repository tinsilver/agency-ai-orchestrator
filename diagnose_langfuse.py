#!/usr/bin/env python3
"""Diagnose Langfuse connection and tracing issues"""

import os
import sys
from dotenv import load_dotenv

# Load env vars
load_dotenv()

def diagnose():
    """Run comprehensive Langfuse diagnostics"""

    print("=" * 70)
    print("🔍 LANGFUSE DIAGNOSTICS")
    print("=" * 70)
    print()

    # 1. Check environment variables
    print("1️⃣  Environment Variables:")
    print("-" * 70)

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    base_url = os.getenv("LANGFUSE_BASE_URL")

    print(f"LANGFUSE_PUBLIC_KEY: {'✅ Set' if public_key else '❌ Missing'}")
    print(f"LANGFUSE_SECRET_KEY: {'✅ Set' if secret_key else '❌ Missing'}")
    print(f"LANGFUSE_BASE_URL: {base_url or '❌ Missing'}")
    print()

    if not all([public_key, secret_key, base_url]):
        print("❌ Missing required environment variables!")
        return False

    # 2. Test Langfuse client initialization
    print("2️⃣  Client Initialization:")
    print("-" * 70)

    try:
        from langfuse import Langfuse
        client = Langfuse()
        print("✅ Langfuse client initialized")

        # Check if client is enabled
        if hasattr(client, 'enabled'):
            print(f"Client enabled: {client.enabled}")

        # Try to access the client's configuration
        if hasattr(client, '_client_wrapper'):
            print(f"Base URL: {client._client_wrapper._base_url}")

    except Exception as e:
        print(f"❌ Failed to initialize Langfuse client: {e}")
        import traceback
        traceback.print_exc()
        return False

    print()

    # 3. Test network connectivity to Langfuse
    print("3️⃣  Network Connectivity:")
    print("-" * 70)

    try:
        import httpx

        # Test if we can reach the Langfuse instance
        test_url = f"{base_url}/api/public/health"
        print(f"Testing: {test_url}")

        with httpx.Client(timeout=10.0) as http_client:
            try:
                response = http_client.get(test_url)
                print(f"✅ Connection successful: HTTP {response.status_code}")
                if response.status_code == 200:
                    print(f"Response: {response.text[:100]}")
            except httpx.ConnectError as e:
                print(f"❌ Connection error: {e}")
                print("This could mean:")
                print("  - Langfuse service is down")
                print("  - URL is incorrect")
                print("  - Network/firewall blocking connection")
                return False
            except httpx.TimeoutException:
                print("❌ Connection timeout")
                return False
    except ImportError:
        print("⚠️  httpx not available for connectivity test")

    print()

    # 4. Test tracing functionality
    print("4️⃣  Trace Generation:")
    print("-" * 70)

    try:
        from langfuse import observe

        @observe(name="test-trace")
        def test_function():
            return "test successful"

        result = test_function()
        print(f"✅ Trace decorator executed: {result}")

        # Flush to ensure traces are sent
        from langfuse import get_client
        langfuse = get_client()
        langfuse.flush()
        print("✅ Flush called - traces should be sent to Langfuse")

    except Exception as e:
        print(f"❌ Tracing test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    print()

    # 5. Check if traces are being sent
    print("5️⃣  Trace Sending Status:")
    print("-" * 70)

    try:
        from langfuse import get_client
        langfuse = get_client()

        # Check queue status if available
        if hasattr(langfuse, '_task_manager'):
            print("Task manager found - traces are being queued")

        print("✅ Client is configured to send traces")
        print()
        print("💡 To verify traces are actually arriving:")
        print(f"   1. Visit: {base_url}")
        print("   2. Check the Traces page")
        print("   3. Look for trace named 'test-trace'")

    except Exception as e:
        print(f"⚠️  Could not check trace status: {e}")

    print()
    print("=" * 70)
    print("✅ DIAGNOSTICS COMPLETE")
    print("=" * 70)
    return True


def railway_specific_checks():
    """Railway-specific diagnostics"""

    print()
    print("=" * 70)
    print("🚂 RAILWAY-SPECIFIC CHECKS")
    print("=" * 70)
    print()

    # Check if running on Railway
    railway_env = os.getenv("RAILWAY_ENVIRONMENT")
    railway_service = os.getenv("RAILWAY_SERVICE_NAME")

    if railway_env or railway_service:
        print(f"✅ Running on Railway")
        print(f"   Environment: {railway_env or 'unknown'}")
        print(f"   Service: {railway_service or 'unknown'}")
        print()

        # Check internal URL format
        base_url = os.getenv("LANGFUSE_BASE_URL", "")
        if "railway.internal" in base_url:
            print("✅ Using Railway internal URL")
            print(f"   URL: {base_url}")
            print()
            print("💡 Internal URLs should be in format:")
            print("   http://<service-name>.railway.internal:<port>")
            print()

            # Suggest checking service name
            print("🔍 Verify the Langfuse service name in Railway:")
            print("   1. Go to Railway dashboard")
            print("   2. Check the exact service name (case-sensitive)")
            print("   3. Ensure it matches the URL")
        else:
            print("⚠️  Not using Railway internal URL")
            print(f"   Current: {base_url}")
            print("   Expected format: http://langfuse-web.railway.internal:8080")
            print()
            print("💡 To use internal URL (faster, no egress costs):")
            print("   Set LANGFUSE_BASE_URL=http://<langfuse-service-name>.railway.internal:<port>")
    else:
        print("ℹ️  Not running on Railway (local environment)")

    print()


if __name__ == "__main__":
    print()
    success = diagnose()
    railway_specific_checks()

    if success:
        print()
        print("✅ All checks passed!")
        print()
        print("If traces still aren't showing up in Langfuse:")
        print("1. Check Railway logs for any Langfuse-related errors")
        print("2. Verify LANGFUSE_BASE_URL in Railway env vars")
        print("3. Test connectivity from Railway: railway run python diagnose_langfuse.py")
        print("4. Check Langfuse dashboard for any API errors")
        sys.exit(0)
    else:
        print()
        print("❌ Some checks failed - see errors above")
        sys.exit(1)
