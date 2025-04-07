# Variables
ENV ?= dev
SERVICE_DIR := budget-bot
INFRA_DIR := infrastructure

check-resource:
	@if [ -z "$(RESOURCE)" ]; then \
		echo "⚠️ ERROR: RESOURCE name is required! Usage: make $@ RESOURCE=<resource_name>"; \
		exit 1; \
	fi

# SAM build and deploy
.PHONY: build deploy
build:
	@echo "Building SAM application for $(ENV)..."
	cd $(SERVICE_DIR) && sam build

deploy: build
	@echo "Deploying SAM application to $(ENV)..."
	cd $(SERVICE_DIR) && sam deploy --config-env $(ENV) --no-confirm-changeset --no-fail-on-empty-changeset

.PHONY: watch run 
run:
	@echo "🔄 Starting SAM..."
	@cd $(SERVICE_DIR) && sam build && sam local start-api
watch:
	@cd $(SERVICE_DIR) && python3 expense_analyzer/watch.py
# needs to update in future based on requirements.
.PHONY: infra-init infra-plan infra-apply infra-lint
infra-init: check-resource
	@echo "Initializing Terraform in $(INFRA_DIR)/$(RESOURCE) ......"
#add backend config when necessary
	cd $(INFRA_DIR)/$(RESOURCE) && terraform init -reconfigure

infra-plan:
	@echo "Planning Terraform plan  $(INFRA_DIR)/$(RESOURCE) ..."
	cd $(INFRA_DIR)/$(RESOURCE) && terraform plan -var-file="$(ENV).tfvars"

infra-apply:
	@echo "Applying Terraform deployment $(INFRA_DIR)/$(RESOURCE)  ..."
	cd $(INFRA_DIR)/$(RESOURCE) && terraform apply -var-file="$(ENV).tfvars"

#infra linting:
infra-lint:
	@echo "🔍 Running Terraform lint..."
	@tflint --recursive || { \
		echo "❌ tflint failed, please fix the issues"; \
		exit 1; \
	}
	@echo "✅ tflint completed successfully!"

# Formatting
.PHONY: format
format:
	@echo "Formatting Terraform and Python code..."
	@echo "Running terraform fmt..."
	@terraform fmt -recursive -check || { \
		echo "❌ terraform fmt failed, please run terraform fmt to fix the errors"; \
		exit 1; \
	}
	@echo "✅ terraform fmt completed successfully!"
	@echo "Formatting service..."
	@echo "Running black for Python formatting..."
	@black --check --quiet $(SERVICE_DIR) || { \
		echo "❌ black formatting failed, please run black to fix the errors"; \
		exit 1; \
	}
	@echo "✅ black formatting completed successfully!"
	@echo "Checking YAML file formats..."
	@yamllint . || { \
    echo "❌ yamllint detected issues, please fix remaining issues manually"; \
    exit 1; \
	}
	@echo "✅ YAML format check completed successfully!"