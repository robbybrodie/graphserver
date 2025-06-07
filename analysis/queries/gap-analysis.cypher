// Gap Analysis Queries
// Identify missing links and implementation gaps between strategic planning and execution

// 1. Strategic Epics without any GitHub tracking
MATCH (epic:Issue {issueType: 'Epic'})
WHERE epic.status IN ['Open', 'In Progress', 'To Do', 'New']
  AND NOT (epic)-[:TRACKED_IN]->(:GitHubIssue)
  AND NOT (epic)-[:IMPLEMENTED_IN]->(:PullRequest)
RETURN epic.key, epic.summary, epic.status, epic.priority, epic.project,
       epic.assignee, epic.created, epic.updated
ORDER BY 
  CASE epic.priority 
    WHEN 'Highest' THEN 1 
    WHEN 'High' THEN 2 
    WHEN 'Medium' THEN 3 
    WHEN 'Low' THEN 4 
    ELSE 5 
  END,
  epic.created DESC;

// 2. Stories without implementation (no GitHub links)
MATCH (story:Issue {issueType: 'Story'})
WHERE story.status IN ['Open', 'In Progress', 'To Do', 'New']
  AND NOT (story)-[:TRACKED_IN]->(:GitHubIssue)
  AND NOT (story)-[:IMPLEMENTED_IN]->(:PullRequest)
OPTIONAL MATCH (story)-[:CHILD_OF]->(epic:Issue {issueType: 'Epic'})
RETURN story.key, story.summary, story.status, story.priority,
       epic.key as epic_key, epic.summary as epic_summary,
       story.assignee, story.created
ORDER BY epic.key, story.priority DESC, story.created DESC;

// 3. GitHub issues without Jira strategic context
MATCH (g:GitHubIssue)
WHERE g.state = 'open'
  AND NOT (g)-[:ADDRESSES]->(:Issue)
  AND NOT (g)-[:REFERENCED_BY]->(:Issue)
RETURN g.repository, g.number, g.title, g.author, g.created, g.labels
ORDER BY g.repository, g.created DESC;

// 4. Pull Requests without Jira context
MATCH (pr:PullRequest)
WHERE pr.state IN ['open', 'merged']
  AND NOT (pr)-[:IMPLEMENTS]->(:Issue)
  AND NOT (pr)-[:ADDRESSES]->(:Issue)
RETURN pr.repository, pr.number, pr.title, pr.author, pr.state,
       pr.created, pr.merged_at
ORDER BY pr.repository, pr.created DESC;

// 5. Technology gaps - technologies mentioned in Jira but not in GitHub
MATCH (tech:Technology)<-[:INVOLVES]-(j:Issue)
WHERE NOT (tech)<-[:INVOLVES]-(:GitHubIssue)
  AND NOT (tech)<-[:INVOLVES]-(:PullRequest)
RETURN tech.name, 
       count(j) as jira_mentions,
       collect(DISTINCT j.project) as jira_projects,
       collect(DISTINCT j.issueType) as issue_types
ORDER BY jira_mentions DESC;

// 6. Component implementation gaps
MATCH (comp:Component)<-[:AFFECTS]-(j:Issue)
WHERE j.status IN ['Open', 'In Progress', 'To Do']
OPTIONAL MATCH (comp)<-[:IMPLEMENTS]-(r:Repository)
OPTIONAL MATCH (comp)<-[:RELATES_TO]-(g:GitHubIssue)
WITH comp, count(j) as jira_items, count(r) as repos, count(g) as github_items
WHERE repos = 0 OR github_items = 0
RETURN comp.name, jira_items, repos, github_items,
       CASE 
         WHEN repos = 0 THEN 'No implementing repositories'
         WHEN github_items = 0 THEN 'No GitHub issues/PRs'
         ELSE 'Partial implementation'
       END as gap_type
ORDER BY jira_items DESC;

// 7. Orphaned hierarchies - Epics with stories but no implementation
MATCH (epic:Issue {issueType: 'Epic'})-[:PARENT_OF]->(story:Issue)
WHERE epic.status IN ['Open', 'In Progress']
WITH epic, collect(story) as stories
WHERE size(stories) > 0
OPTIONAL MATCH (epic)-[:TRACKED_IN|IMPLEMENTED_IN]->(epic_impl)
OPTIONAL MATCH (story IN stories)-[:TRACKED_IN|IMPLEMENTED_IN]->(story_impl)
WHERE epic_impl IS NULL AND story_impl IS NULL
RETURN epic.key, epic.summary, epic.status, epic.priority,
       size(stories) as story_count,
       [s IN stories | {key: s.key, summary: s.summary, status: s.status}] as stories_detail
ORDER BY epic.priority DESC, story_count DESC;

// 8. Stale cross-references - old GitHub items still referencing closed Jira issues
MATCH (g:GitHubIssue)-[:ADDRESSES]->(j:Issue)
WHERE g.state = 'open' 
  AND j.status IN ['Closed', 'Done', 'Resolved', 'Cancelled']
  AND duration.between(j.updated, datetime()).days > 30
RETURN g.repository, g.number, g.title, g.updated,
       j.key, j.summary, j.status, j.updated as jira_updated,
       duration.between(j.updated, datetime()).days as days_since_jira_closed
ORDER BY days_since_jira_closed DESC;

// 9. Missing assignee alignment
MATCH (j:Issue)-[:TRACKED_IN]->(g:GitHubIssue)
WHERE j.assignee IS NOT NULL 
  AND g.author IS NOT NULL
  AND toLower(j.assignee) <> toLower(g.author)
RETURN j.key, j.summary, j.assignee as jira_assignee,
       g.repository, g.number, g.title, g.author as github_author
ORDER BY j.project, j.key;

// 10. Implementation velocity gaps - stories created but not implemented
MATCH (story:Issue {issueType: 'Story'})
WHERE story.created < datetime() - duration({days: 90})
  AND story.status IN ['Open', 'In Progress', 'To Do']
  AND NOT (story)-[:TRACKED_IN]->(:GitHubIssue)
  AND NOT (story)-[:IMPLEMENTED_IN]->(:PullRequest)
RETURN story.key, story.summary, story.status, story.priority,
       story.assignee, story.created,
       duration.between(story.created, datetime()).days as days_old
ORDER BY days_old DESC, story.priority DESC;

// 11. Cross-system status misalignment
MATCH (j:Issue)-[:TRACKED_IN]->(g:GitHubIssue)
WHERE (j.status IN ['Closed', 'Done', 'Resolved'] AND g.state = 'open')
   OR (j.status IN ['Open', 'In Progress', 'To Do'] AND g.state = 'closed')
RETURN j.key, j.summary, j.status as jira_status,
       g.repository, g.number, g.title, g.state as github_status,
       j.updated as jira_updated, g.updated as github_updated
ORDER BY j.updated DESC;

// 12. Repository coverage gaps - active repositories without Jira context
MATCH (r:Repository)<-[:BELONGS_TO]-(item)
WHERE item:GitHubIssue OR item:PullRequest
WITH r, count(item) as activity
WHERE activity > 5  // Repositories with significant activity
OPTIONAL MATCH (r)<-[:BELONGS_TO]-(linked_item)-[:ADDRESSES|IMPLEMENTS]->(:Issue)
WITH r, activity, count(linked_item) as linked_activity
WHERE linked_activity = 0 OR (100.0 * linked_activity / activity) < 20
RETURN r.name, r.owner, activity, linked_activity,
       round(100.0 * linked_activity / activity, 1) as jira_link_percentage
ORDER BY activity DESC, jira_link_percentage ASC;
