// Graph Schema for Jira-GitHub Relationship Mapping
// Defines the complete data model for the three-layer architecture:
// 1. Discrete data loading (Jira and GitHub entities)
// 2. Cross-reference processing (relationships between systems)
// 3. Analysis layer (derived entities and insights)

// ============================================================================
// LAYER 1: DISCRETE DATA ENTITIES
// ============================================================================

// Jira Entities
// -------------

// Create constraints for Jira entities
CREATE CONSTRAINT jira_issue_key IF NOT EXISTS FOR (i:Issue) REQUIRE i.key IS UNIQUE;
CREATE CONSTRAINT jira_project_key IF NOT EXISTS FOR (p:Project) REQUIRE p.key IS UNIQUE;

// Create indexes for performance
CREATE INDEX jira_issue_status IF NOT EXISTS FOR (i:Issue) ON (i.status);
CREATE INDEX jira_issue_type IF NOT EXISTS FOR (i:Issue) ON (i.issueType);
CREATE INDEX jira_issue_priority IF NOT EXISTS FOR (i:Issue) ON (i.priority);
CREATE INDEX jira_issue_project IF NOT EXISTS FOR (i:Issue) ON (i.project);
CREATE INDEX jira_issue_assignee IF NOT EXISTS FOR (i:Issue) ON (i.assignee);
CREATE INDEX jira_issue_created IF NOT EXISTS FOR (i:Issue) ON (i.created);
CREATE INDEX jira_issue_updated IF NOT EXISTS FOR (i:Issue) ON (i.updated);

// GitHub Entities
// ---------------

// Create constraints for GitHub entities
CREATE CONSTRAINT github_issue_unique IF NOT EXISTS FOR (g:GitHubIssue) REQUIRE (g.repository, g.number) IS UNIQUE;
CREATE CONSTRAINT github_pr_unique IF NOT EXISTS FOR (pr:PullRequest) REQUIRE (pr.repository, pr.number) IS UNIQUE;
CREATE CONSTRAINT github_repo_unique IF NOT EXISTS FOR (r:Repository) REQUIRE r.full_name IS UNIQUE;
CREATE CONSTRAINT github_org_unique IF NOT EXISTS FOR (o:GitHubOrganization) REQUIRE o.name IS UNIQUE;

// Create indexes for GitHub entities
CREATE INDEX github_issue_state IF NOT EXISTS FOR (g:GitHubIssue) ON (g.state);
CREATE INDEX github_issue_repo IF NOT EXISTS FOR (g:GitHubIssue) ON (g.repository);
CREATE INDEX github_issue_author IF NOT EXISTS FOR (g:GitHubIssue) ON (g.author);
CREATE INDEX github_issue_created IF NOT EXISTS FOR (g:GitHubIssue) ON (g.created);
CREATE INDEX github_issue_updated IF NOT EXISTS FOR (g:GitHubIssue) ON (g.updated);

CREATE INDEX github_pr_state IF NOT EXISTS FOR (pr:PullRequest) ON (pr.state);
CREATE INDEX github_pr_repo IF NOT EXISTS FOR (pr:PullRequest) ON (pr.repository);
CREATE INDEX github_pr_author IF NOT EXISTS FOR (pr:PullRequest) ON (pr.author);
CREATE INDEX github_pr_merged IF NOT EXISTS FOR (pr:PullRequest) ON (pr.merged);

CREATE INDEX github_repo_owner IF NOT EXISTS FOR (r:Repository) ON (r.owner);
CREATE INDEX github_repo_name IF NOT EXISTS FOR (r:Repository) ON (r.name);

// ============================================================================
// LAYER 2: CROSS-REFERENCE ENTITIES
// ============================================================================

// Shared Entities
// ---------------

// Create constraints for shared entities
CREATE CONSTRAINT user_name_unique IF NOT EXISTS FOR (u:User) REQUIRE u.name IS UNIQUE;
CREATE CONSTRAINT technology_name_unique IF NOT EXISTS FOR (t:Technology) REQUIRE t.name IS UNIQUE;
CREATE CONSTRAINT component_name_unique IF NOT EXISTS FOR (c:Component) REQUIRE c.name IS UNIQUE;

// Create indexes for shared entities
CREATE INDEX user_name IF NOT EXISTS FOR (u:User) ON (u.name);
CREATE INDEX technology_name IF NOT EXISTS FOR (t:Technology) ON (t.name);
CREATE INDEX component_name IF NOT EXISTS FOR (c:Component) ON (c.name);

// ============================================================================
// LAYER 3: ANALYSIS ENTITIES
// ============================================================================

// Analysis and Metadata Entities
// -------------------------------

CREATE CONSTRAINT processing_metadata_unique IF NOT EXISTS FOR (m:ProcessingMetadata) REQUIRE m.type IS UNIQUE;
CREATE INDEX processing_metadata_last_run IF NOT EXISTS FOR (m:ProcessingMetadata) ON (m.last_run);

// ============================================================================
// RELATIONSHIP DEFINITIONS
// ============================================================================

// Jira Internal Relationships
// ----------------------------
// :BELONGS_TO - Issue belongs to Project
// :PARENT_OF - Epic/Story has child issues
// :CHILD_OF - Task/Story belongs to parent issue
// :ASSIGNED_TO - Issue assigned to User
// :REPORTED_BY - Issue reported by User

// GitHub Internal Relationships
// ------------------------------
// :BELONGS_TO - Issue/PR belongs to Repository
// :OWNED_BY - Repository owned by Organization
// :CREATED_BY - Issue/PR created by User
// :HAS_LABEL - Issue/PR has Label

