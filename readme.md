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

## Getting Started

### Prerequisites
- ROSA/OpenShift cluster with ArgoCD
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
