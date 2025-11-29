#!/bin/bash
# CloudWatch Monitoring Setup - Quick Start Script
# This script sets up CloudWatch monitoring for AgenticAI production system

set -e

# Default values
REGION="${1:-us-east-1}"
STACK_NAME="${2:-agenticai-stack}"

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}CloudWatch Monitoring Setup${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

echo -e "${YELLOW}Configuration:${NC}"
echo "  Region: $REGION"
echo "  Stack Name: $STACK_NAME"
echo ""

# Check if Python is available
echo -e "${YELLOW}Checking prerequisites...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "  ${GREEN}✓ Python: $PYTHON_VERSION${NC}"
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_VERSION=$(python --version)
    echo -e "  ${GREEN}✓ Python: $PYTHON_VERSION${NC}"
    PYTHON_CMD="python"
else
    echo -e "  ${RED}✗ Python not found. Please install Python 3.8+${NC}"
    exit 1
fi

# Check if boto3 is installed
echo -e "  ${YELLOW}Checking boto3...${NC}"
if $PYTHON_CMD -c "import boto3" 2>/dev/null; then
    BOTO3_VERSION=$($PYTHON_CMD -c "import boto3; print(boto3.__version__)")
    echo -e "  ${GREEN}✓ boto3: $BOTO3_VERSION${NC}"
else
    echo -e "  ${YELLOW}✗ boto3 not found. Installing...${NC}"
    pip install boto3
    echo -e "  ${GREEN}✓ boto3 installed${NC}"
fi

# Check AWS credentials
echo -e "  ${YELLOW}Checking AWS credentials...${NC}"
if aws sts get-caller-identity &> /dev/null; then
    echo -e "  ${GREEN}✓ AWS credentials configured${NC}"
else
    echo -e "  ${RED}✗ AWS credentials not configured${NC}"
    echo -e "    ${YELLOW}Run: aws configure${NC}"
    exit 1
fi

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}Step 1: Creating CloudWatch Dashboard${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

$PYTHON_CMD scripts/setup_cloudwatch_dashboard.py "$REGION" "$STACK_NAME"

if [ $? -ne 0 ]; then
    echo ""
    echo -e "${RED}✗ Dashboard creation failed${NC}"
    echo -e "  ${YELLOW}Check the error messages above${NC}"
    exit 1
fi

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}Step 2: Verifying Dashboard${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

$PYTHON_CMD scripts/test_cloudwatch_dashboard.py "$REGION"

if [ $? -ne 0 ]; then
    echo ""
    echo -e "${YELLOW}⚠ Dashboard verification had issues${NC}"
    echo -e "  ${YELLOW}The dashboard may still work, check AWS Console${NC}"
else
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✓ Monitoring Setup Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
fi

echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo -e "  ${WHITE}1. View dashboard in AWS Console${NC}"
echo -e "     ${CYAN}https://$REGION.console.aws.amazon.com/cloudwatch/home?region=$REGION#dashboards:name=AgenticAI-Production${NC}"
echo ""
echo -e "  ${WHITE}2. Trigger some API requests to generate metrics${NC}"
echo ""
echo -e "  ${WHITE}3. Proceed to Task 2: Implement error alerting${NC}"
echo -e "     ${CYAN}See: .kiro/specs/production-hardening/tasks.md${NC}"
echo ""
echo -e "${YELLOW}Documentation:${NC}"
echo -e "  ${CYAN}- Setup Guide: docs/CLOUDWATCH_DASHBOARD_SETUP.md${NC}"
echo -e "  ${CYAN}- Script README: scripts/README_CLOUDWATCH.md${NC}"
echo ""
