// Impact Analysis Queries
// Understand how changes propagate across systems and identify dependencies

// 1. Downstream impact of Epic changes
MATCH (epic:Issue {issueType: 'Epic'})-[:PARENT_OF*1..3]->(child:Issue)
OPTIONAL MATCH (child)-[:TRACKED_IN|IMPLEMENTED_IN]->(impl)
WHERE impl:GitHubIssue OR impl:PullRequest
RETURN epic.key, epic.summary, epic.status,
       count(DISTINCT child) as affected_children,
       count(DISTINCT impl) as github_implementations,
       collect(DISTINCT child.issueType) as child_types,
       collect(DISTINCT impl.repository) as affected_repos
ORDER BY affected_children DESC, github_implementations DESC;

// 2. Repository impact analysis - what Jira items are affected by repo changes
MATCH (r:Repository)<-[:BELONGS_TO]-(item)-[:ADDRESSES|IMPLEMENTS]->(j:Issue)
WHERE item:GitHubIssue OR item:PullRequest
RETURN r.name, r.owner,
       count(DISTINCT j) as affected_jira_items,
       count(DISTINCT j.project) as affected_projects,
       collect(DISTINCT j.issueType) as affected_issue_types,
       collect(DISTINCT j.key)[0..10] as sample_jira_keys
ORDER BY affected_jira_items DESC;

// 3. Technology impact chains
MATCH (tech:Technology)<-[:INVOLVES]-(item)
OPTIONAL MATCH (item)-[rel]-(connected)
WHERE type(rel) IN ['ADDRESSES', 'TRACKED_IN', 'IMPLEMENTS', 'CHILD_OF', 'PARENT_OF']
RETURN tech.name,
       count(DISTINCT item) as direct_mentions,
       count(DISTINCT connected) as connected_items,
       collect(DISTINCT labels(item)) as item_types,
       collect(DISTINCT type(rel)) as relationship_types
ORDER BY direct_mentions + connected_items DESC;

// 4. User impact analysis - workload distribution
MATCH (user:User)
OPTIONAL MATCH (user)<-[:ASSIGNED_TO]-(j:Issue)
OPTIONAL MATCH (user)<-[:CREATED_BY]-(g:GitHubIssue)
OPTIONAL MATCH (user)<-[:CREATED_BY]-(pr:PullRequest)
WITH user, 
     collect(DISTINCT j) as jira_items,
     collect(DISTINCT g) as github_issues,
     collect(DISTINCT pr) as pull_requests
WHERE size(jira_items) > 0 OR size(github_issues) > 0 OR size(pull_requests) > 0
RETURN user.name,
       size(jira_items) as jira_assignments,
       size(github_issues) as github_issues_created,
       size(pull_requests) as prs_created,
       [j IN jira_items WHERE j.status IN ['Open', 'In Progress'] | j.key] as active_jira,
       [g IN github_issues WHERE g.state = 'open' | g.repository + '#' + toString(g.number)] as active_github
ORDER BY jira_assignments + github_issues_created + prs_created DESC;

// 5. Component dependency impact
MATCH (comp:Component)
OPTIONAL MATCH (comp)<-[:AFFECTS]-(j:Issue)
OPTIONAL MATCH (comp)<-[:IMPLEMENTS]-(r:Repository)
OPTIONAL MATCH (comp)<-[:RELATES_TO]-(g:GitHubIssue)
WITH comp, 
     collect(DISTINCT j.project) as jira_projects,
     collect(DISTINCT r.owner) as github_orgs,
     count(DISTINCT j) as jira_count,
     count(DISTINCT r) as repo_count,
     count(DISTINCT g) as github_count
WHERE jira_count > 0 OR repo_count > 0 OR github_count > 0
RETURN comp.name,
       jira_projects, github_orgs,
       jira_count, repo_count, github_count,
       jira_count + repo_count + github_count as total_impact
ORDER BY total_impact DESC;

// 6. Cross-project impact analysis
MATCH (j1:Issue)-[:TRACKED_IN|IMPLEMENTED_IN]->(impl)<-[:ADDRESSES|IMPLEMENTS]-(j2:Issue)
WHERE j1.project <> j2.project
RETURN j1.project as source_project, j2.project as target_project,
       count(*) as cross_references,
       collect(DISTINCT impl.repository)[0..5] as connecting_repos,
       collect(DISTINCT {source: j1.key, target: j2.key})[0..5] as sample_links
ORDER BY cross_references DESC;

// 7. Priority cascade analysis
MATCH (high:Issue)-[:PARENT_OF*1..2]->(child:Issue)
WHERE high.priority IN ['Highest', 'High']
OPTIONAL MATCH (child)-[:TRACKED_IN|IMPLEMENTED_IN]->(impl)
RETURN high.key, high.summary, high.priority, high.status,
       count(DISTINCT child) as child_items,
       count(DISTINCT impl) as implementations,
       collect(DISTINCT child.status) as child_statuses,
       collect(DISTINCT child.priority) as child_priorities
