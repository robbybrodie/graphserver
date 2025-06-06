# Graph Visualization GitOps Stack for ROSA

This repository contains a complete GitOps specification for deploying a graph visualization system on Red Hat OpenShift Service on AWS (ROSA) using Argo CD. The stack includes:

- **Neo4j Database**: Graph database for storing and querying graph data
- **Frontend Visualization**: Neovis.js-based web interface for graph visualization
- **OAuth Security**: OpenShift OAuth Proxy for authentication
- **ETL Components**: Automated data ingestion from JIRA and GitHub APIs
- **GitOps Management**: Argo CD for declarative deployment and management

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Argo CD       │───▶│  Graph Stack     │───▶│    Neo4j        │
│   Application   │    │  Deployment      │    │   Database      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │                          ▲
                              ▼                          │
                       ┌──────────────────┐              │
                       │  Frontend +      │              │
                       │  OAuth Proxy     │              │
                       └──────────────────┘              │
                              │                          │
                              ▼                          │
                       ┌──────────────────┐              │
                       │  OpenShift       │              │
                       │  Route           │              │
                       └──────────────────┘              │
                                                         │
┌─────────────────┐    ┌──────────────────┐              │
│   JIRA API      │───▶│  JIRA ETL Job    │──────────────┤
│   (Issues)      │    │  (CronJob)       │              │
└─────────────────┘    └──────────────────┘              │
                                                         │
┌─────────────────┐    ┌──────────────────┐              │
│   GitHub API    │───▶│  GitHub ETL Job  │──────────────┘
│   (Issues/PRs)  │    │  (CronJob)       │
└─────────────────┘    └──────────────────┘
```

## Directory Structure

```
graph-visualisation/
├── applications/
│   ├── graph-stack.yaml              # Argo CD Application for main stack
│   ├── etl-stack.yaml                # Argo CD Application for ETL jobs
│   └── company-integration-stack.yaml # Argo CD Application for company-specific JIRA-GitHub integration
├── company-specific/                  # Company-specific JIRA-GitHub integration (separate for security)
│   ├── schema/
│   │   └── jira-github-integration-schema.cypher
│   ├── etl/
│   │   ├── jira-github-integration/
│   │   └── shared/
│   ├── applications/
│   └── README.md
├── neo4j/
│   ├── kustomization.yaml            # Kustomize configuration
│   └── values.yaml                   # Helm values for Neo4j
├── frontend/
│   ├── Dockerfile                    # NGINX container serving Neovis.js HTML
│   ├── index.html                    # Visualization app (Neovis, etc.)
│   ├── deployment.yaml               # Frontend + OAuth Proxy
│   ├── service.yaml                  # Kubernetes Service
│   └── route.yaml                    # OpenShift Route
├── etl/
│   ├── shared/
│   │   └── configmap.yaml            # Shared ETL configuration and Cypher queries
│   ├── jira/
│   │   ├── cronjob.yaml              # JIRA ETL CronJob
│   │   ├── Dockerfile                # JIRA ETL container
│   │   ├── requirements.txt          # Python dependencies
│   │   └── jira_etl.py               # JIRA ETL script
│   └── github/
│       ├── cronjob.yaml              # GitHub ETL CronJob
│       ├── Dockerfile                # GitHub ETL container
│       ├── requirements.txt          # Python dependencies
│       └── github_etl.py             # GitHub ETL script
└── README.md                         # This file
```

## Prerequisites

### ROSA Cluster Requirements
- **ROSA Cluster**: Version 4.12+ with admin access
- **Machine Pool**: At least 3 worker nodes with 4 vCPU, 16GB RAM each
- **Storage**: Default storage class configured (gp3-csi recommended)
- **Networking**: Cluster must have internet access for container registry pulls

### Required Tools
Install the following tools on your local machine:

```bash
# Install OpenShift CLI
curl -O https://mirror.openshift.com/pub/openshift-v4/clients/ocp/stable/openshift-client-linux.tar.gz
tar -xzf openshift-client-linux.tar.gz
sudo mv oc kubectl /usr/local/bin/

# Install Podman (for container builds)
sudo dnf install -y podman

# Install Git
sudo dnf install -y git

