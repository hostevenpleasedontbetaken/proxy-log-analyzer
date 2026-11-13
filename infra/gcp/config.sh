# Shared settings for the deploy scripts (sourced, not run).
PROJECT="${PROJECT:-tenex-log-analyzer-f42ca}"
REGION="us-east1"            # near Neon's aws-us-east-1; a Cloud Run free-tier region
SITE="${SITE:-proxy-log-analyzer}"   # Firebase Hosting site (public URL: https://$SITE.web.app)
REPO="tenex"                 # Artifact Registry repository for the API image
RUNNER="api-runner@$PROJECT.iam.gserviceaccount.com"
SECRET_POOLED="neon-database-url"          # app traffic, through Neon's connection pooler
SECRET_DIRECT="neon-database-url-direct"   # migrations, which need a direct session
