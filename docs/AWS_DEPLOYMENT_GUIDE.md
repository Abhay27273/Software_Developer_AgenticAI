# AWS Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the AI-powered Software Development Agentic System to AWS using free tier services. The deployment uses AWS SAM (Serverless Application Model) for infrastructure as code and GitHub Actions for CI/CD automation.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [AWS Account Setup](#aws-account-setup)
3. [Local Environment Setup](#local-environment-setup)
4. [Initial Configuration](#initial-configuration)
5. [Deployment Steps](#deployment-steps)
6. [Verification](#verification)
7. [Post-Deployment Configuration](#post-deployment-configuration)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Accounts
- AWS Account (new accounts get 12 months free tier)
- GitHub Account (for CI/CD)
- Google AI Studio Account (for Gemini API key)

### Required Software
- Python 3.11 or higher
- AWS CLI 2.x
- AWS SAM CLI 1.x
- Git
- Docker (for local testing)

### Estimated Time
- Initial setup: 30-45 minutes
- First deployment: 15-20 minutes
- Subsequent deployments: 5-10 minutes (automated)

## AWS Account Setup

### Step 1: Create AWS Account

1. Go to [aws.amazon.com](https://aws.amazon.com)
2. Click "Create an AWS Account"
3. Follow the registration process:
   - Provide email and password
   - Enter account information
   - Add payment method (required but won't be charged if staying within free tier)
   - Verify phone number
   - Select "Basic Support - Free" plan

4. Wait for account activation (usually takes a few minutes)

### Step 2: Create IAM User for Deployment

**Why**: Never use root account credentials for deployments. Create a dedicated IAM user with specific permissions.

1. Sign in to AWS Console as root user
2. Navigate to IAM service
3. Click "Users" → "Add users"
4. Configure user:
   - **User name**: `agenticai-deployer`
   - **Access type**: Select "Programmatic access"
   - Click "Next: Permissions"

5. Set permissions:
   - Click "Attach existing policies directly"
   - Search and select the following policies:
     - `AWSLambda_FullAccess`
     - `AmazonDynamoDBFullAccess`
     - `AmazonS3FullAccess`
     - `AmazonSQSFullAccess`
     - `AmazonAPIGatewayAdministrator`
     - `CloudWatchFullAccess`
     - `IAMFullAccess` (needed for creating Lambda execution roles)
     - `AWSCloudFormationFullAccess`
   - Click "Next: Tags"

6. Add tags (optional):
   - Key: `Project`, Value: `AgenticAI`
   - Key: `Environment`, Value: `Production`
   - Click "Next: Review"

7. Review and create:
   - Click "Create user"
   - **IMPORTANT**: Download the CSV file with credentials or copy:
     - Access Key ID
     - Secret Access Key
   - Store these securely (you won't be able to see the secret key again)

### Step 3: Enable Required AWS Services

Most services are enabled by default, but verify:

1. Navigate to each service in AWS Console:
   - Lambda
   - DynamoDB
   - S3
   - SQS
   - API Gateway
   - CloudWatch
   - Systems Manager (Parameter Store)

2. If prompted to enable, click "Enable" or "Get Started"

## Local Environment Setup

### Step 1: Install AWS CLI

**macOS** (using Homebrew):
```bash
brew install awscli
```

**Windows**:
```powershell
# Download and run the installer
msiexec.exe /i https://awscli.amazonaws.com/AWSCLIV2.msi
```

**Linux**:
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

**Verify installation**:
```bash
aws --version
# Expected output: aws-cli/2.x.x Python/3.x.x ...
```

### Step 2: Configure AWS CLI

```bash
aws configure
```

Enter the following when prompted:
```
AWS Access Key ID: [Your Access Key from Step 2.7]
AWS Secret Access Key: [Your Secret Key from Step 2.7]
Default region name: us-east-1
Default output format: json
```

**Verify configuration**:
```bash
aws sts get-caller-identity
```

Expected output:
```json
{
    "UserId": "AIDAXXXXXXXXXXXXXXXXX",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/agenticai-deployer"
}
```

### Step 3: Install AWS SAM CLI

**macOS** (using Homebrew):
```bash
brew tap aws/tap
brew install aws-sam-cli
```

**Windows**:
```powershell
# Download and run the installer
msiexec.exe /i https://github.com/aws/aws-sam-cli/releases/latest/download/AWS_SAM_CLI_64_PY3.msi
```

**Linux**:
```bash
# Download the installer
wget https://github.com/aws/aws-sam-cli/releases/latest/download/aws-sam-cli-linux-x86_64.zip
unzip aws-sam-cli-linux-x86_64.zip -d sam-installation
sudo ./sam-installation/install
```

**Verify installation**:
```bash
sam --version
# Expected output: SAM CLI, version 1.x.x
```

### Step 4: Install Docker

Docker is required for local testing and building Lambda functions.

**macOS/Windows**: Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop)

**Linux**:
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

**Verify installation**:
```bash
docker --version
# Expected output: Docker version 20.x.x, build ...
```

### Step 5: Navigate to Project Directory

**If you already have the code** (you're working in the project):
```bash
# You're already in the right place!
# Just make sure you're in the project root directory
cd C:\Users\Abhay.Bhadauriya\Software_Developer_AgenticAI
```

**If you're deploying from a fresh machine** (new team member, CI/CD server):
```bash
git clone https://github.com/your-org/agenticai-system.git
cd agenticai-system
```

### Step 6: Install Python Dependencies

```bash
# Create virtual environment
python3.11 -m venv venv

# Activate virtual environment
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Initial Configuration

### Step 1: Set Up Parameter Store Secrets

Store sensitive credentials in AWS Systems Manager Parameter Store:

```bash
# Set Gemini API Key
aws ssm put-parameter \
    --name "/agenticai/gemini-api-key" \
    --value "YOUR_GEMINI_API_KEY" \
    --type "SecureString" \
    --description "Gemini API key for AI agents"

# Set JWT Secret (generate a random string)
aws ssm put-parameter \
    --name "/agenticai/jwt-secret" \
    --value "$(openssl rand -base64 32)" \
    --type "SecureString" \
    --description "JWT secret for authentication"

# Optional: GitHub token for repository operations
aws ssm put-parameter \
    --name "/agenticai/github-token" \
    --value "YOUR_GITHUB_TOKEN" \
    --type "SecureString" \
    --description "GitHub personal access token"
```

**Verify parameters**:
```bash
aws ssm get-parameter --name "/agenticai/gemini-api-key" --with-decryption
```

**Alternative**: Use the provided script:
```bash
python scripts/setup_parameter_store.py
```

### Step 2: Create S3 Bucket for SAM Artifacts

SAM needs an S3 bucket to store deployment artifacts:

```bash
# Create bucket (must be globally unique)
aws s3 mb s3://agenticai-sam-artifacts-$(aws sts get-caller-identity --query Account --output text)

# Enable versioning
aws s3api put-bucket-versioning \
    --bucket agenticai-sam-artifacts-$(aws sts get-caller-identity --query Account --output text) \
    --versioning-configuration Status=Enabled
```

### Step 3: Configure SAM

Create `samconfig.toml` in the project root:

```toml
version = 0.1

[default]
[default.deploy]
[default.deploy.parameters]
stack_name = "agenticai-stack"
s3_bucket = "agenticai-sam-artifacts-YOUR_ACCOUNT_ID"
s3_prefix = "agenticai"
region = "us-east-1"
capabilities = "CAPABILITY_IAM"
parameter_overrides = "Environment=production"
confirm_changeset = false
```

Replace `YOUR_ACCOUNT_ID` with your AWS account ID:
```bash
aws sts get-caller-identity --query Account --output text
```

### Step 4: Configure Environment Variables

Create `.env` file (for local development only):

```bash
cp .env.example .env
```

Edit `.env`:
```env
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012

# DynamoDB
DYNAMODB_TABLE_NAME=agenticai-data

# S3
S3_BUCKET_NAME=agenticai-generated-code

# SQS Queue URLs (will be populated after deployment)
SQS_QUEUE_URL_PM=
SQS_QUEUE_URL_DEV=
SQS_QUEUE_URL_QA=
SQS_QUEUE_URL_OPS=

# API Configuration
API_ENDPOINT=

# Gemini API (for local testing only - use Parameter Store in production)
GEMINI_API_KEY=your_key_here
```

**IMPORTANT**: Never commit `.env` to version control. It's already in `.gitignore`.

## Deployment Steps

**🚀 DEPLOYMENT ARCHITECTURE NOTE**:
This guide uses a **serverless-only architecture** for fast, simple deployment:
- ✅ Deploys in 5-10 minutes
- ✅ Uses only Lambda, API Gateway, DynamoDB, SQS, S3
- ✅ No VPC, ECS, or container complexity
- ✅ Stays within AWS free tier limits

If your `template.yaml` includes VPC/ECS resources, deployment may take 30+ minutes or get stuck. See [Issue 9](#issue-9-deployment-stuck-or-taking-too-long) for troubleshooting.

### Step 1: Validate SAM Template

Before deploying, validate the template syntax:

```bash
sam validate --template template.yaml
```

Expected output:
```
template.yaml is a valid SAM Template
```

### Step 2: Build Lambda Functions

Build all Lambda functions and dependencies:

```bash
sam build --template template.yaml
```

This will:
- Create a `.aws-sam` directory
- Install Python dependencies for each Lambda function
- Package the code for deployment

Expected output:
```
Build Succeeded

Built Artifacts  : .aws-sam/build
Built Template   : .aws-sam/build/template.yaml
```

### Step 3: Deploy to AWS (First Time)

**IMPORTANT**: The deployment uses a **serverless-only architecture** (Lambda + API Gateway + DynamoDB + SQS + S3) which deploys in 5-10 minutes. If your template includes VPC/ECS resources, it may take 30+ minutes or get stuck.

For the first deployment, use guided mode:

```bash
sam deploy --guided
```

Answer the prompts:
```
Stack Name [agenticai-stack]: agenticai-stack
AWS Region [us-east-1]: us-east-1
Parameter Environment [prod]: prod
Parameter BudgetAlertEmail: your-email@example.com
Confirm changes before deploy [Y/n]: n
Allow SAM CLI IAM role creation [Y/n]: Y
Disable rollback [y/N]: N
Save arguments to configuration file [Y/n]: Y
SAM configuration file [samconfig.toml]: samconfig.toml
SAM configuration environment [default]: default
```

The deployment will:
1. Create a CloudFormation change set
2. Display resources to be created
3. Deploy the stack (takes 5-10 minutes for serverless-only)

**Monitor deployment**:
```bash
# In another terminal
aws cloudformation describe-stack-events \
    --stack-name agenticai-stack \
    --query 'StackEvents[0:10].[Timestamp,ResourceStatus,ResourceType,LogicalResourceId]' \
    --output table
```

**Expected Resources** (serverless-only):
- 4 Lambda Functions (ApiHandler, PMAgentWorker, DevAgentWorker, QAAgentWorker, OpsAgentWorker)
- 1 API Gateway REST API
- 1 DynamoDB Table
- 4 SQS Queues
- 1 S3 Bucket
- 1 IAM Role

**⚠️ If deployment takes longer than 15 minutes**, see [Troubleshooting: Stuck Deployment](#issue-9-deployment-stuck-or-taking-too-long)

### Step 4: Deploy to AWS (Subsequent Deployments)

After the first deployment, use:

```bash
sam build && sam deploy
```

This uses the saved configuration from `samconfig.toml`.

### Step 5: Deploy WebSocket Handler (Optional - Not in Serverless-Only Template)

**NOTE**: The serverless-only template does NOT include the WebSocket handler (ECS Fargate). This is intentional to keep deployment simple and fast (5-10 minutes vs 30+ minutes).

**If you need WebSocket support**, you can deploy it separately later:

```bash
cd websocket_handler

# Build Docker image
docker build -t agenticai-websocket:latest .

# Tag for ECR
aws ecr create-repository --repository-name agenticai-websocket
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com

docker tag agenticai-websocket:latest $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com/agenticai-websocket:latest

# Push to ECR
docker push $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com/agenticai-websocket:latest

# Deploy ECS service (using provided script)
./deploy.sh
```

Or use the PowerShell script on Windows:
```powershell
.\deploy.ps1
```

**For most use cases, the REST API (included in serverless-only) is sufficient.**

## Verification

### Step 1: Get Stack Outputs

Retrieve important endpoints and resource names:

```bash
aws cloudformation describe-stacks \
    --stack-name agenticai-stack \
    --query 'Stacks[0].Outputs' \
    --output table
```

Expected outputs:
- `ApiEndpoint`: REST API URL
- `DataTableName`: DynamoDB table name
- `CodeBucketName`: S3 bucket name
- `DevQueueUrl`: Dev agent SQS queue URL
- (and others)

### Step 2: Test API Endpoints

```bash
# Get API endpoint
export API_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name agenticai-stack \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
    --output text)

# Test health check
curl $API_ENDPOINT/health

# Expected response:
# {"status":"healthy","timestamp":"2025-11-25T..."}

# Test project creation
curl -X POST $API_ENDPOINT/api/projects \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Test Project",
        "type": "api",
        "description": "Test deployment"
    }'

# Expected response:
# {"success":true,"project":{"id":"proj_...","name":"Test Project",...}}
```

### Step 3: Verify Lambda Functions

```bash
# List Lambda functions
aws lambda list-functions \
    --query 'Functions[?starts_with(FunctionName, `agenticai`)].FunctionName' \
    --output table

# Test a Lambda function directly
aws lambda invoke \
    --function-name agenticai-stack-ApiHandler-XXXXX \
    --payload '{"httpMethod":"GET","path":"/health"}' \
    response.json

cat response.json
```

### Step 4: Verify DynamoDB Table

```bash
# Describe table
aws dynamodb describe-table \
    --table-name agenticai-data \
    --query 'Table.[TableName,TableStatus,ItemCount,TableSizeBytes]' \
    --output table

# List items (should be empty initially)
aws dynamodb scan \
    --table-name agenticai-data \
    --max-items 10
```

### Step 5: Verify SQS Queues

```bash
# List queues
aws sqs list-queues \
    --queue-name-prefix agenticai

# Get queue attributes
aws sqs get-queue-attributes \
    --queue-url $(aws sqs get-queue-url --queue-name agenticai-dev-queue --query 'QueueUrl' --output text) \
    --attribute-names All
```

### Step 6: Run Deployment Verification

**Option 1: Quick Manual Verification (Recommended)**

```bash
# Get API endpoint
export API_ENDPOINT=$(aws cloudformation describe-stacks --stack-name agenticai-stack --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' --output text)

echo "Your API Endpoint: $API_ENDPOINT"

# Test health endpoint
curl $API_ENDPOINT/health

# Expected: {"success": true, "status": "healthy", "timestamp": "...", "service": "api-handler"}

# Test project creation
curl -X POST $API_ENDPOINT/api/projects \
    -H "Content-Type: application/json" \
    -d '{"name":"Test Project","type":"api","description":"Verification test"}'

# Expected: {"success":true,"project":{"PK":"PROJECT#proj_...","name":"Test Project",...}}
```

**Windows PowerShell**:
```powershell
# Get API endpoint
$API_ENDPOINT = aws cloudformation describe-stacks --stack-name agenticai-stack --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' --output text

Write-Host "Your API Endpoint: $API_ENDPOINT"

# Test health endpoint
curl $API_ENDPOINT/health

# Test project creation
curl -Method POST -Uri "$API_ENDPOINT/api/projects" `
    -Headers @{"Content-Type"="application/json"} `
    -Body '{"name":"Test Project","type":"api","description":"Verification test"}'
```

**✅ Success Indicators**:
- Health endpoint returns `200 OK` with `"status": "healthy"`
- Project creation returns `201 Created` with project details
- Project is stored in DynamoDB (check with `aws dynamodb scan --table-name agenticai-data`)

**Option 2: Automated Verification Script**

```bash
# Run deployment verification script
python scripts/verify_deployment.py
```

Expected output:
```
✓ API Gateway is accessible
✓ Lambda functions are deployed
✓ DynamoDB table exists
✓ SQS queues are configured
✓ S3 bucket is accessible
✓ CloudWatch logs are configured
All checks passed!
```

**Option 3: Run Tests (Optional)**

**⚠️ Note**: If you encounter SSL certificate errors on Windows, this is a local Python SSL configuration issue and does NOT affect your deployed AWS infrastructure. Your deployment is working fine - the SSL errors only block local pytest from connecting to AWS APIs.

```bash
# Run Lambda-specific tests
pytest tests/test_lambda_api_handler.py -v
pytest tests/test_lambda_agent_workers.py -v

# Run DynamoDB adapter tests
pytest tests/test_dynamodb_adapters.py -v

# Skip deployment verification tests if SSL errors occur
# (Your deployment is verified via manual testing above)
```

**If you see SSL errors**: Your AWS deployment is working correctly. The SSL certificate verification errors are a Windows Python configuration issue that only affects local testing, not your production API.



**Solution**:
- Check if API key is required
- Verify CORS configuration
- Check Lambda execution role permissions

#### Issue 6: WebSocket Connection Fails

**Error**: `WebSocket connection failed`

**Solution**:
- Verify ECS service is running:
```bash
aws ecs list-services --cluster agenticai-cluster
aws ecs describe-services --cluster agenticai-cluster --services agenticai-websocket
```
- Check security group allows inbound traffic on port 8080
- View ECS logs:
```bash
aws logs tail /ecs/agenticai-websocket --follow
```

#### Issue 7: Parameter Store Access Denied

**Error**: `AccessDeniedException: User is not authorized to perform: ssm:GetParameter`

**Solution**:
- Add SSM permissions to Lambda execution role
- Verify parameter exists:
```bash
aws ssm get-parameter --name "/agenticai/gemini-api-key"
```

#### Issue 8: S3 Bucket Already Exists

**Error**: `agenticai-generated-code already exists`

**Solution**:
- Bucket names must be globally unique
- Update bucket name in `template.yaml`:
```yaml
CodeBucket:
  Type: AWS::S3::Bucket
  Properties:
    BucketName: !Sub 'agenticai-code-${AWS::AccountId}'
```

#### Issue 9: Deployment Stuck or Taking Too Long

**Symptoms**:
- Deployment has been running for 30+ minutes
- Stack stuck on `CREATE_IN_PROGRESS` for VPC, ECS, or ALB resources
- Resources like `WebSocketService`, `WebSocketALB`, or `WebSocketListener` are being created

**Root Cause**: You're using a template with VPC/ECS resources instead of the serverless-only template.

**Solution**:

1. **Cancel the stuck deployment**:
```bash
# In AWS Console, go to CloudFormation → Stacks → agenticai-stack → Delete
# OR via CLI:
aws cloudformation delete-stack --stack-name agenticai-stack --region us-east-1

# Wait for deletion (may take 10-15 minutes)
aws cloudformation wait stack-delete-complete --stack-name agenticai-stack --region us-east-1
```

2. **Verify you're using the serverless-only template**:
```bash
# Check if template has VPC/ECS resources
grep -E "VPC|ECS|LoadBalancer" template.yaml

# If found, you need the simplified template
```

3. **Use the simplified serverless-only template** (no VPC/ECS):
   - The correct template should only have: Lambda, API Gateway, DynamoDB, SQS, S3, IAM
   - Should NOT have: VPC, ECS, ALB, Fargate, Container definitions
   - Deployment time: 5-10 minutes (not 30+ minutes)

4. **Redeploy with correct template**:
```bash
# Clear build cache
rm -rf .aws-sam

# Rebuild and deploy
sam build
sam deploy
```

**Prevention**:
- Always validate template before deploying: `sam validate`
- Check resource count: serverless-only should have ~15-20 resources, not 50+
- Monitor deployment: if it takes >15 minutes, something is wrong

### Debugging Commands

```bash
# View CloudFormation stack events
aws cloudformation describe-stack-events \
    --stack-name agenticai-stack \
    --max-items 20

# View Lambda function configuration
aws lambda get-function-configuration \
    --function-name agenticai-stack-ApiHandler-XXXXX

# View Lambda function logs
aws logs tail /aws/lambda/agenticai-stack-ApiHandler-XXXXX --since 1h

# Test Lambda function locally
sam local invoke ApiHandler -e events/test-event.json

# Start local API Gateway
sam local start-api

# View DynamoDB table items
aws dynamodb scan --table-name agenticai-data --max-items 10

# Check SQS queue depth
aws sqs get-queue-attributes \
    --queue-url YOUR_QUEUE_URL \
    --attribute-names ApproximateNumberOfMessages

# View CloudWatch metrics
aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Invocations \
    --dimensions Name=FunctionName,Value=agenticai-stack-ApiHandler-XXXXX \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Sum
```

### Getting Help

1. **Check CloudWatch Logs**: Most issues are logged here
2. **Review SAM Documentation**: https://docs.aws.amazon.com/serverless-application-model/
3. **AWS Support**: Use AWS Support Center (free tier includes basic support)
4. **GitHub Issues**: Report bugs or ask questions in the repository
5. **AWS Forums**: https://forums.aws.amazon.com/

### Clean Up (Delete All Resources)

If you need to delete everything:

```bash
# Delete CloudFormation stack
aws cloudformation delete-stack --stack-name agenticai-stack

# Wait for deletion to complete
aws cloudformation wait stack-delete-complete --stack-name agenticai-stack

# Delete S3 buckets (must be empty first)
aws s3 rm s3://agenticai-generated-code --recursive
aws s3 rb s3://agenticai-generated-code

aws s3 rm s3://agenticai-sam-artifacts-ACCOUNT_ID --recursive
aws s3 rb s3://agenticai-sam-artifacts-ACCOUNT_ID

# Delete Parameter Store parameters
aws ssm delete-parameter --name "/agenticai/gemini-api-key"
aws ssm delete-parameter --name "/agenticai/jwt-secret"
aws ssm delete-parameter --name "/agenticai/github-token"

# Delete ECR repository
aws ecr delete-repository --repository-name agenticai-websocket --force

# Delete ECS cluster
aws ecs delete-cluster --cluster agenticai-cluster
```

## Next Steps

After successful deployment:

1. **Set Up CloudWatch Monitoring** (Recommended First Step):
   ```bash
   # Create comprehensive monitoring dashboard
   python scripts/setup_cloudwatch_dashboard.py
   
   # Verify dashboard configuration
   python scripts/test_cloudwatch_dashboard.py
   ```
   
   See [CloudWatch Dashboard Setup Guide](./CLOUDWATCH_DASHBOARD_SETUP.md) for detailed instructions.

2. **Update Template Outputs** (if verification shows missing outputs):
   ```bash
   # Redeploy with updated outputs
   sam build && sam deploy
   ```

3. **Review Operations Runbook**: See `AWS_OPERATIONS_RUNBOOK.md` for day-to-day operations

4. **Review API Documentation**: See `AWS_API_REFERENCE.md` for API usage

5. **Enable Cost Tracking**: Monitor usage to stay within free tier
   ```bash
   python scripts/monitor_cost_limits.py
   ```

6. **Test End-to-End**: Create a test project and verify all functionality
   ```bash
   # Get API endpoint
   export API_ENDPOINT=$(aws cloudformation describe-stacks --stack-name agenticai-stack --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' --output text)
   
   # Create test project
   curl -X POST $API_ENDPOINT/api/projects \
       -H "Content-Type: application/json" \
       -d '{"name":"Test Project","type":"api","description":"End-to-end test"}'
   ```

7. **Production Hardening** (For production deployments):
   - Set up error alerting (Task 2)
   - Implement API authentication (Task 5)
   - Enable backups and recovery (Task 6)
   - Configure security hardening (Task 7)
   
   See `.kiro/specs/production-hardening/` for the complete production hardening plan.

## Additional Resources

- [AWS Free Tier Details](https://aws.amazon.com/free/)
- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
- [API Gateway Documentation](https://docs.aws.amazon.com/apigateway/)
- [Project Repository](https://github.com/your-org/agenticai-system)