# Install jq (for JSON processing)
sudo dnf install -y jq
```

### Container Registry Access
- **Quay.io Account**: Create account at https://quay.io
- **Registry Credentials**: Generate robot account or use personal credentials
- **Repository Access**: Create repositories for your containers

### API Access Requirements

#### JIRA API Access
- **JIRA Cloud Instance**: Access to Atlassian JIRA Cloud
- **API Token**: Generate from https://id.atlassian.com/manage-profile/security/api-tokens
- **User Email**: Email address associated with JIRA account
- **Project Access**: Read permissions for target JIRA projects

#### GitHub API Access
- **GitHub Account**: Personal or organization account
- **Personal Access Token**: Generate from GitHub Settings > Developer settings > Personal access tokens
- **Required Scopes**: `repo`, `read:org`, `read:user`
- **Organization Access**: Read permissions for target repositories

### Argo CD Installation
If Argo CD is not already installed on your ROSA cluster:

#### 1. Access Your ROSA Cluster

First, you need to connect to your ROSA cluster. There are several ways to do this:

**Option A: Using ROSA CLI (Recommended)**
```bash
# Install ROSA CLI if not already installed
curl -Ls https://mirror.openshift.com/pub/openshift-v4/clients/rosa/latest/rosa-linux.tar.gz | tar xz
sudo mv rosa /usr/local/bin/rosa

# Login to your Red Hat account
rosa login

# List your clusters
rosa list clusters

# Get login command for your cluster
rosa describe cluster YOUR-CLUSTER-NAME --output json | jq -r '.api.url'

# Login using the cluster API URL
oc login https://api.YOUR-CLUSTER-NAME.RANDOM-STRING.p1.openshiftapps.com:6443
```

**Option B: Using OpenShift Console**
```bash
# 1. Go to https://console.redhat.com/openshift
# 2. Select your ROSA cluster
# 3. Click "Open Console" 
# 4. In the OpenShift console, click your username (top right)
# 5. Select "Copy login command"
# 6. Click "Display Token"
# 7. Copy and run the oc login command

# Example of what you'll copy:
oc login --token=sha256~EXAMPLE-TOKEN --server=https://api.YOUR-CLUSTER.p1.openshiftapps.com:6443
```

**Option C: Using Cluster Credentials**
```bash
# If you have cluster admin credentials
oc login -u kubeadmin -p YOUR-KUBEADMIN-PASSWORD https://api.YOUR-CLUSTER.p1.openshiftapps.com:6443
```

#### 2. Verify Cluster Access
```bash
# Verify you're connected to the right cluster
oc whoami
oc cluster-info

# Check your permissions
oc auth can-i create namespace
oc auth can-i create deployment

# List existing projects
oc get projects
```

#### 3. Install Argo CD
```bash
# Create Argo CD namespace
oc create namespace argocd

# Install Argo CD operator
oc apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Create required secrets that are missing from the default installation
# Create Redis secret (required for ArgoCD components)
oc create secret generic argocd-redis --from-literal=auth="" -n argocd

# Generate and add server secret key to argocd-secret
SECRET_KEY=$(openssl rand -base64 32)
oc patch secret argocd-secret -n argocd --type merge -p="{\"data\":{\"server.secretkey\":\"$(echo -n $SECRET_KEY | base64)\"}}"

# Add dex configuration to argocd-cm ConfigMap
oc patch configmap argocd-cm -n argocd --type merge -p='{"data":{"dex.config":"issuer: https://argocd-dex-server.argocd.svc.cluster.local:5556/dex\nstorage:\n  type: memory\nweb:\n  http: 0.0.0.0:5556\nlogger:\n  level: \"debug\"\n  format: text\nconnectors:\n- type: oidc\n  id: oidc\n  name: OpenShift\n  config:\n    issuer: https://kubernetes.default.svc.cluster.local\n    clientID: system:serviceaccount:argocd:argocd-dex-server\n    clientSecret: \"\"\n    requestedScopes: [\"openid\", \"profile\", \"email\", \"groups\"]\n    requestedIDTokenClaims: {\"groups\": {\"essential\": true}}\nstaticClients:\n- id: argo-cd-cli\n  name: \"Argo CD CLI\"\n  public: true\n- id: argo-cd\n  name: \"Argo CD\"\n  secret: \"$2a$10$mivhwttXM0VwgbPLQxcZJOa.ClzGraLqXtx5Mq8gLjHA3wTTILjjK\"\n  redirectURIs:\n  - https://argocd-server/auth/callback"}}'

