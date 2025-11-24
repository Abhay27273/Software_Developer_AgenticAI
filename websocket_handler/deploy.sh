#!/bin/bash
# Deployment script for WebSocket Handler to ECS Fargate

set -e

# Configuration
ENVIRONMENT=${1:-prod}
AWS_REGION=${AWS_REGION:-us-east-1}
STACK_NAME="agenticai-stack"

echo "=========================================="
echo "WebSocket Handler Deployment"
echo "Environment: $ENVIRONMENT"
echo "Region: $AWS_REGION"
echo "=========================================="

# Get ECR repository URI from CloudFormation stack
echo "Getting ECR repository URI..."
REPOSITORY_URI=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query "Stacks[0].Outputs[?OutputKey=='WebSocketRepositoryUri'].OutputValue" \
  --output text \
  --region $AWS_REGION)

if [ -z "$REPOSITORY_URI" ]; then
  echo "Error: Could not get ECR repository URI from stack"
  exit 1
fi

echo "Repository URI: $REPOSITORY_URI"

# Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $REPOSITORY_URI

# Build Docker image
echo "Building Docker image..."
docker build -t agenticai-websocket:latest .

# Tag image
echo "Tagging image..."
docker tag agenticai-websocket:latest $REPOSITORY_URI:latest
docker tag agenticai-websocket:latest $REPOSITORY_URI:$(date +%Y%m%d-%H%M%S)

# Push image to ECR
echo "Pushing image to ECR..."
docker push $REPOSITORY_URI:latest
docker push $REPOSITORY_URI:$(date +%Y%m%d-%H%M%S)

# Update ECS service to use new image
echo "Updating ECS service..."
CLUSTER_NAME=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query "Stacks[0].Outputs[?OutputKey=='ECSClusterName'].OutputValue" \
  --output text \
  --region $AWS_REGION)

SERVICE_NAME=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query "Stacks[0].Outputs[?OutputKey=='WebSocketServiceName'].OutputValue" \
  --output text \
  --region $AWS_REGION)

aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service $SERVICE_NAME \
  --force-new-deployment \
  --region $AWS_REGION

echo "=========================================="
echo "Deployment complete!"
echo "Cluster: $CLUSTER_NAME"
echo "Service: $SERVICE_NAME"
echo "=========================================="

# Get WebSocket endpoint
WEBSOCKET_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query "Stacks[0].Outputs[?OutputKey=='WebSocketEndpoint'].OutputValue" \
  --output text \
  --region $AWS_REGION)

echo "WebSocket Endpoint: $WEBSOCKET_ENDPOINT"
echo ""
echo "Monitor deployment status:"
echo "aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $AWS_REGION"
