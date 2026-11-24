# Google Cloud deployment: plan with Google sign-in (nothing deployed yet)

Updated 2026-11-22. I have **not** created, changed or deployed anything in Google Cloud. The `gcloud` login on this PC (`data.analyst@vijayspheroidals.com`, project `ai-tms-project`) has expired, and I will not sign in for you.

## What this design does
- **One Cloud Run service** serves the API and the web pages from one address, so there is a single door to guard.
- **Identity-Aware Proxy (IAP)** stands in front of it: nobody reaches the app without signing in to Google, and only people on your list can pass.
- **The backend trusts only IAP's signed token**, checks it against Google's published keys, the issuer and this service's audience, and then looks the e-mail up in your **e-mail-to-role list** (Stores, Foundry, Purchase, Management, Admin). An e-mail not on the list gets no access even if it can sign in to Google. The unsigned Google headers are never trusted.
- Extra hardening in the same patch: API documentation pages are off in production, no content sniffing or framing, no caching of API responses, HSTS in production, the built-in development logins refuse to work with any provider other than `dev`, and the service refuses to start if Google sign-in is half configured.
- The database is a **new empty Cloud SQL PostgreSQL**, not your Supabase data.

## What I need from you
1. Run `gcloud auth login` in a terminal and finish the browser sign-in (I cannot do this).
2. A billing account to attach to a **new project** (for example `vspl-mms`). Creating a project and linking billing needs your permission:
   ```
   gcloud projects create <NEW_PROJECT_ID> --name="VSPL MMS"
   gcloud billing projects link <NEW_PROJECT_ID> --billing-account=<BILLING_ACCOUNT_ID>
   ```
3. **The e-mail-to-role list**: each person's company Google e-mail and their one role. The role list decides what each person sees and can do.
4. A decision on **migrations 009 to 012** for the test database (see item 3 under "Still open").

## Steps (to run after the items above; replace placeholders)
```
gcloud config set project <NEW_PROJECT_ID>
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com sqladmin.googleapis.com iap.googleapis.com
gcloud artifacts repositories create vspl-mms --repository-format=docker --location=asia-south1
gcloud sql instances create vspl-mms-db --database-version=POSTGRES_16 --tier=db-f1-micro --region=asia-south1
gcloud sql databases create vspl_mms --instance=vspl-mms-db
gcloud sql users create vspl_app --instance=vspl-mms-db --password=<LONG_RANDOM_PASSWORD>
```
Secrets (values are never stored in files):
```
printf '%s' '<long-random>'                                   | gcloud secrets create vspl-secret-key --data-file=-
printf '%s' 'postgresql+psycopg://vspl_app:<PW>@/vspl_mms?host=/cloudsql/<PROJECT>:asia-south1:vspl-mms-db' | gcloud secrets create vspl-database-url --data-file=-
printf '%s' '["https://<service-url>"]'                       | gcloud secrets create vspl-allowed-origins --data-file=-
printf '%s' '{"a.person@company.com":"Stores","b.person@company.com":"Management"}' | gcloud secrets create vspl-iap-role-map --data-file=-
printf '%s' '/projects/<PROJECT_NUMBER>/locations/asia-south1/services/vspl-mms' | gcloud secrets create vspl-iap-audience --data-file=-
```
Give the Cloud Run service account `roles/secretmanager.secretAccessor` and `roles/cloudsql.client`. Then:
1. Create the schema on the new database (a Cloud SQL Auth Proxy session from a trusted PC, or a one-off Cloud Run job): `alembic upgrade head`.
2. Deploy: `gcloud builds submit --config deploy/google-cloud/cloudbuild.yaml --substitutions _SQL_INSTANCE=<PROJECT>:asia-south1:vspl-mms-db`
3. Let each listed person through IAP: `gcloud iap web add-iam-policy-binding --resource-type=cloud-run --service=vspl-mms --region=asia-south1 --member=user:<email> --role=roles/iap.httpsResourceAccessor` (or bind a Google group).
4. Verify: open the service URL, sign in with a listed account, check `/api/v1/auth/me` shows the right role, try an unlisted Google account (must be refused), and check that `/docs` shows the app, not API documentation.

## Still open (not solved by this plan)
1. **QA-05 and QA-06** governance decisions (what Admin may do; who posts opening balances). The role list lets you decide who is Admin, but the permission rules themselves are still the open decision.
2. **Production database.** This plan creates a test environment on an empty database. Moving the real Supabase data later needs the approved migration plan and a verified backup.
3. **Migrations 009 to 012** are proposed, not approved. Without them the heat and costing screens fail on the new database. For a test database I recommend applying them there; for production they need management approval.
4. **Demo data** is still bundled in the frontend source. A production build compiles out the fallback, but the data file is still shipped in the bundle; remove it before real users.
5. **`frontend/vercel.json`** still forwards `/api` to a laptop tunnel. Remove it when this deployment replaces Vercel.
6. **Hard-coded development passwords** exist in the backend source (`DEV_CREDENTIALS` in `auth.py`). They only work with the development provider, which production refuses; rotate or remove them before any shared development tunnel is used again.
7. **Region and cost.** `asia-south1` and the smallest Cloud SQL tier are assumptions; Cloud SQL and Cloud Run bill by use.
8. Not built: I have not built the image. IAP's direct Cloud Run integration (`--iap`) is available in this `gcloud`, but I could not test it without your project.

## Roll back
```
gcloud run services update-traffic vspl-mms --region asia-south1 --to-revisions <previous-revision>=100
```
A database migration is not undone by this; keep a backup before any schema change on a database that holds real data.

## Files here
`Dockerfile` (API and web pages in one image), `cloudbuild.yaml` (template), `backend.env.example` (names only).
