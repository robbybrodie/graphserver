# Graph Server - Jira & GitHub Relationship Mapping

A Neo4j-based system for mapping and analyzing relationships between Jira and GitHub ecosystems. This project focuses on three core layers:

1. **Discrete ETL Processes** - Load Jira and GitHub data separately, preserving internal hierarchies
2. **Cross-Reference Processing** - Identify and create relationships between the two systems
3. **Analysis/Query Layer** - Provide tools to interrogate the combined relationship graph

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Jira ETL      │───▶│                  │    │    Neo4j        │
│   (Discrete)    │    │  Cross-Reference │───▶│   Graph DB      │
└─────────────────┘    │   Processing     │    │                 │
                       │                  │    │  • Jira Items   │
┌─────────────────┐    │  • Text Analysis │    │  • GitHub Items │
│  GitHub ETL     │───▶│  • Key Matching  │    │  • Relationships│
│  (Discrete)     │    │  • Link Creation │    │  • Hierarchies  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────┐
                                               │ Analysis Layer  │
                                               │                 │
                                               │ • Query Tools   │
                                               │ • Visualization │
                                               │ • Reports       │
                                               └─────────────────┘
```

## Core Concepts

### Discrete Data Loading
- **Jira ETL**: Loads issues with their natural hierarchy (epics → stories → tasks) and internal relationships
- **GitHub ETL**: Loads issues and PRs with their repository relationships and internal references

### Cross-Reference Processing
- **Text Analysis**: Scans free-text fields for references between systems (e.g., "JIRA-123" in GitHub issues)
- **Key Matching**: Identifies explicit references using configurable patterns
- **Relationship Creation**: Creates bidirectional links between related items across systems

### Analysis Layer
- **Relationship Queries**: Find connections between strategic planning (Jira) and implementation (GitHub)
- **Gap Analysis**: Identify strategic items without implementation tracking
- **Impact Analysis**: Understand how changes propagate across systems

## Directory Structure

```
graphserver/
├── etl/
│   ├── jira/                     # Discrete Jira ETL
│   │   ├── jira_etl.py          # Core Jira extraction
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── github/                   # Discrete GitHub ETL  
│   │   ├── github_etl.py        # Core GitHub extraction
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── cross-reference/          # Cross-system relationship processing
│       ├── cross_ref_etl.py     # Link detection and creation
│       ├── Dockerfile
│       └── requirements.txt
├── analysis/
│   ├── queries/                  # Pre-built analysis queries
│   │   ├── relationship-mapping.cypher
│   │   ├── gap-analysis.cypher
│   │   └── impact-analysis.cypher
│   └── tools/                    # Analysis utilities
│       └── query-runner.py      # Query execution and reporting
├── frontend/                     # Visualization interface
│   ├── index.html               # Frontend application
│   └── Dockerfile               # Container build
├── applications/                 # ArgoCD applications (complete deployments)
│   ├── graph-stack.yaml         # Neo4j + Frontend + Schema
│   ├── etl-stack.yaml           # ETL processes + Configuration
│   └── analysis-stack.yaml      # Analysis tools + Reports
└── schema/
    └── graph-schema.cypher       # Complete graph schema
```

## Data Model

### Jira Entities
- **Issue**: Core Jira items with hierarchy (Epic → Story → Task → Subtask)
- **Project**: Jira project containers
- **User**: Assignees, reporters, watchers
- **Component**: Jira components and their relationships

### GitHub Entities  
- **Issue**: GitHub issues with labels and assignments
- **PullRequest**: PRs with branch and merge information
- **Repository**: Code repositories with ownership
- **Organization**: GitHub organizations

### Cross-System Relationships
- **ADDRESSES**: GitHub item addresses Jira item
- **TRACKED_IN**: Jira item tracked in GitHub item  
- **REFERENCES**: General reference relationship
- **IMPLEMENTS**: Implementation relationship

### Analysis Entities
- **Technology**: Extracted technology mentions
- **Component**: Logical system components
- **Theme**: Strategic themes and initiatives

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
- **Required Scopes**: repo, read:org, read:user
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

# Configure ArgoCD server to run in insecure mode (required for OpenShift routes)
oc patch configmap argocd-cmd-params-cm -n argocd --type merge -p='{"data":{"server.insecure":"true"}}'

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

# Create Argo CD route (using HTTP port since server runs in insecure mode)
oc create route edge argocd-server --service=argocd-server --port=http --insecure-policy=Redirect -n argocd

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

## Getting Started

### System Components
The Argo CD applications deploy the following components:

#### Graph Stack (Sync Wave 1)
- **Neo4j Database**: Community edition 5.15 with APOC plugins
- **Graph Schema**: Constraints and indexes for optimal performance
- **Frontend Interface**: Web-based visualization and query interface

#### ETL Stack (Sync Wave 3)
- **Jira ETL**: Extracts issues, projects, and relationships
- **GitHub ETL**: Extracts issues, PRs, and repository data
- **Cross-Reference ETL**: Creates relationships between systems

#### Analysis Stack (Sync Wave 5)
- **Query Runner**: Interactive analysis tool
- **Report Generator**: Automated weekly reports
- **Persistent Storage**: Report archival and history

### Quick Start Prerequisites
- ROSA/OpenShift cluster with ArgoCD installed
- Jira API access (username + API token)
- GitHub API access (personal access token)
- Container registry access (Quay.io recommended)

### Quick Start

1. **Clone and Configure**
```bash
git clone <your-fork>
cd graphserver

