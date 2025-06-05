// Neo4j Schema for JIRA-GitHub Integration
// Company-Specific Implementation for Strategy-to-Implementation Traceability

// ============================================================================
// CONSTRAINTS AND INDEXES
// ============================================================================

// JIRA Constraints
CREATE CONSTRAINT jira_issue_key IF NOT EXISTS FOR (j:JiraIssue) REQUIRE j.key IS UNIQUE;
CREATE CONSTRAINT jira_project_key IF NOT EXISTS FOR (p:JiraProject) REQUIRE p.key IS UNIQUE;

// GitHub Constraints  
CREATE CONSTRAINT github_issue_id IF NOT EXISTS FOR (g:GitHubIssue) REQUIRE (g.repository, g.number) IS UNIQUE;
CREATE CONSTRAINT github_repo_name IF NOT EXISTS FOR (r:GitHubRepository) REQUIRE r.fullName IS UNIQUE;

// Strategic Constraints
CREATE CONSTRAINT epic_id IF NOT EXISTS FOR (e:Epic) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT feature_id IF NOT EXISTS FOR (f:Feature) REQUIRE f.id IS UNIQUE;
CREATE CONSTRAINT strategy_id IF NOT EXISTS FOR (s:Strategy) REQUIRE s.id IS UNIQUE;

// Cross-cutting Constraints
CREATE CONSTRAINT person_username IF NOT EXISTS FOR (p:Person) REQUIRE p.username IS UNIQUE;
CREATE CONSTRAINT technology_name IF NOT EXISTS FOR (t:Technology) REQUIRE t.name IS UNIQUE;
CREATE CONSTRAINT component_name IF NOT EXISTS FOR (c:Component) REQUIRE c.name IS UNIQUE;

// Performance Indexes
CREATE INDEX jira_issue_status IF NOT EXISTS FOR (j:JiraIssue) ON (j.status);
CREATE INDEX jira_issue_project IF NOT EXISTS FOR (j:JiraIssue) ON (j.project);
CREATE INDEX jira_issue_created IF NOT EXISTS FOR (j:JiraIssue) ON (j.created);
CREATE INDEX github_issue_state IF NOT EXISTS FOR (g:GitHubIssue) ON (g.state);
CREATE INDEX github_issue_repo IF NOT EXISTS FOR (g:GitHubIssue) ON (g.repository);
CREATE INDEX github_issue_created IF NOT EXISTS FOR (g:GitHubIssue) ON (g.created);

// ============================================================================
// NODE CREATION PROCEDURES
// ============================================================================

// Create JIRA Issue with validation
CALL apoc.custom.asProcedure(
  'createJiraIssue',
  'MERGE (j:JiraIssue {key: $key})
   SET j.summary = $summary,
       j.description = $description,
       j.status = $status,
       j.priority = $priority,
       j.issueType = $issueType,
       j.project = $project,
       j.created = datetime($created),
       j.updated = datetime($updated),
       j.assignee = $assignee,
       j.reporter = $reporter,
       j.labels = $labels,
       j.components = $components,
       j.lastSynced = datetime()
   RETURN j',
  'read',
  [['j','NODE']]
);

// Create GitHub Issue with validation
CALL apoc.custom.asProcedure(
  'createGitHubIssue',
  'MERGE (g:GitHubIssue {repository: $repository, number: $number})
   SET g.title = $title,
       g.body = $body,
       g.state = $state,
       g.created = datetime($created),
       g.updated = datetime($updated),
       g.author = $author,
       g.url = $url,
       g.labels = $labels,
       g.organization = $organization,
       g.type = $type,
       g.lastSynced = datetime()
   RETURN g',
  'read',
  [['g','NODE']]
);

// ============================================================================
// RELATIONSHIP CREATION PROCEDURES
// ============================================================================

// Create cross-reference relationships based on text analysis
CALL apoc.custom.asProcedure(
  'linkJiraGitHubReferences',
  'MATCH (g:GitHubIssue)
   WHERE g.body IS NOT NULL OR g.title IS NOT NULL
   WITH g, 
        [x IN apoc.text.regexGroups(coalesce(g.body, "") + " " + coalesce(g.title, ""), "(AAPRFE|ANSTRAT)-\\d+") | x[0]] AS jiraRefs
   UNWIND jiraRefs AS jiraRef
   MATCH (j:JiraIssue {key: jiraRef})
   MERGE (g)-[:ADDRESSES]->(j)
   MERGE (j)-[:TRACKED_IN]->(g)
   RETURN count(*) as linksCreated',
  'write',
  [['linksCreated','INTEGER']]
);

// ============================================================================
// DATA QUALITY AND CLEANUP PROCEDURES
// ============================================================================

