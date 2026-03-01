// ============================================================
// ANF Foundry SelfOps — Infrastructure as Code (Bicep)
// ============================================================
// Deploys:
//   1. Azure NetApp Files account, capacity pool, and sample volume
//   2. Azure AI Foundry project with model deployment
//   3. User-Assigned Managed Identity with RBAC assignments
//
// Usage:
//   az deployment group create \
//     --resource-group <rg-name> \
//     --template-file infra/main.bicep \
//     --parameters infra/parameters.json
// ============================================================

targetScope = 'resourceGroup'

// ── Parameters ──────────────────────────────────────────────

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Base name prefix for all resources')
param baseName string = 'anfselfops'

@description('ANF capacity pool size in TiB')
@minValue(4)
param poolSizeTiB int = 4

@description('ANF volume size in GiB')
@minValue(100)
param volumeSizeGiB int = 1024

@description('ANF service level')
@allowed(['Standard', 'Premium', 'Ultra'])
param serviceLevel string = 'Premium'

@description('VNet address prefix')
param vnetAddressPrefix string = '10.0.0.0/16'

@description('ANF delegated subnet prefix')
param anfSubnetPrefix string = '10.0.1.0/24'

@description('AI model deployment name')
param modelDeploymentName string = 'gpt-4o'

// ── Variables ───────────────────────────────────────────────

var uniqueSuffix = uniqueString(resourceGroup().id)
var anfAccountName = '${baseName}-anf-${uniqueSuffix}'
var poolName = 'pool-${serviceLevel}'
var volumeName = 'vol-sample-data'
var vnetName = '${baseName}-vnet'
var anfSubnetName = 'anf-delegated'
var managedIdentityName = '${baseName}-identity'

// ── Networking ──────────────────────────────────────────────

resource vnet 'Microsoft.Network/virtualNetworks@2024-01-01' = {
  name: vnetName
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [vnetAddressPrefix]
    }
    subnets: [
      {
        name: anfSubnetName
        properties: {
          addressPrefix: anfSubnetPrefix
          delegations: [
            {
              name: 'anfDelegation'
              properties: {
                serviceName: 'Microsoft.NetApp/volumes'
              }
            }
          ]
        }
      }
    ]
  }
}

// ── Azure NetApp Files ──────────────────────────────────────

resource anfAccount 'Microsoft.NetApp/netAppAccounts@2024-07-01' = {
  name: anfAccountName
  location: location
  properties: {}
}

resource capacityPool 'Microsoft.NetApp/netAppAccounts/capacityPools@2024-07-01' = {
  parent: anfAccount
  name: poolName
  location: location
  properties: {
    serviceLevel: serviceLevel
    size: poolSizeTiB * 1099511627776 // Convert TiB to bytes
  }
}

resource volume 'Microsoft.NetApp/netAppAccounts/capacityPools/volumes@2024-07-01' = {
  parent: capacityPool
  name: volumeName
  location: location
  properties: {
    creationToken: volumeName
    serviceLevel: serviceLevel
    usageThreshold: volumeSizeGiB * 1073741824 // Convert GiB to bytes
    subnetId: vnet.properties.subnets[0].id
    protocolTypes: ['NFSv4.1']
    snapshotDirectoryVisible: true
    exportPolicy: {
      rules: [
        {
          ruleIndex: 1
          unixReadOnly: false
          unixReadWrite: true
          allowedClients: '0.0.0.0/0'
          nfsv41: true
          nfsv3: false
        }
      ]
    }
  }
}

// ── Managed Identity + RBAC ─────────────────────────────────

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: managedIdentityName
  location: location
}

// Contributor on ANF account (for management operations)
resource anfRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(anfAccount.id, managedIdentity.id, 'Contributor')
  scope: anfAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c') // Contributor
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ── Outputs ─────────────────────────────────────────────────

output anfAccountName string = anfAccount.name
output poolName string = capacityPool.name
output volumeName string = volume.name
output managedIdentityClientId string = managedIdentity.properties.clientId
output managedIdentityPrincipalId string = managedIdentity.properties.principalId
output vnetId string = vnet.id

// NOTE: AI Foundry project deployment is commented out below.
// Foundry projects are typically created via the portal or CLI
// as the Bicep resource provider for Foundry is evolving.
// Use this command after deploying the above:
//
//   az ml workspace create \
//     --name "${baseName}-foundry" \
//     --resource-group <rg> \
//     --kind "project" \
//     --hub-id <hub-resource-id>