# Wait for Argo CD to be ready (this may take a few minutes)
oc wait --for=condition=available --timeout=600s deployment/argocd-server -n argocd

# Restart ArgoCD deployments to pick up the new configuration
oc rollout restart deployment/argocd-dex-server -n argocd
oc rollout restart deployment/argocd-server -n argocd
oc rollout restart deployment/argocd-repo-server -n argocd
oc rollout restart statefulset/argocd-application-controller -n argocd

# Wait for all components to be running
echo "Waiting for ArgoCD components to be ready..."
oc wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-dex-server -n argocd --timeout=300s
oc wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-server -n argocd --timeout=300s
oc wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-repo-server -n argocd --timeout=300s
oc wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-application-controller -n argocd --timeout=300s

# Create Argo CD route
oc create route edge argocd-server --service=argocd-server --port=https --insecure-policy=Redirect -n argocd

# Get Argo CD admin password
ARGOCD_PASSWORD=$(oc get secret argocd-initial-admin-secret -n argocd -o jsonpath="{.data.password}" | base64 -d)

# Get the Argo CD URL
ARGOCD_URL="https://$(oc get route argocd-server -n argocd -o jsonpath='{.spec.host}')"

echo "Argo CD URL: $ARGOCD_URL"
echo "Username: admin"
echo "Password: $ARGOCD_PASSWORD"
```

#### 4. Access Argo CD UI
```bash
# Get the Argo CD URL and admin password
ARGOCD_URL="https://$(oc get route argocd-server -n argocd -o jsonpath='{.spec.host}')"
ARGOCD_PASSWORD=$(oc get secret argocd-initial-admin-secret -n argocd -o jsonpath="{.data.password}" | base64 -d)

echo "Argo CD URL: $ARGOCD_URL"
echo "Username: admin"
echo "Password: $ARGOCD_PASSWORD"

# Open in browser (macOS)
open "$ARGOCD_URL"

# Open in browser (Linux)
xdg-open "$ARGOCD_URL"
```

## Deployment Steps

### Step 1: Fork and Clone Repository

```bash
# Fork this repository to your GitHub account
# Then clone your fork
git clone https://github.com/YOUR-USERNAME/graph-visualisation.git
cd graph-visualisation
```

### Step 2: Configure Repository URLs

Update the repository URLs in the Argo CD applications:

```bash
# Update graph-stack application
sed -i 's|https://github.com/myorg/graph-visualisation|https://github.com/YOUR-USERNAME/graph-visualisation|g' applications/graph-stack.yaml

# Update etl-stack application  
sed -i 's|https://github.com/myorg/graph-visualisation|https://github.com/YOUR-USERNAME/graph-visualisation|g' applications/etl-stack.yaml

# Commit changes
git add applications/
git commit -m "Update repository URLs for deployment"
git push origin main
```

### Step 3: Login to ROSA Cluster

```bash
# Login to your ROSA cluster
oc login --token=YOUR-TOKEN --server=https://api.YOUR-CLUSTER.YOUR-REGION.aroapp.io:6443

# Verify cluster access
oc whoami
oc get nodes
```

### Step 4: Create Project Namespace

```bash
# Create the graph-system namespace
oc new-project graph-system

# Set as current project
oc project graph-system
```

### Step 5: Configure Container Registry Access

```bash
# Create registry secret for Quay.io
oc create secret docker-registry quay-registry-secret \
  --docker-server=quay.io \
  --docker-username=YOUR-QUAY-USERNAME \
  --docker-password=YOUR-QUAY-PASSWORD \
  --docker-email=YOUR-EMAIL \
  -n graph-system

# Link secret to default service account
oc secrets link default quay-registry-secret --for=pull -n graph-system
oc secrets link builder quay-registry-secret -n graph-system
```

### Step 6: Create API Credentials Secrets

```bash
# Create JIRA credentials secret
oc create secret generic jira-credentials \
  --from-literal=url=https://YOUR-DOMAIN.atlassian.net \
  --from-literal=username=your-email@company.com \
  --from-literal=api-token=YOUR-JIRA-API-TOKEN \
  -n graph-system