ORDER BY 
  CASE high.priority WHEN 'Highest' THEN 1 WHEN 'High' THEN 2 ELSE 3 END,
  child_items DESC;

// 8. Timeline impact analysis - items blocking others
MATCH (blocker:Issue)-[:PARENT_OF]->(blocked:Issue)
WHERE blocker.status IN ['Open', 'In Progress', 'To Do']
  AND blocked.status IN ['Open', 'In Progress', 'To Do']
OPTIONAL MATCH (blocker)-[:TRACKED_IN|IMPLEMENTED_IN]->(blocker_impl)
OPTIONAL MATCH (blocked)-[:TRACKED_IN|IMPLEMENTED_IN]->(blocked_impl)
RETURN blocker.key, blocker.summary, blocker.status, blocker.assignee,
       blocked.key as blocked_key, blocked.summary as blocked_summary,
       blocked.assignee as blocked_assignee,
       CASE WHEN blocker_impl IS NOT NULL THEN 'Has Implementation' ELSE 'No Implementation' END as blocker_status,
       CASE WHEN blocked_impl IS NOT NULL THEN 'Has Implementation' ELSE 'No Implementation' END as blocked_status
ORDER BY blocker.priority DESC, blocked.priority DESC;

// 9. Repository hotspot analysis - repos with high cross-system activity
MATCH (r:Repository)<-[:BELONGS_TO]-(item)
WHERE item:GitHubIssue OR item:PullRequest
WITH r, count(item) as total_activity
WHERE total_activity > 10
OPTIONAL MATCH (r)<-[:BELONGS_TO]-(linked_item)-[:ADDRESSES|IMPLEMENTS]->(j:Issue)
WITH r, total_activity, count(linked_item) as jira_linked,
     collect(DISTINCT j.project) as affected_projects
RETURN r.name, r.owner, total_activity, jira_linked,
       round(100.0 * jira_linked / total_activity, 1) as jira_link_percentage,
       size(affected_projects) as project_count,
       affected_projects
ORDER BY total_activity DESC, jira_link_percentage DESC;

// 10. Change velocity impact
MATCH (item)-[:TRACKED_IN|IMPLEMENTED_IN|ADDRESSES]->(connected)
WHERE (item.updated > datetime() - duration({days: 30}) OR 
       connected.updated > datetime() - duration({days: 30}))
WITH item, connected,
     duration.between(item.updated, datetime()).days as item_age,
     duration.between(connected.updated, datetime()).days as connected_age
RETURN labels(item)[0] as item_type, labels(connected)[0] as connected_type,
       count(*) as recent_changes,
       avg(item_age) as avg_item_age,
       avg(connected_age) as avg_connected_age,
       collect(DISTINCT 
         CASE 
           WHEN item:Issue THEN item.project
           WHEN item:GitHubIssue THEN item.repository
           WHEN item:PullRequest THEN item.repository
         END
       )[0..5] as affected_areas
ORDER BY recent_changes DESC;

// 11. Epic completion impact prediction
MATCH (epic:Issue {issueType: 'Epic'})-[:PARENT_OF]->(story:Issue)
WHERE epic.status IN ['Open', 'In Progress']
OPTIONAL MATCH (story)-[:TRACKED_IN|IMPLEMENTED_IN]->(impl)
WITH epic, 
     count(story) as total_stories,
     count(impl) as implemented_stories,
     collect(story.status) as story_statuses
RETURN epic.key, epic.summary, epic.priority, epic.assignee,
       total_stories, implemented_stories,
       round(100.0 * implemented_stories / total_stories, 1) as completion_percentage,
       size([s IN story_statuses WHERE s IN ['Closed', 'Done', 'Resolved']]) as closed_stories,
       size([s IN story_statuses WHERE s IN ['Open', 'To Do']]) as open_stories,
       size([s IN story_statuses WHERE s = 'In Progress']) as in_progress_stories
ORDER BY completion_percentage DESC, total_stories DESC;

// 12. Dependency bottleneck analysis
MATCH (item)-[rel]->(dependency)
WHERE type(rel) IN ['CHILD_OF', 'ADDRESSES', 'IMPLEMENTS', 'TRACKED_IN']
WITH dependency, count(item) as dependent_count, collect(DISTINCT labels(item)[0]) as dependent_types
WHERE dependent_count > 3
OPTIONAL MATCH (dependency)-[:ASSIGNED_TO]->(user:User)
RETURN 
  CASE 
    WHEN dependency:Issue THEN dependency.key
    WHEN dependency:GitHubIssue THEN dependency.repository + '#' + toString(dependency.number)
    WHEN dependency:PullRequest THEN dependency.repository + '#' + toString(dependency.number)
  END as dependency_id,
  labels(dependency)[0] as dependency_type,
  dependent_count,
  dependent_types,
  user.name as assignee,
  CASE 
    WHEN dependency:Issue THEN dependency.status
    WHEN dependency:GitHubIssue THEN dependency.state
    WHEN dependency:PullRequest THEN dependency.state
  END as status
ORDER BY dependent_count DESC;