// Cross-System Relationships
// ---------------------------
// :ADDRESSES - GitHub item addresses Jira item
// :TRACKED_IN - Jira item tracked in GitHub item
// :IMPLEMENTS - GitHub PR implements Jira item
// :IMPLEMENTED_IN - Jira item implemented in GitHub PR
// :REFERENCES - General reference relationship
// :REFERENCED_BY - Reverse reference relationship

// Analysis Relationships
// ----------------------
// :INVOLVES - Item involves Technology
// :AFFECTS - Issue affects Component
// :IMPLEMENTS - Repository implements Component
// :RELATES_TO - GitHub item relates to Component

// ============================================================================
// SAMPLE DATA VALIDATION QUERIES
// ============================================================================

// Validate Jira data structure
// MATCH (i:Issue)-[:BELONGS_TO]->(p:Project)
// RETURN p.key, count(i) as issue_count
// ORDER BY issue_count DESC;

// Validate GitHub data structure
// MATCH (item)-[:BELONGS_TO]->(r:Repository)-[:OWNED_BY]->(o:GitHubOrganization)
// WHERE item:GitHubIssue OR item:PullRequest
// RETURN o.name, r.name, count(item) as item_count
// ORDER BY item_count DESC;

// Validate cross-references
// MATCH (j:Issue)-[rel]-(g)
// WHERE g:GitHubIssue OR g:PullRequest
// RETURN type(rel), count(*) as relationship_count
// ORDER BY relationship_count DESC;

// ============================================================================
// DATA QUALITY CONSTRAINTS
// ============================================================================

// Ensure Jira issues have required fields
// Note: These would be enforced at application level, not database level
// - Issue.key must match pattern [A-Z]+-\d+
// - Issue.status must be from valid status list
// - Issue.issueType must be from valid type list
// - Issue.project must reference existing Project

// Ensure GitHub items have required fields
// - GitHubIssue.repository must reference existing Repository
// - GitHubIssue.number must be positive integer
// - GitHubIssue.state must be 'open' or 'closed'
// - PullRequest.state must be 'open', 'closed', or 'merged'

// ============================================================================
// PERFORMANCE OPTIMIZATION
// ============================================================================

// Additional indexes for common query patterns
CREATE INDEX cross_ref_jira_github IF NOT EXISTS FOR ()-[r:ADDRESSES|TRACKED_IN|IMPLEMENTS]-() ON (r.created);
CREATE INDEX hierarchy_parent_child IF NOT EXISTS FOR ()-[r:PARENT_OF|CHILD_OF]-() ON (r.created);
CREATE INDEX technology_involvement IF NOT EXISTS FOR ()-[r:INVOLVES]-() ON (r.created);
CREATE INDEX component_relationships IF NOT EXISTS FOR ()-[r:AFFECTS|IMPLEMENTS|RELATES_TO]-() ON (r.created);

// Text search indexes for content analysis
// Note: These require APOC or full-text search plugin
// CREATE FULLTEXT INDEX jira_content_search IF NOT EXISTS FOR (i:Issue) ON EACH [i.summary, i.description];
// CREATE FULLTEXT INDEX github_content_search IF NOT EXISTS FOR (g:GitHubIssue) ON EACH [g.title, g.body];

// ============================================================================
// SCHEMA VALIDATION PROCEDURES
// ============================================================================

// Procedure to validate schema integrity
// This would be implemented as a custom procedure or run as validation queries

/*
CALL apoc.custom.asProcedure(
  'validateSchema',
  'MATCH (i:Issue) WHERE i.key IS NULL OR i.key = "" RETURN count(i) as invalid_jira_keys',
  'read',
  [['invalid_count', 'long']]
);
*/

// ============================================================================
// MIGRATION SUPPORT
// ============================================================================

// Version tracking for schema changes
MERGE (schema:SchemaVersion {version: '1.0.0'})
SET schema.created = datetime(),
    schema.description = 'Initial three-layer architecture schema',
    schema.layers = ['discrete_data', 'cross_reference', 'analysis'];

// ============================================================================
// CLEANUP PROCEDURES
// ============================================================================

// Procedure to clean up stale data (older than specified days)
/*
MATCH (i:Issue) 
WHERE i.lastSynced < datetime() - duration({days: 30})
  AND i.status IN ['Closed', 'Done', 'Resolved']
DETACH DELETE i;

MATCH (g:GitHubIssue) 
WHERE g.lastSynced < datetime() - duration({days: 30})
  AND g.state = 'closed'
DETACH DELETE g;
*/

// ============================================================================
// MONITORING QUERIES
// ============================================================================

// Data freshness monitoring
/*
MATCH (meta:ProcessingMetadata)
RETURN meta.type, meta.last_run, 
       duration.between(meta.last_run, datetime()).hours as hours_since_last_run
ORDER BY hours_since_last_run DESC;
*/

// Relationship health monitoring
/*
MATCH (j:Issue)
WHERE j.status IN ['Open', 'In Progress']
  AND j.issueType IN ['Epic', 'Story']
OPTIONAL MATCH (j)-[:TRACKED_IN|IMPLEMENTED_IN]->(impl)
RETURN j.project, 
       count(j) as open_strategic_items,
       count(impl) as items_with_implementation,
       round(100.0 * count(impl) / count(j), 1) as implementation_percentage
ORDER BY implementation_percentage ASC;
*/
