#!/usr/bin/env bash
set -e

# End-to-End Deployment Script for AIFoundryAgent-ANF-SelfOps
# Deploys ANF via Bicep, then creates AI Foundry components via CLI

if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <subscription-id> <resource-group> <location>"
    echo "Example: $0 xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx anf-selfops-rg eastus2"
    exit 1
fi

SUB_ID=$1
RG_NAME=$2
LOCATION=$3

# Naming conventions (using random string to ensure global uniqueness)
SUFFIX=$(LC_ALL=C tr -dc 'a-z0-9' < /dev/urandom | head -c 5)
AOAI_NAME="anfselfops-aoai-${SUFFIX}"
HUB_NAME="anfselfops-hub-${SUFFIX}"
PROJECT_NAME="anfselfops-project-${SUFFIX}"

az account set --subscription "$SUB_ID"

echo "======================================================"
echo "1. Creating Resource Group: $RG_NAME in $LOCATION"
echo "======================================================"
az group create --name "$RG_NAME" --location "$LOCATION" -o none

echo "======================================================"
echo "1.5 Registering Resource Providers"
echo "======================================================"
az provider register --namespace Microsoft.NetApp --wait
az provider register --namespace Microsoft.MachineLearningServices --wait
az provider register --namespace Microsoft.CognitiveServices --wait

echo "======================================================"
echo "2. Deploying Base Infrastructure (VNet, ANF, Identity) via Bicep"
echo "======================================================"
DEPLOYMENT_OUTPUT=$(az deployment group create \
    --resource-group "$RG_NAME" \
    --template-file infra/main.bicep \
    --parameters infra/parameters.json -o json)

BICEP_ANF_ACCOUNT_NAME=$(echo "$DEPLOYMENT_OUTPUT" | jq -r '.properties.outputs.anfAccountName.value')
BICEP_ANF_POOL_NAME=$(echo "$DEPLOYMENT_OUTPUT" | jq -r '.properties.outputs.poolName.value')

echo "======================================================"
echo "3. Creating Azure OpenAI Resource: $AOAI_NAME"
echo "======================================================"
az cognitiveservices account create \
    --name "$AOAI_NAME" \
    --resource-group "$RG_NAME" \
    --location "$LOCATION" \
    --kind OpenAI \
    --sku S0 \
    --custom-domain "$AOAI_NAME" -o none

echo "Deploying GPT-4o model..."
az cognitiveservices account deployment create \
    --name "$AOAI_NAME" \
    --resource-group "$RG_NAME" \
    --deployment-name gpt-4o \
    --model-name gpt-4o \
    --model-version 2024-05-13 \
    --model-format OpenAI \
    --sku-name "Standard" \
    --sku-capacity 50 -o none

echo "======================================================"
echo "4. Creating AI Foundry Hub and Project"
echo "======================================================"
# Create Hub (Workspace)
az ml workspace create \
    --name "$HUB_NAME" \
    --resource-group "$RG_NAME" \
    --location "$LOCATION" \
    --kind hub -o none

# Create Project linked to the Hub
az ml workspace create \
    --name "$PROJECT_NAME" \
    --resource-group "$RG_NAME" \
    --location "$LOCATION" \
    --kind project \
    --hub-id "/subscriptions/$SUB_ID/resourceGroups/$RG_NAME/providers/Microsoft.MachineLearningServices/workspaces/$HUB_NAME" -o none

echo "======================================================"
echo "5. Connecting Azure OpenAI to AI Foundry Hub"
echo "======================================================"
AOAI_ID="/subscriptions/$SUB_ID/resourceGroups/$RG_NAME/providers/Microsoft.CognitiveServices/accounts/$AOAI_NAME"
AOAI_ENDPOINT=$(az cognitiveservices account show --name "$AOAI_NAME" --resource-group "$RG_NAME" --query "properties.endpoint" -o tsv)
echo "AOAI endpoint: $AOAI_ENDPOINT"