# Create GitHub credentials secret
oc create secret generic github-credentials \
  --from-literal=token=YOUR-GITHUB-PERSONAL-ACCESS-TOKEN \
  -n graph-system

# Create Neo4j auth secret (change password from default)
oc create secret generic neo4j-auth \
  --from-literal=password=YOUR-SECURE-NEO4J-PASSWORD \
  -n graph-system
```

### Step 7: Update Configuration Files

Update the ETL configuration with your specific settings:

```bash
# Update JIRA projects in cronjob
sed -i 's/AAP,PLATFORM,DEVOPS/YOUR-PROJECT-1,YOUR-PROJECT-2,YOUR-PROJECT-3/g' etl/jira/cronjob.yaml

# Update GitHub organization and repositories
sed -i 's/myorg/YOUR-GITHUB-ORG/g' etl/github/cronjob.yaml
sed -i 's/repo1,repo2,repo3/YOUR-REPO-1,YOUR-REPO-2,YOUR-REPO-3/g' etl/github/cronjob.yaml

# Update container registry references
find . -name "*.yaml" -exec sed -i 's/quay.io\/myorg/quay.io\/YOUR-QUAY-USERNAME/g' {} \;

# Update Neo4j password in values.yaml
sed -i 's/changeme/YOUR-SECURE-NEO4J-PASSWORD/g' neo4j/values.yaml

# Commit configuration changes
git add .
git commit -m "Update configuration for deployment"
git push origin main
```

### Step 8: Build and Push Container Images

```bash
# Login to Quay.io
podman login quay.io

# Build and push frontend container
cd frontend
podman build -t quay.io/YOUR-QUAY-USERNAME/graph-frontend:latest .
podman push quay.io/YOUR-QUAY-USERNAME/graph-frontend:latest

# Build and push JIRA ETL container
cd ../etl/jira
podman build -t quay.io/YOUR-QUAY-USERNAME/jira-etl:latest .
podman push quay.io/YOUR-QUAY-USERNAME/jira-etl:latest

# Build and push GitHub ETL container
cd ../github
podman build -t quay.io/YOUR-QUAY-USERNAME/github-etl:latest .
podman push quay.io/YOUR-QUAY-USERNAME/github-etl:latest

cd ../..
```

### Step 9: Configure OAuth Client

```bash
# Get the Argo CD server URL for OAuth redirect
ARGOCD_URL=$(oc get route argocd-server -n argocd -o jsonpath='{.spec.host}')

# Create OAuth client for the frontend
oc create oauthclient graph-frontend \
  --redirect-uri=https://graph-frontend-graph-system.apps.YOUR-CLUSTER.YOUR-REGION.aroapp.io/oauth2/callback \
  --secret=$(openssl rand -base64 32)

# Get the OAuth client secret
OAUTH_SECRET=$(oc get oauthclient graph-frontend -o jsonpath='{.secret}')

# Generate cookie secret
COOKIE_SECRET=$(openssl rand -base64 32)

# Create OAuth proxy secrets
oc create secret generic oauth-proxy-secrets \
  --from-literal=client-secret=$OAUTH_SECRET \
  --from-literal=cookie-secret=$COOKIE_SECRET \
  -n graph-system
```

### Step 10: Deploy via Argo CD

```bash
# Apply the Argo CD applications
oc apply -f applications/graph-stack.yaml
oc apply -f applications/etl-stack.yaml

# For company-specific JIRA-GitHub integration (optional)
# First configure company-specific secrets (see company-specific/README.md)
oc apply -f applications/company-integration-stack.yaml

# Verify applications are created
oc get applications -n argocd
```

### Step 10a: Company-Specific JIRA-GitHub Integration (Optional)

If you want to deploy the advanced JIRA-GitHub integration for strategy-to-implementation traceability:

```bash
# Create company-specific secrets
oc create secret generic jira-github-integration-secrets \
  --from-literal=jira-server=https://your-jira-instance.atlassian.net \
  --from-literal=jira-username=your-jira-username \
  --from-literal=jira-token=your-jira-api-token \
  --from-literal=github-token=your-github-personal-access-token \
  -n graphserver

