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
│   │   ├── cronjob.yaml         # Kubernetes CronJob
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── github/                   # Discrete GitHub ETL  
│   │   ├── github_etl.py        # Core GitHub extraction
│   │   ├── cronjob.yaml         # Kubernetes CronJob
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── cross-reference/          # Cross-system relationship processing
│   │   ├── cross_ref_etl.py     # Link detection and creation
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── shared/
│       └── configmap.yaml       # Shared configuration
├── analysis/
│   ├── queries/                  # Pre-built analysis queries
│   │   ├── relationship-mapping.cypher
│   │   ├── gap-analysis.cypher
│   │   └── impact-analysis.cypher
│   └── tools/                    # Analysis utilities
│       └── query-runner.py      # Query execution and reporting
├── frontend/                     # Visualization interface
│   ├── index.html
│   ├── Dockerfile
│   ├── deployment.yaml
│   ├── service.yaml
│   └── route.yaml
├── neo4j/                        # Database configuration
│   ├── kustomization.yaml
│   └── values.yaml
├── applications/                 # ArgoCD applications
│   ├── etl-stack.yaml           # ETL processes
│   ├── analysis-stack.yaml      # Analysis tools
│   └── graph-stack.yaml         # Neo4j + Frontend
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

# Update configuration
cp etl/shared/configmap.yaml.example etl/shared/configmap.yaml
# Edit with your Jira projects, GitHub repos, etc.
```

2. **Create Secrets**
```bash
# Jira credentials
oc create secret generic jira-credentials \
  --from-literal=url=https://your-domain.atlassian.net \
  --from-literal=username=your-email@company.com \
  --from-literal=api-token=YOUR-JIRA-API-TOKEN

# GitHub credentials  
oc create secret generic github-credentials \
  --from-literal=token=YOUR-GITHUB-TOKEN

# Neo4j credentials
oc create secret generic neo4j-auth \
  --from-literal=password=YOUR-NEO4J-PASSWORD
```

3. **Deploy via ArgoCD**
```bash
oc apply -f applications/graph-stack.yaml      # Neo4j + Frontend
oc apply -f applications/etl-stack.yaml        # ETL processes
oc apply -f applications/analysis-stack.yaml   # Analysis tools
```

### ETL Process Flow

1. **Discrete Loading** (Parallel)
   - Jira ETL loads issues with internal hierarchy
   - GitHub ETL loads issues/PRs with repository structure

2. **Cross-Reference Processing** (Sequential)
   - Scans loaded data for cross-references
   - Creates relationship links between systems
   - Extracts technology and component mentions

3. **Analysis Ready**
   - Combined graph available for querying
   - Visualization tools can access unified data

## Configuration

### Jira Configuration
```yaml
jira:
  projects: ["PROJECT1", "PROJECT2"]
  issue_types: ["Epic", "Story", "Task", "Bug"]
  custom_fields:
    - "customfield_10001"  # Story Points
    - "customfield_10002"  # Sprint
```

### GitHub Configuration  
```yaml
github:
  repositories: 
    - "ansible/ansible"
    - "ansible/ansible-runner"
    - "ansible/awx"
    - "redhat-cop/automation-good-practices"
  include_pull_requests: true
```

### Cross-Reference Patterns
```yaml
cross_reference:
  jira_patterns:
    - "[A-Z]+-\\d+"           # Standard Jira keys
    - "JIRA[:\\s]+([A-Z]+-\\d+)"  # "JIRA: ABC-123"
  github_patterns:
    - "#(\\d+)"               # Issue numbers
    - "github\\.com/.+/(\\d+)" # Full URLs
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

The system uses ArgoCD for GitOps deployment with three application stacks:

1. **graph-stack**: Neo4j database and frontend
2. **etl-stack**: All ETL processes (Jira, GitHub, Cross-reference)  
3. **analysis-stack**: Query tools and reporting utilities

Each stack can be deployed independently, with proper dependency management through ArgoCD sync waves.

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