# Create connection via YAML — the CLI --set approach is unreliable for AOAI connections.
# Key findings from testing:
#   - auth_type must be AAD (not api_key) to use DefaultAzureCredential
#   - target must be the ARM resource ID (not the endpoint URL)
#   - The Foundry Agents SDK resolves the AOAI endpoint from the ARM resource ID
cat << EOF > aoai-connection.yml
name: aoai-connection
type: azure_open_ai
target: $AOAI_ID
auth_type: aad
EOF
az ml connection create --file aoai-connection.yml --workspace-name "$HUB_NAME" --resource-group "$RG_NAME" -o none
rm -f aoai-connection.yml
echo "AOAI connection created (AAD auth, ARM resource ID target)."

echo "======================================================"
echo "6. Resolving AI Foundry Project Endpoint"
echo "======================================================"
# Resolve the project endpoint for the Agents SDK (azure-ai-projects 1.0.0 / azure-ai-agents 1.1.0)
# For hub-based projects, the SDK accepts a connection string in the format:
#   <region>.api.azureml.ms;<subscription>;<resourceGroup>;<projectName>
# The foundry_agent.py code detects the semicolon-delimited format and enables
# legacy mode (AZURE_AI_AGENTS_TESTS_IS_TEST_RUN=True) for proper auth scopes.
DISCOVERY_URL=$(az resource show \
    --ids "/subscriptions/$SUB_ID/resourceGroups/$RG_NAME/providers/Microsoft.MachineLearningServices/workspaces/$PROJECT_NAME" \
    --query "properties.discoveryUrl" -o tsv)
# Extract region base URL (e.g., eastus2.api.azureml.ms)
BASE_HOST=$(echo "$DISCOVERY_URL" | sed -E 's|https://([^/]+).*|\1|' | sed 's|/discovery||')
# Connection string format: region;subscription;resourceGroup;projectName
PROJECT_ENDPOINT="${BASE_HOST};${SUB_ID};${RG_NAME};${PROJECT_NAME}"
echo "Resolved project endpoint (connection string): $PROJECT_ENDPOINT"

echo "======================================================"
echo "6.5 Assigning RBAC — Cognitive Services OpenAI Contributor"
echo "======================================================"
# The agent needs OpenAI Assistants write permission on the AOAI resource.
# Assign to the current logged-in user's principal.
CURRENT_USER_OID=$(az ad signed-in-user show --query id -o tsv 2>/dev/null || true)
if [ -n "$CURRENT_USER_OID" ]; then
    az role assignment create \
        --assignee-object-id "$CURRENT_USER_OID" \
        --assignee-principal-type User \
        --role "Cognitive Services OpenAI Contributor" \
        --scope "/subscriptions/$SUB_ID/resourceGroups/$RG_NAME/providers/Microsoft.CognitiveServices/accounts/$AOAI_NAME" \
        -o none 2>/dev/null || echo "Role assignment may already exist — continuing."
    echo "Assigned Cognitive Services OpenAI Contributor to current user."
else
    echo "WARNING: Could not determine current user OID. Manually assign 'Cognitive Services OpenAI Contributor' on the AOAI resource."
fi

echo "======================================================"
echo "7. Outputting Recommended .env Configuration"
echo "======================================================"
cat << EOF > .env.generated
AZURE_SUBSCRIPTION_ID="$SUB_ID"
ANF_RESOURCE_GROUP="$RG_NAME"
ANF_ACCOUNT_NAME="$BICEP_ANF_ACCOUNT_NAME"
ANF_POOL_NAME="$BICEP_ANF_POOL_NAME"
MODEL_DEPLOYMENT_NAME="gpt-4o"
AZURE_AI_PROJECT_ENDPOINT="$PROJECT_ENDPOINT"
EOF

echo "Deployment complete! Your configuration has been saved to .env.generated"
echo "Please review the file and rename it to .env: mv .env.generated .env"
