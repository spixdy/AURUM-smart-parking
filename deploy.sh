#!/usr/bin/env bash
# One-time AWS setup: ECR repository + App Runner service for the Streamlit container.
# Prereqs: AWS CLI configured (`aws configure`), Docker. Not executed in the authoring sandbox: review first.
set -euo pipefail
: "${AWS_REGION:=ap-south-1}"
: "${ECR_REPO:=aurum}"
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REGISTRY="$ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com"

aws ecr describe-repositories --repository-names "$ECR_REPO" --region "$AWS_REGION" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "$ECR_REPO" --region "$AWS_REGION"
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$REGISTRY"
docker build -t "$REGISTRY/$ECR_REPO:latest" .
docker push "$REGISTRY/$ECR_REPO:latest"

# App Runner needs an access role that can pull from ECR (create once in IAM: AppRunnerECRAccessRole).
ROLE_ARN="arn:aws:iam::$ACCOUNT:role/AppRunnerECRAccessRole"
aws apprunner create-service --region "$AWS_REGION" --service-name aurum-parking \
  --source-configuration "{
    \"ImageRepository\": {\"ImageIdentifier\": \"$REGISTRY/$ECR_REPO:latest\", \"ImageRepositoryType\": \"ECR\",
      \"ImageConfiguration\": {\"Port\": \"8501\"}},
    \"AuthenticationConfiguration\": {\"AccessRoleArn\": \"$ROLE_ARN\"}, \"AutoDeploymentsEnabled\": false}"
