# Deployment

## Streamlit Community Cloud (dashboard)
1. Push this repository to GitHub.
2. https://share.streamlit.io → *New app* → pick the repo, branch `main`, main file `streamlit_app.py`.
3. The first start trains the model automatically (about 10 s). Streamlit Cloud has no persistent
   disk, so the **Live** tab needs an external PostgreSQL: add `DATABASE_URL` under *Advanced settings →
   Secrets* (`DATABASE_URL = "postgresql://…"`). Managed free tiers (Neon, Supabase, Azure, AWS RDS) work.
4. Redeploys happen automatically on every push to `main`.

## GitHub Actions
| Workflow | Trigger | Does |
|---|---|---|
| `ci.yml` | push, pull request | ruff, pytest with coverage, Docker build and smoke test |
| `publish-image.yml` | tag `v*` or manual | pushes the image to `ghcr.io/<owner>/<repo>` |
| `deploy-azure.yml` | manual | builds in Azure Container Registry, updates the Web App |
| `deploy-aws.yml` | manual | pushes to ECR, triggers App Runner deployment |

Create the secrets and variables each deploy workflow lists at the top of its file
(*Settings → Secrets and variables → Actions*).

## Azure
```bash
az login
AZ_ACR=aurumacr123 AZ_APP=aurum-parking-123 MQTT_HOST=... bash infra/azure/deploy.sh
```
Creates a resource group, container registry and Linux Web App for Containers (port 8501).
For PostgreSQL use *Azure Database for PostgreSQL – Flexible Server* and set `DATABASE_URL`.

## AWS
```bash
aws configure
bash infra/aws/deploy.sh
```
Creates an ECR repository and an App Runner service. Create the IAM role `AppRunnerECRAccessRole`
(policy `AWSAppRunnerServicePolicyForECRAccess`) once beforehand. For PostgreSQL use RDS.

## Running the whole pipeline in the cloud
Run `ingest` as a second container (same image, command `python -m aurum.ingest`) on Azure Container
Apps / AWS ECS, pointed at HiveMQ or EMQX Cloud and a managed PostgreSQL. Grafana Cloud can read the same
database.
