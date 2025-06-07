// Relationship Mapping Queries
// Find connections between Jira strategic items and GitHub implementation

// 1. Find Epics with GitHub implementation tracking
MATCH (epic:Issue {issueType: 'Epic'})-[:TRACKED_IN]->(g:GitHubIssue)
RETURN epic.key, epic.summary, epic.project,
       collect({repo: g.repository, number: g.number, title: g.title}) as github_items
ORDER BY epic.project, epic.key;

// 2. Find Stories linked to Pull Requests (implementation)
MATCH (story:Issue {issueType: 'Story'})-[:IMPLEMENTED_IN]->(pr:PullRequest)
RETURN story.key, story.summary, story.status,
       pr.repository, pr.number, pr.title, pr.state, pr.merged
ORDER BY story.project, story.key;

// 3. Cross-system impact analysis - find all items related to a technology
MATCH (tech:Technology {name: 'ansible'})<-[:INVOLVES]-(item)
OPTIONAL MATCH (item)-[rel]-(connected)
WHERE type(rel) IN ['ADDRESSES', 'TRACKED_IN', 'IMPLEMENTS', 'REFERENCES']
RETURN item, type(item) as item_type, 
       collect({connected: connected, relationship: type(rel)}) as connections;

// 4. Find orphaned strategic items (no implementation tracking)
MATCH (epic:Issue {issueType: 'Epic'})
WHERE NOT (epic)-[:TRACKED_IN]->(:GitHubIssue)
  AND NOT (epic)-[:IMPLEMENTED_IN]->(:PullRequest)
RETURN epic.key, epic.summary, epic.status, epic.priority, epic.project
ORDER BY epic.priority DESC, epic.created DESC;

// 5. Find GitHub items addressing multiple Jira issues
MATCH (g:GitHubIssue)-[:ADDRESSES]->(j:Issue)
WITH g, collect(j) as jira_issues
WHERE size(jira_issues) > 1
RETURN g.repository, g.number, g.title,
       [issue IN jira_issues | {key: issue.key, summary: issue.summary}] as addresses
ORDER BY size(jira_issues) DESC;

// 6. Technology adoption across projects
MATCH (tech:Technology)<-[:INVOLVES]-(j:Issue)-[:BELONGS_TO]->(p:Project)
RETURN tech.name, p.key as project,
       count(j) as mentions,
       collect(DISTINCT j.issueType) as issue_types
ORDER BY tech.name, mentions DESC;

// 7. Component relationship mapping
MATCH (comp:Component)<-[:AFFECTS]-(j:Issue)
OPTIONAL MATCH (comp)<-[:IMPLEMENTS]-(r:Repository)<-[:BELONGS_TO]-(g:GitHubIssue)
RETURN comp.name,
       count(DISTINCT j) as jira_items,
       count(DISTINCT g) as github_items,
       collect(DISTINCT j.project) as jira_projects,
       collect(DISTINCT r.name) as github_repos
ORDER BY jira_items + github_items DESC;

// 8. User activity across systems
MATCH (user:User)
OPTIONAL MATCH (user)<-[:ASSIGNED_TO]-(j:Issue)
OPTIONAL MATCH (user)<-[:CREATED_BY]-(g:GitHubIssue)
RETURN user.name,
       count(DISTINCT j) as jira_assignments,
       count(DISTINCT g) as github_issues,
       collect(DISTINCT j.project) as jira_projects,
       collect(DISTINCT g.repository) as github_repos
WHERE jira_assignments > 0 OR github_issues > 0
ORDER BY jira_assignments + github_issues DESC;

// 9. Hierarchy with cross-system links
MATCH (epic:Issue {issueType: 'Epic'})-[:PARENT_OF]->(story:Issue)
OPTIONAL MATCH (epic)-[:TRACKED_IN]->(epic_gh:GitHubIssue)
OPTIONAL MATCH (story)-[:TRACKED_IN]->(story_gh:GitHubIssue)
OPTIONAL MATCH (story)-[:IMPLEMENTED_IN]->(story_pr:PullRequest)
RETURN epic.key, epic.summary,
       story.key, story.summary, story.status,
       epic_gh.repository as epic_repo, epic_gh.number as epic_gh_number,
       story_gh.repository as story_repo, story_gh.number as story_gh_number,
       story_pr.repository as pr_repo, story_pr.number as pr_number
ORDER BY epic.key, story.key;

// 10. Gap analysis - strategic themes without implementation
MATCH (epic:Issue {issueType: 'Epic'})
WHERE epic.status IN ['Open', 'In Progress', 'To Do']
OPTIONAL MATCH (epic)-[:PARENT_OF]->(story:Issue)
OPTIONAL MATCH (story)-[:TRACKED_IN|IMPLEMENTED_IN]->(impl)
WHERE impl:GitHubIssue OR impl:PullRequest
WITH epic, count(story) as total_stories, count(impl) as implemented_stories
WHERE total_stories > 0 AND implemented_stories = 0
RETURN epic.key, epic.summary, epic.priority, epic.status,
       total_stories, implemented_stories,
       round(100.0 * implemented_stories / total_stories, 1) as implementation_percentage
ORDER BY epic.priority DESC, total_stories DESC;