# Update repository URLs in application manifests
sed -i 's/YOUR-USERNAME/your-github-username/g' applications/*.yaml
sed -i 's/YOUR-QUAY-USERNAME/your-quay-username/g' applications/*.yaml
```

2. **Create Secrets**
```bash
# Jira credentials
oc create secret generic jira-credentials \
  --from-literal=url=https://your-domain.atlassian.net \
  --from-literal=username=your-email@company.com \
  --from-literal=api-token=YOUR-JIRA-API-TOKEN \
  -n graph-system

# GitHub credentials  
oc create secret generic github-credentials \
  --from-literal=token=YOUR-GITHUB-TOKEN \
  -n graph-system

# Neo4j credentials
oc create secret generic neo4j-auth \
  --from-literal=password=YOUR-NEO4J-PASSWORD \
  -n graph-system
```

3. **Deploy via ArgoCD (Automatic Sync Waves)**
```bash
# Deploy all applications - ArgoCD will handle proper ordering via sync waves
oc apply -f applications/

# Or deploy individually in order:
oc apply -f applications/graph-stack.yaml      # Wave 1: Neo4j + Frontend + Schema
oc apply -f applications/etl-stack.yaml        # Wave 3: ETL processes + Config
oc apply -f applications/analysis-stack.yaml   # Wave 5: Analysis tools + Reports
```

4. **Verify Deployment**
```bash
# Check ArgoCD applications
oc get applications -n argocd

# Check deployment status
oc get pods -n graph-system
oc get cronjobs -n graph-system

# Access frontend
oc get route graph-frontend -n graph-system
```

## Configuration

Configuration is now embedded in the ArgoCD application manifests. Update these values in `applications/etl-stack.yaml`:

### GitHub Repositories
```bash
# Update in etl-stack.yaml
- name: GITHUB_REPOS
  value: "ansible/ansible,ansible/ansible-runner,ansible/awx,redhat-cop/automation-good-practices"
```

### Jira Projects  
```bash
# Update in etl-stack.yaml
- name: JIRA_PROJECTS
  value: "PROJECT1,PROJECT2,PROJECT3"
```

## Analysis Examples

### Find Strategic Items Without Implementation
```cypher
MATCH (j:JiraIssue {issueType: 'Epic'})
WHERE NOT (j)-[:TRACKED_IN]->(:GitHubIssue)
RETURN j.key, j.summary, j.project
```

### Map Technology Usage Across Systems
```cypher
MATCH (tech:Technology)<-[:INVOLVES]-(item)
WHERE item:JiraIssue OR item:GitHubIssue
RETURN tech.name, 
       count(CASE WHEN item:JiraIssue THEN 1 END) as jira_mentions,
       count(CASE WHEN item:GitHubIssue THEN 1 END) as github_mentions
```

### Find Cross-System Impact Chains
```cypher
MATCH path = (j:JiraIssue)-[:TRACKED_IN]->(g:GitHubIssue)-[:BELONGS_TO]->(r:Repository)
RETURN j.key, j.summary, g.number, g.title, r.name
```

## Deployment

The system uses ArgoCD for GitOps deployment with three self-contained application stacks that deploy in sequence using sync waves:

### **Application Stack Architecture**

1. **graph-stack** (Sync Wave 1)
   - **Neo4j StatefulSet** with persistent storage and health checks
   - **Schema Setup Job** that waits for Neo4j readiness before applying constraints
   - **Frontend Deployment** with visualization interface
   - **OpenShift Route** for external access

2. **etl-stack** (Sync Wave 3)
   - **Jira ETL CronJob** (runs every 6 hours)
   - **GitHub ETL CronJob** (runs every 6 hours, offset by 15 minutes)
   - **Cross-Reference ETL CronJob** (runs 30 minutes after discrete ETL)
   - **Complete ETL Configuration** with Cypher queries and patterns

3. **analysis-stack** (Sync Wave 5)
   - **Query Runner Deployment** for interactive analysis
   - **Analysis Reports CronJob** (weekly automated reports)
   - **Persistent Storage** for report output

### **Sync Wave Sequence**
```
Wave 0: Namespace creation
Wave 1: Neo4j + Schema + Frontend infrastructure
Wave 2: Schema setup (waits for Neo4j readiness)
Wave 3: ETL processes (discrete Jira & GitHub loading)
Wave 4: Cross-reference processing (after discrete ETL)
Wave 5: Analysis tools (after all data is loaded)
```

### **Deployment Benefits**
- ✅ **Automatic dependency management** - ArgoCD handles proper ordering
- ✅ **Self-contained applications** - each stack includes all its resources
- ✅ **No resource duplication** - clean separation of concerns
- ✅ **Rollback safety** - each stack can be rolled back independently
- ✅ **GitOps ready** - all configuration in Git, no manual steps

## Monitoring

- **ETL Metrics**: Track items processed, relationships created, errors
- **Data Quality**: Monitor cross-reference accuracy, missing links
- **Performance**: Query response times, database growth

## Contributing

1. Fork the repository
2. Create feature branch
3. Update relevant ETL or analysis components
4. Test with your Jira/GitHub instances
5. Submit pull request

## License

MIT License - see LICENSE file for details
