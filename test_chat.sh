#!/bin/bash
KEY="${MRC_API_KEY:-your-api-key-here}"
MSG="${1:-What amenities does Vampire Manor offer?}"
curl -s -X POST http://localhost:8000/chat \
  -H "X-API-Key: ${KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"${MSG}\"}" | python3 -m json.tool
