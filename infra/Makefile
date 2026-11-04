# Run from infra/. Needs: terraform, ansible, aws credentials (aws configure), node 20+.
TF := terraform -chdir=terraform

.PHONY: up infra deploy url ssh down check

up: infra deploy ## Create everything on AWS and deploy the app

infra: ## Create or update AWS resources
	$(TF) init -input=false
	$(TF) apply
	@echo "App address: $$($(TF) output -raw app_url)"

deploy: ## Copy the current code to the server and restart it
	cd ansible && ansible-galaxy collection install -r requirements.yml >/dev/null
	cd ansible && ansible-playbook site.yml

url: ## Print the public HTTPS address
	@$(TF) output -raw app_url; echo

ssh: ## Log in to the server
	ssh ubuntu@$$($(TF) output -raw server_ip)

down: ## Delete everything Terraform created (photos included)
	$(TF) destroy

check: ## Format and lint checks, no AWS needed
	$(TF) fmt -check -recursive
	$(TF) init -backend=false -input=false >/dev/null && $(TF) validate
	cd ansible && ansible-lint site.yml
