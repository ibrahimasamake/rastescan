# Deploy to AWS with Terraform and Ansible

Terraform creates the AWS resources. Ansible sets up the server and deploys the app from your checkout.
The only manual step is your own AWS login.

## What gets created (Mumbai, ap-south-1)
| Resource | Why |
|---|---|
| EC2 t4g.small, Ubuntu 24.04 ARM, 20 GB encrypted disk, IMDSv2 only | Runs the API and serves the web app |
| Elastic IP | Fixed address for CloudFront and SSH |
| Security group | SSH only from your IP; port 8000 only from CloudFront |
| CloudFront distribution | Free HTTPS address (phones need it for camera and GPS) |
| S3 bucket (private, encrypted) | Blurred photos |
| IAM role and instance profile | Lets the server call Nova and S3 without any keys |
| AWS Budget ($50, alerts at 20%, 50%, 80%) | Email before the credit runs out |

About $20 a month while running. `make down` deletes all of it.

## One-time setup on your laptop
1. Install Terraform 1.6+, Ansible (`pip install ansible`), Node 20+, rsync and the AWS CLI.
2. Log in to AWS with a user allowed to create the resources above (an admin IAM user is simplest on a student account):
   ```bash
   aws configure
   ```
   Use region `ap-south-1`.
3. Create an SSH key if you don't have one:
   ```bash
   ssh-keygen -t ed25519
   ```
4. Fill in the settings:
   ```bash
   cd infra/terraform
   cp terraform.tfvars.example terraform.tfvars
   ```
   Set `ssh_allowed_cidr` to your IP with `/32` (find it with `curl -s https://checkip.amazonaws.com`) and `budget_email`.
5. Choose the ward dashboard PIN. It stays in your shell, never in git:
   ```bash
   export RASTESCAN_DASHBOARD_PIN=<at least 4 digits>
   ```

## Create and deploy
```bash
cd infra
make up
```
Terraform shows what it will create and asks you to type `yes`. Ansible then:
1. builds the web app on your laptop,
2. copies it with the backend and prompt to the server,
3. installs Python packages and the system service,
4. checks the app runs in Bedrock mode, not test mode,
5. waits until the HTTPS address answers (the first CloudFront deploy takes 10–15 minutes),
6. prints the address.

## Everyday commands (run in `infra/`)
| Command | What it does |
|---|---|
| `make deploy` | Send your current code to the server and restart |
| `make url` | Print the HTTPS address (put it in `web/.env.android`) |
| `make ssh` | Log in to the server; `journalctl -u rastescan -f` shows the logs |
| `make infra` | Apply Terraform changes only |
| `make down` | Delete everything, photos included |
| `make check` | Format and lint checks, no AWS needed |

If your IP changes (new Wi-Fi), update `ssh_allowed_cidr` and run `make infra` before `make deploy`.

## Bedrock access
The server role is allowed to call Amazon Nova. If the first report fails with an access error, open the Bedrock
console in ap-south-1, enable Nova Pro and Nova Lite, and try again.
To switch to Nova Lite, set `bedrock_model_id = "apac.amazon.nova-lite-v1:0"` in `terraform.tfvars`, then:
```bash
make infra deploy
```

## Check the AI before the expo
Put 20–30 labelled photos in `test-photos/` with `labels.csv`, then run the evaluation from your laptop with your
own AWS login:
```bash
cd backend
AWS_REGION=ap-south-1 BEDROCK_MODEL_ID=apac.amazon.nova-pro-v1:0 .venv/bin/python ../scripts/evaluate.py
```