# Build and push the company-specific ETL container
cd company-specific/etl/jira-github-integration
podman build -t quay.io/YOUR-QUAY-USERNAME/jira-github-integration-etl:latest .
podman push quay.io/YOUR-QUAY-USERNAME/jira-github-integration-etl:latest

# Update the image reference in the CronJob
sed -i 's|jira-github-integration-etl:latest|quay.io/YOUR-QUAY-USERNAME/jira-github-integration-etl:latest|g' cronjob.yaml

# Deploy the company integration (ArgoCD will handle dependencies automatically)
oc apply -f ../../applications/company-integration-stack.yaml

cd ../../..
```

**Deployment Order & Dependencies**: 
The system uses ArgoCD sync waves to ensure proper deployment order:
1. **Wave 1**: Neo4j database, ConfigMaps, Secrets
2. **Wave 2**: Health checks, schema setup, basic ETL jobs  
3. **Wave 3**: Company-specific advanced ETL

**Health Checks**: The deployment includes automatic health checks that:
- Verify Neo4j connectivity before starting ETL
- Apply the JIRA-GitHub integration schema automatically
- Validate APOC plugin availability
- Ensure database is ready before data loading

**Advanced Features**:
- Strategy-to-implementation traceability between JIRA and GitHub
- Hierarchical filtering (only open items + closed items with open dependencies)
- Cross-reference detection and technology tracking
- Gap analysis for strategic planning
- Automatic schema management and health validation

See `company-specific/README.md` for detailed configuration and usage.

### Step 11: Configure Argo CD Repository Access

```bash
# Get Argo CD admin password
ARGOCD_PASSWORD=$(oc get secret argocd-initial-admin-secret -n argocd -o jsonpath="{.data.password}" | base64 -d)

# Login to Argo CD CLI (optional)
argocd login $ARGOCD_URL --username admin --password $ARGOCD_PASSWORD --insecure

# Add repository to Argo CD (via UI or CLI)
argocd repo add https://github.com/YOUR-USERNAME/graph-visualisation.git
```

### Step 12: Monitor Deployment

```bash
# Check application sync status
oc get applications -n argocd

# Monitor pods in graph-system namespace
oc get pods -n graph-system -w

# Check application logs
oc logs -f deployment/graph-frontend -n graph-system

# Verify Neo4j is running
oc get pods -l app=neo4j -n graph-system

# Check ETL job status
oc get cronjobs -n graph-system
oc get jobs -n graph-system
```

### Step 13: Access the Application

```bash
# Get the frontend route URL
oc get route graph-frontend -n graph-system -o jsonpath='{.spec.host}'

# Open in browser
echo "Access the application at: https://$(oc get route graph-frontend -n graph-system -o jsonpath='{.spec.host}')"
```

## Webhook Configuration (Optional)

To enable automatic deployments when you push changes to your repository:

### GitHub Webhook Setup

1. **Get Argo CD Webhook URL**:
```bash
ARGOCD_URL=$(oc get route argocd-server -n argocd -o jsonpath='{.spec.host}')
echo "Webhook URL: https://$ARGOCD_URL/api/webhook"
```

2. **Configure GitHub Webhook**:
   - Go to your GitHub repository settings
   - Navigate to "Webhooks" section
   - Click "Add webhook"
   - Set Payload URL: `https://YOUR-ARGOCD-URL/api/webhook`
   - Set Content type: `application/json`
   - Set Secret: (optional, for security)
   - Select events: `Push` and `Pull request`
   - Click "Add webhook"

3. **Configure Argo CD Application for Auto-sync**:
```bash
# Enable auto-sync for applications
oc patch application graph-stack -n argocd --type='merge' -p='{"spec":{"syncPolicy":{"automated":{"prune":true,"selfHeal":true}}}}'
oc patch application etl-stack -n argocd --type='merge' -p='{"spec":{"syncPolicy":{"automated":{"prune":true,"selfHeal":true}}}}'
```

## Verification and Testing

### Verify Neo4j Connection
```bash
# Port forward to Neo4j
oc port-forward svc/neo4j 7474:7474 7687:7687 -n graph-system

# Access Neo4j browser at http://localhost:7474
# Login with: neo4j / YOUR-SECURE-NEO4J-PASSWORD
```

