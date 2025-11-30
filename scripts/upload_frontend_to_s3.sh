#!/bin/bash

# Upload Frontend to S3
# This script uploads the updated index.html with API key to your S3 bucket

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}Frontend S3 Upload Script${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# Get bucket name
if [ -z "$1" ]; then
    echo -e "${YELLOW}Enter your S3 bucket name (e.g., my-agenticai-frontend):${NC}"
    read BUCKET_NAME
else
    BUCKET_NAME="$1"
fi

# Validate bucket name
if [ -z "$BUCKET_NAME" ]; then
    echo -e "${RED}❌ Error: Bucket name is required${NC}"
    exit 1
fi

echo -e "${GREEN}📦 Bucket: $BUCKET_NAME${NC}"
echo ""

# Check if index.html exists
INDEX_PATH="templates/index.html"
if [ ! -f "$INDEX_PATH" ]; then
    echo -e "${RED}❌ Error: $INDEX_PATH not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Found: $INDEX_PATH${NC}"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ Error: AWS CLI not installed${NC}"
    echo -e "${YELLOW}Install from: https://aws.amazon.com/cli/${NC}"
    exit 1
fi

AWS_VERSION=$(aws --version 2>&1)
echo -e "${GREEN}✓ AWS CLI: $AWS_VERSION${NC}"
echo ""

# Confirm upload
echo -e "${CYAN}Ready to upload index.html to S3${NC}"
echo -e "  Source: $INDEX_PATH"
echo -e "  Destination: s3://$BUCKET_NAME/index.html"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}❌ Upload cancelled${NC}"
    exit 0
fi

echo ""
echo -e "${CYAN}📤 Uploading to S3...${NC}"

# Upload with proper content type and cache control
if aws s3 cp "$INDEX_PATH" "s3://$BUCKET_NAME/index.html" \
    --content-type "text/html" \
    --cache-control "no-cache, no-store, must-revalidate" \
    --metadata-directive REPLACE; then
    
    echo -e "${GREEN}✅ Upload successful!${NC}"
    echo ""
    
    # Get bucket website endpoint
    echo -e "${CYAN}🌐 Getting website endpoint...${NC}"
    if aws s3api get-bucket-website --bucket "$BUCKET_NAME" &> /dev/null; then
        ENDPOINT="http://$BUCKET_NAME.s3-website-us-east-1.amazonaws.com"
        echo -e "${GREEN}✓ Website URL: $ENDPOINT${NC}"
        echo ""
        echo -e "${GREEN}🎉 Frontend deployed successfully!${NC}"
        echo ""
        echo -e "${CYAN}Next steps:${NC}"
        echo "  1. Open: $ENDPOINT"
        echo "  2. Open browser DevTools (F12) → Network tab"
        echo "  3. Verify 'x-api-key' header is present in API requests"
    else
        echo -e "${YELLOW}⚠️ Upload successful, but couldn't get website endpoint${NC}"
        echo -e "${YELLOW}Check your S3 bucket configuration${NC}"
    fi
else
    echo -e "${RED}❌ Upload failed${NC}"
    echo -e "${YELLOW}Check AWS credentials and bucket permissions${NC}"
    exit 1
fi

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}Upload Complete${NC}"
echo -e "${CYAN}========================================${NC}"
