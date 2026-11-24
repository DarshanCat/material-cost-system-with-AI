# Auto-deploy MMS from GitHub (Cloud Build trigger)

Pushing to `main` builds the image, runs migrations, then rolls out the new revision
(`cloudbuild.deploy.yaml`). If migrations fail, the live service is left unchanged.

One-time setup (project `vspl-mms-prod`):
1. Cloud Build > Repositories > link `DarshanCat/material-cost-system-with-AI` (GitHub approval in browser).
2. Cloud Build > Triggers > Create: event = push to branch `^main$`, config = `cloudbuild.deploy.yaml`.
3. Give the build service account these roles: Cloud Run Admin, Service Account User,
   Artifact Registry Writer.
4. Rollback: Cloud Run > vspl-mms > Revisions > route 100% traffic to the previous revision.
   Migrations are not rolled back automatically.
Note: MES and the other systems are separate and are not covered by this trigger.
