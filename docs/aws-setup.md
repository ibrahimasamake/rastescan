# AWS setup (about 1 hour)

Everything in **Asia Pacific (Mumbai) ap-south-1** unless Nova is not offered there for your account; then use the
region Bedrock shows it in and set `AWS_REGION` and `BEDROCK_MODEL_ID` to match.

## 1. Protect the credit (5 min)
Billing → Budgets → Create budget → Monthly cost budget of $50 with alerts at $10, $25 and $40 to your email.

## 2. Turn on Amazon Nova in Bedrock (5 min)
Bedrock console → Model access (or Model catalog) → enable **Nova Pro** and **Nova Lite**.
Note the **inference profile id** shown for Nova Pro (for Mumbai it looks like `apac.amazon.nova-pro-v1:0`).

## 3. S3 bucket for photos (3 min)
S3 → Create bucket → name e.g. `rastescan-photos-<yourname>` → keep "Block all public access" ON.

## 4. IAM role for the server (5 min)
IAM → Policies → Create → JSON → paste `deploy/iam-policy.json` with your bucket name → name `rastescan-server`.
IAM → Roles → Create → AWS service: EC2 → attach `rastescan-server` → name `rastescan-ec2`.
The app never needs AWS keys; it uses this role.

## 5. Access to this private repo from the server (3 min)
Easiest: GitHub → Settings → Developer settings → Fine-grained tokens → token with **read-only Contents** on
`rastescan` only. Clone with `https://<token>@github.com/ibrahimasamake/rastescan.git`.

## 6. EC2 instance (10 min)
EC2 → Launch instance:
- Ubuntu Server 24.04, **64-bit (Arm)**, type **t4g.small**, 20 GB gp3 disk
- Key pair: create one, keep the .pem file safe (never commit it)
- Security group: SSH (22) from **My IP**; Custom TCP **8000** from the CloudFront prefix list
  `com.amazonaws.global.cloudfront.origin-facing` (choose "Prefix list" as source)
- Advanced → IAM instance profile: `rastescan-ec2`

Then:
```bash
ssh -i rastescan.pem ubuntu@<public-ip>
git clone https://<token>@github.com/ibrahimasamake/rastescan.git /tmp/r && bash /tmp/r/deploy/setup-ec2.sh https://<token>@github.com/ibrahimasamake/rastescan.git
sudo nano /etc/rastescan.env      # set S3_BUCKET, DASHBOARD_PIN, BEDROCK_MODEL_ID, AWS_REGION
sudo systemctl restart rastescan
curl localhost:8000/api/health    # should say "ai_mode":"bedrock"
```

## 7. CloudFront for HTTPS (10 min + up to 15 min to deploy)
CloudFront → Create distribution:
- Origin domain: the instance's **Public IPv4 DNS** (ec2-…compute.amazonaws.com), protocol **HTTP only**, port **8000**
- Viewer protocol policy: **Redirect HTTP to HTTPS**
- Allowed methods: **GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE**
- Cache policy: **CachingDisabled**; Origin request policy: **AllViewerExceptHostHeader**
- Response timeout: 60 seconds (the AI can take a few seconds)

The address looks like `https://d1234abcd.cloudfront.net`. Open it on your phone over mobile data and send a report.
Put this address in `web/.env.android` for the Android build.

## 8. Check the AI before the expo
Put 20–30 labelled photos in `test-photos/` with `labels.csv`, then on the server:
```bash
cd /opt/rastescan && sudo -u rastescan env $(cat /etc/rastescan.env | xargs) backend/.venv/bin/python scripts/evaluate.py
```
Try `apac.amazon.nova-lite-v1:0` too; keep Lite if it scores the same.

## Updating after a push to main
```bash
bash /opt/rastescan/deploy/update.sh
```

## Avoid (each one alone can use most of the credit)
NAT gateway, Application Load Balancer, RDS, SageMaker endpoints, an Elastic IP left unattached.
Stop the instance after the expo.