### Test ETL Jobs
```bash
# Manually trigger JIRA ETL job
oc create job jira-etl-manual --from=cronjob/jira-etl -n graph-system

# Manually trigger GitHub ETL job  
oc create job github-etl-manual --from=cronjob/github-etl -n graph-system

# Check job logs
oc logs job/jira-etl-manual -n graph-system
oc logs job/github-etl-manual -n graph-system
```

### Verify Data in Neo4j
```cypher
// Check JIRA data
MATCH (i:Issue) RETURN count(i) as jira_issues;

// Check GitHub data  
MATCH (g:GitHubIssue) RETURN count(g) as github_issues;

// Check relationships
MATCH (u:User)-[r]->(i) RETURN type(r), count(r);
```

## Troubleshooting

### Common Issues

1. **Pod ImagePullBackOff**:
   - Verify container registry credentials
   - Check image names and tags
   - Ensure images are pushed to registry

2. **OAuth Authentication Fails**:
   - Verify OAuth client configuration
   - Check redirect URI matches route
   - Validate secrets are created correctly

3. **Neo4j Connection Issues**:
   - Check Neo4j pod logs
   - Verify service names and ports
   - Confirm password matches across configurations

4. **ETL Jobs Failing**:
   - Check API credentials and permissions
   - Verify network connectivity to external APIs
   - Review job logs for specific errors

5. **Dependency/Health Check Issues**:
   - Check ArgoCD sync waves are deploying in order
   - Verify Neo4j health check job completed successfully
   - Ensure schema setup job ran without errors
   - Check if APOC plugin is available in Neo4j

### Dependency Troubleshooting Commands

```bash
# Check ArgoCD sync wave order
oc get applications -n argocd -o custom-columns=NAME:.metadata.name,SYNC-WAVE:.metadata.annotations.'argocd\.argoproj\.io/sync-wave',STATUS:.status.sync.status

# Check health check job status
oc get jobs -n graphserver -l app=neo4j-health-check
oc logs job/neo4j-health-check -n graphserver

# Check schema setup job status  
oc get jobs -n graphserver -l app=jira-github-schema-setup
oc logs job/jira-github-schema-setup -n graphserver

# Verify Neo4j is ready for connections
oc exec -it deployment/neo4j -n graphserver -- cypher-shell -u neo4j -p YOUR-PASSWORD "CALL db.ping();"

# Check if company-specific ETL is waiting for dependencies
oc describe cronjob jira-github-integration-etl -n graphserver
```

### Useful Commands

```bash
# Check all resources in namespace
oc get all -n graph-system

# Describe problematic pods
oc describe pod POD-NAME -n graph-system

# Check events
oc get events -n graph-system --sort-by='.lastTimestamp'

# Check Argo CD application details
oc describe application graph-stack -n argocd

# Force sync Argo CD application
oc patch application graph-stack -n argocd --type='merge' -p='{"operation":{"sync":{"revision":"HEAD"}}}'
```

## Security Considerations

1. **Secrets Management**: All sensitive data is stored in OpenShift Secrets
2. **Network Policies**: Consider implementing network policies for additional security
3. **RBAC**: Configure appropriate role-based access controls
4. **TLS**: All external traffic uses TLS termination
5. **Container Security**: All containers run as non-root users
6. **API Rate Limits**: ETL jobs include retry logic and respect API rate limits

## Scaling and Performance

### Neo4j Scaling
- Increase CPU/memory in `neo4j/values.yaml`
- Configure persistent volume size based on data requirements
- Consider Neo4j clustering for high availability

### ETL Performance
- Adjust CronJob schedules based on data volume
- Implement parallel processing for large datasets
- Monitor API rate limits and adjust accordingly

### Frontend Scaling
- Increase replica count in `frontend/deployment.yaml`
- Configure horizontal pod autoscaling
- Optimize Cypher queries for better performance

## Support

For issues and questions:
- Check the Argo CD application status and logs
- Review pod logs for specific error messages
- Verify all prerequisites are met
- Ensure API credentials have proper permissions
- Check network connectivity to external services

## License

This configuration is provided as-is for educational and development purposes.
