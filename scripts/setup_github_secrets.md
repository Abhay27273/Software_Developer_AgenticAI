# GitHub Secrets Setup Guide

## Why You Need This

GitHub Actions needs AWS credentials to deploy your app automatically on every push to `main` branch.

## Steps

### 1. Get Your AWS Credentials

You should already have these from your IAM user setup:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

If you don't have them, create a new IAM user:

```bash
# Create IAM user for GitHub Actions
aws iam create-user --user-name github-actions-deployer

# Attach required policies
aws iam attach-user-policy \
    --user-name github-actions-deployer \
    --policy-arn arn:aws:iam::aws:policy/AWSLambda_FullAccess

aws iam attach-user-policy \
    --user-name github-actions-deployer \
    --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

aws iam attach-user-policy \
    --user-name github-actions-deployer \
    --policy-arn arn:aws:iam::aws:policy/AWSCloudFormationFullAccess

# Create access key
aws iam create-access-key --user-name github-actions-deployer
```

### 2. Add Secrets to GitHub

1. **Go to your GitHub repository**
   ```
   https://github.com/YOUR_USERNAME/YOUR_REPO
   ```

2. **Navigate to Settings**
   - Click "Settings" tab
   - Click "Secrets and variables" → "Actions"

3. **Add New Repository Secret**
   - Click "New repository secret"
   
4. **Add AWS_ACCESS_KEY_ID**
   - Name: `AWS_ACCESS_KEY_ID`
   - Value: Your AWS access key ID
   - Click "Add secret"

5. **Add AWS_SECRET_ACCESS_KEY**
   - Click "New repository secret" again
   - Name: `AWS_SECRET_ACCESS_KEY`
   - Value: Your AWS secret access key
   - Click "Add secret"

### 3. Verify Setup

Your secrets should look like this:

```
Repository secrets (2)
├── AWS_ACCESS_KEY_ID
└── AWS_SECRET_ACCESS_KEY
```

### 4. Test CI/CD

```bash
# Make a small change
echo "# Test CI/CD" >> README.md

# Commit and push
git add README.md
git commit -m "test: trigger CI/CD pipeline"
git push origin main
```

### 5. Monitor Deployment

1. Go to your GitHub repository
2. Click "Actions" tab
3. You should see a workflow running
4. Click on it to see deployment progress

### Expected Workflow

```
✓ Run Tests (2-3 minutes)
✓ Build SAM Application (3-5 minutes)
✓ Deploy to AWS (5-10 minutes)
✓ Run Verification Tests (1-2 minutes)
```

Total time: ~15-20 minutes for first run

### Troubleshooting

**Workflow fails with "AccessDenied"**:
- Check secrets are named exactly: `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`
- Verify IAM user has required permissions

**Workflow doesn't trigger**:
- Check `.github/workflows/deploy.yml` exists
- Verify you pushed to `main` branch
- Check workflow file syntax

**Build fails**:
- Check `template.yaml` is valid
- Run `sam validate` locally first

## What Happens After Setup

Every time you push to `main`:
1. ✅ Tests run automatically
2. ✅ SAM builds your Lambda functions
3. ✅ Deploys to AWS
4. ✅ Runs verification tests
5. ✅ Updates your live application

**No manual deployment needed!** 🎉