// Remove stale data (items closed > 90 days ago without open dependencies)
CALL apoc.custom.asProcedure(
  'cleanupStaleData',
  'MATCH (j:JiraIssue)
   WHERE j.status IN ["Closed", "Done", "Resolved"]
     AND j.updated < datetime() - duration("P90D")
     AND NOT (j)<-[:DEPENDS_ON|BLOCKS|RELATES_TO]-(:JiraIssue {status: "Open"})
     AND NOT (j)<-[:ADDRESSES]-(:GitHubIssue {state: "open"})
   DETACH DELETE j
   
   MATCH (g:GitHubIssue)
   WHERE g.state = "closed"
     AND g.updated < datetime() - duration("P90D")
     AND NOT (g)-[:ADDRESSES]->(:JiraIssue)
     WHERE j.status IN ["Open", "In Progress", "New"]
   DETACH DELETE g
   
   RETURN "Cleanup completed" as result',
  'write',
  [['result','STRING']]
);

// ============================================================================
// ANALYTICAL QUERIES
// ============================================================================

// Find orphaned strategic items (JIRA without GitHub implementation)
CALL apoc.custom.asFunction(
  'findOrphanedStrategicItems',
  'MATCH (j:JiraIssue)
   WHERE j.project IN ["ANSTRAT", "AAPRFE"]
     AND j.status IN ["Open", "In Progress", "New"]
     AND NOT (j)-[:IMPLEMENTED_BY|TRACKED_IN]->(:GitHubIssue)
   RETURN collect({
     key: j.key,
     summary: j.summary,
     status: j.status,
     priority: j.priority,
     components: j.components
   }) as orphanedItems',
  'read'
);

// Find implementation gaps by component
CALL apoc.custom.asFunction(
  'findImplementationGapsByComponent',
  'MATCH (j:JiraIssue)
   WHERE j.status IN ["Open", "In Progress", "New"]
   UNWIND j.components as component
   WITH component, count(j) as totalJiraItems
   OPTIONAL MATCH (j2:JiraIssue)-[:IMPLEMENTED_BY|TRACKED_IN]->(g:GitHubIssue)
   WHERE component IN j2.components
     AND j2.status IN ["Open", "In Progress", "New"]
   WITH component, totalJiraItems, count(g) as implementedItems
   RETURN collect({
     component: component,
     totalStrategic: totalJiraItems,
     implemented: implementedItems,
     gapPercentage: round((totalJiraItems - implementedItems) * 100.0 / totalJiraItems, 2)
   }) as componentGaps',
  'read'
);

// Technology adoption tracking
CALL apoc.custom.asFunction(
  'trackTechnologyAdoption',
  'MATCH (j:JiraIssue)-[:INVOLVES]->(t:Technology)
   WHERE j.status IN ["Open", "In Progress", "New"]
   WITH t, count(j) as strategicMentions
   OPTIONAL MATCH (g:GitHubIssue)-[:INVOLVES]->(t)
   WHERE g.state = "open"
   WITH t, strategicMentions, count(g) as implementationMentions
   RETURN collect({
     technology: t.name,
     category: t.category,
     strategicMentions: strategicMentions,
     implementationMentions: implementationMentions,
     adoptionRatio: case when strategicMentions > 0 
                    then round(implementationMentions * 100.0 / strategicMentions, 2) 
                    else 0 end
   }) as technologyAdoption',
  'read'
);

// ============================================================================
// SAMPLE DATA STRUCTURE (for reference)
// ============================================================================

/*
Example JIRA Issue Node:
{
  key: "AAPRFE-2174",
  summary: "Add Redis SSL feature",
  description: "Request documentation to support the redis SSL connection...",
  status: "New",
  priority: "Undefined",
  issueType: "Feature Request",
  project: "AAPRFE",
  created: "2025-06-05T07:34:43.000Z",
  updated: "2025-06-05T15:15:44.000Z",
  assignee: "Unassigned",
  reporter: "Lisa OH",
  labels: [],
  components: ["docs-product"],
  lastSynced: "2025-06-06T07:56:00.000Z"
}

Example GitHub Issue Node:
{
  repository: "ansible/ansible",
  number: 85274,
  title: "ad-hoc reboot test_command syntax is unintuitive",
  body: "### Summary\n\nI want to reboot a group of servers...",
  state: "open",
  created: "2025-06-05T13:24:26Z",
  updated: "2025-06-05T19:33:49Z",
  author: "Snowman-25",
  url: "https://github.com/ansible/ansible/issues/85274",
  labels: ["module", "bug", "affects_2.18"],
  organization: "ansible",
  type: "issue",
  lastSynced: "2025-06-06T07:56:00.000Z"
}
*/
