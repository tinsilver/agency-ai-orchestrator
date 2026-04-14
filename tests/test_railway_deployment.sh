#!/bin/bash
# Test Railway deployment
# Usage: ./test_railway_deployment.sh https://your-app.up.railway.app

RAILWAY_URL="${1:-web-prod-e2096.up.railway.app}"

echo "Testing Railway deployment at: $RAILWAY_URL"
echo ""

# Test 1: Health check
echo "1. Health Check:"
curl -s "$RAILWAY_URL/health" | jq '.' || echo "Health endpoint failed"
echo ""

# Test 2: Send test webhook
echo "2. Test Webhook (Enrichment):"
curl -X POST "$RAILWAY_URL/webhook" \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "www.theoruby.com",
    "request_text": "Add a contact form to my website",
    "client_priority": "normal",
    "client_category": "development"
  }' | jq '.' || echo "Webhook failed"

echo ""
echo "✅ Deployment test complete!"
echo "Check Langfuse dashboard for traces: https://langfuse-web-production-6d35.up.railway.app"
