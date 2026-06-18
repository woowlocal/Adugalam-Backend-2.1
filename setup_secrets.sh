#!/bin/bash
# ============================================================
# setup_secrets.sh
#
# WHERE TO RUN THIS:
#   1. Go to https://shell.cloud.google.com
#   2. Upload this file OR paste contents directly
#   3. Run: bash setup_secrets.sh
#
# This script creates all Google Secret Manager secrets
# and grants the required IAM permissions for Cloud Run.
# Run this ONCE before your first deployment.
# ============================================================

set -e   # Stop on any error

# ── CONFIG ───────────────────────────────────────────────────
PROJECT_ID="$(gcloud config get-value project)"

if [ -z "$PROJECT_ID" ]; then
  echo "❌ No project set. Run: gcloud config set project YOUR_PROJECT_ID"
  exit 1
fi

echo "════════════════════════════════════════════════════════"
echo "🔐 Setting up Secret Manager for project: $PROJECT_ID"
echo "════════════════════════════════════════════════════════"
echo ""

# ── Helper: create secret (skip if already exists) ───────────
create_secret() {
  local NAME=$1
  local VALUE=$2
  if gcloud secrets describe "$NAME" --project="$PROJECT_ID" &>/dev/null; then
    echo "  ⏭  $NAME already exists — skipping"
    # Update the value to latest version
    echo -n "$VALUE" | gcloud secrets versions add "$NAME" --data-file=- --quiet
    echo "     ↳ updated to latest version"
  else
    echo -n "$VALUE" | gcloud secrets create "$NAME" \
      --data-file=- \
      --replication-policy=automatic \
      --project="$PROJECT_ID" \
      --quiet
    echo "  ✅ $NAME created"
  fi
}

# ── SUPABASE / DATABASE ───────────────────────────────────────
echo "📦 Creating database secrets..."
create_secret "db-name"     "postgres"
create_secret "db-user"     "postgres.bnhhwxwdfsccyyxrcvyg"
create_secret "db-password" "Adugalam@123"
create_secret "db-host"     "aws-1-ap-south-1.pooler.supabase.com"
create_secret "supabase-url" "https://bnhhwxwdfsccyyxrcvyg.supabase.co"
create_secret "supabase-key" "sb_publishable_7UPVHrdmc6-D_Te5SM-OVA_Sbs2G95M"

# ── DJANGO ───────────────────────────────────────────────────
echo ""
echo "🔑 Creating Django secrets..."
# Generate a strong secret key automatically
DJANGO_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
create_secret "django-secret-key" "$DJANGO_SECRET"

# ── SMTP / EMAIL ─────────────────────────────────────────────
echo ""
echo "📧 Creating email secrets..."
create_secret "smtp-host" "smtp.gmail.com"
create_secret "smtp-user" "myadugalam@gmail.com"
create_secret "smtp-pass" "bjlq oqhp wnuq utli"

# ── RAZORPAY ─────────────────────────────────────────────────
echo ""
echo "💳 Creating Razorpay secrets..."
create_secret "razorpay-key-id"     "rzp_live_S2qvjT5ZF9ktdQ"
create_secret "razorpay-key-secret" "dewrEebNJvz5tHCtozV01syN"

# ── WHATSAPP ─────────────────────────────────────────────────
echo ""
echo "📱 Creating WhatsApp secrets..."
create_secret "whatsapp-api-url"         "https://103.229.250.150/unified/v2/send"
create_secret "whatsapp-client-id"       "woowlocal5dhn6wxesv14a2m"
create_secret "whatsapp-client-password" "dnud6xluv1uopqss6amv1fxaenv0f56p"
create_secret "whatsapp-from-number"     "916380433385"

echo ""
echo "════════════════════════════════════════════════════════"
echo "🔐 All secrets created. Now granting IAM permissions..."
echo "════════════════════════════════════════════════════════"
echo ""

# ── GET SERVICE ACCOUNT EMAILS ───────────────────────────────
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
CLOUD_BUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
CLOUD_RUN_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

SECRET_NAMES=(
  "db-name" "db-user" "db-password" "db-host"
  "django-secret-key"
  "supabase-url" "supabase-key"
  "smtp-host" "smtp-user" "smtp-pass"
  "razorpay-key-id" "razorpay-key-secret"
  "whatsapp-api-url" "whatsapp-client-id" "whatsapp-client-password" "whatsapp-from-number"
)

echo "Granting Cloud Build SA access to read all secrets..."
for SECRET in "${SECRET_NAMES[@]}"; do
  gcloud secrets add-iam-policy-binding "$SECRET" \
    --member="serviceAccount:${CLOUD_BUILD_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --project="$PROJECT_ID" \
    --quiet
  echo "  ✅ $SECRET → Cloud Build"
done

echo ""
echo "Granting Cloud Run SA access to read all secrets..."
for SECRET in "${SECRET_NAMES[@]}"; do
  gcloud secrets add-iam-policy-binding "$SECRET" \
    --member="serviceAccount:${CLOUD_RUN_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --project="$PROJECT_ID" \
    --quiet
  echo "  ✅ $SECRET → Cloud Run"
done

echo ""
echo "Granting Cloud Build permission to deploy Cloud Run..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${CLOUD_BUILD_SA}" \
  --role="roles/run.admin" --quiet

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${CLOUD_BUILD_SA}" \
  --role="roles/iam.serviceAccountUser" --quiet

echo ""
echo "════════════════════════════════════════════════════════"
echo "✅ ALL DONE! Your environment is fully set up."
echo ""
echo "Next steps:"
echo "  1. git add -A"
echo "  2. git commit -m 'feat: switch to Supabase PostgreSQL'"
echo "  3. git push origin main   ← triggers Cloud Build auto-deploy"
echo ""
echo "After first deploy, run migrations locally:"
echo "  python manage.py migrate"
echo "════════════════════════════════════════════════════════"
