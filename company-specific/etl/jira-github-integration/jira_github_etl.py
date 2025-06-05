#!/usr/bin/env python3
"""
JIRA-GitHub Integration ETL
Company-Specific Implementation for Strategy-to-Implementation Traceability

This ETL process:
1. Extracts open items from JIRA (AAPRFE, ANSTRAT projects)
2. Extracts open issues/PRs from key GitHub repositories
3. Identifies cross-references and relationships
4. Loads data into Neo4j with proper hierarchical filtering
5. Only includes closed items that have open dependencies
"""

import os
import sys
import logging
import yaml
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from jira import JIRA
from github import Github, GithubException
from neo4j import GraphDatabase
from retrying import retry
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class JiraIssueData:
    """Data structure for JIRA issues"""
    key: str
    summary: str
    description: str
    status: str
    priority: str
    issue_type: str
    project: str
    created: datetime
    updated: datetime
    assignee: str
    reporter: str
    labels: List[str]
    components: List[str]

@dataclass
class GitHubIssueData:
    """Data structure for GitHub issues"""
    repository: str
    number: int
    title: str
    body: str
    state: str
    created: datetime
    updated: datetime
    author: str
    url: str
    labels: List[str]
    organization: str
    issue_type: str  # issue or pull_request

class JiraGitHubETL:
    """Main ETL class for JIRA-GitHub integration"""
    
    def __init__(self, config_path: str):
        """Initialize ETL with configuration"""
        self.config = self._load_config(config_path)
        self._setup_logging()
        self._setup_connections()
        self.processed_items = {"jira": 0, "github": 0, "links": 0}
        
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML file"""
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Expand environment variables
        config_str = yaml.dump(config)
        for env_var in re.findall(r'\$\{([^}]+)\}', config_str):
            config_str = config_str.replace(f'${{{env_var}}}', os.getenv(env_var, ''))
        
        return yaml.safe_load(config_str)
    
    def _setup_logging(self):
        """Setup logging configuration"""
        log_config = self.config['logging']
        logging.basicConfig(
            level=getattr(logging, log_config['level']),
            format=log_config['format'],
            handlers=[
                logging.FileHandler(log_config['file']),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def _setup_connections(self):
        """Setup connections to JIRA, GitHub, and Neo4j"""
        # JIRA connection
        jira_config = self.config['jira']
        self.jira = JIRA(
            server=jira_config['server'],
            basic_auth=(jira_config['username'], jira_config['token'])
        )
        
        # GitHub connection
        github_config = self.config['github']
        self.github = Github(github_config['token'])
        
        # Neo4j connection
        neo4j_config = self.config['neo4j']
        self.neo4j_driver = GraphDatabase.driver(
            neo4j_config['uri'],
            auth=(neo4j_config['username'], neo4j_config['password']),
            max_connection_lifetime=neo4j_config['max_connection_lifetime'],
            max_connection_pool_size=neo4j_config['max_connection_pool_size'],
            connection_acquisition_timeout=neo4j_config['connection_acquisition_timeout']
        )
        
    @retry(stop_max_attempt_number=3, wait_exponential_multiplier=1000)
    def _fetch_jira_issues(self) -> List[JiraIssueData]:
        """Fetch JIRA issues with hierarchical filtering"""
        self.logger.info("Fetching JIRA issues...")
        
        jira_config = self.config['jira']
        all_issues = []
        
        # Fetch open items
        open_jql = jira_config['jql_filters']['open_items']
        open_issues = self._fetch_jira_batch(open_jql)
        all_issues.extend(open_issues)
        
        # Fetch recently closed items
        recent_closed_jql = jira_config['jql_filters']['recent_closed']
        recent_closed = self._fetch_jira_batch(recent_closed_jql)
        
        # Filter closed items - only include if they have open dependencies
        filtered_closed = self._filter_closed_with_open_deps(recent_closed, open_issues)
        all_issues.extend(filtered_closed)
        
        self.logger.info(f"Fetched {len(all_issues)} JIRA issues ({len(open_issues)} open, {len(filtered_closed)} closed with open deps)")
        return all_issues
    
    def _fetch_jira_batch(self, jql: str) -> List[JiraIssueData]:
        """Fetch a batch of JIRA issues"""
        issues = []
        start_at = 0
        batch_size = self.config['jira']['batch_size']
        
        while True:
            batch = self.jira.search_issues(
                jql, 
                startAt=start_at, 
                maxResults=batch_size,
                expand='changelog'
            )
            
            if not batch:
                break
                
            for issue in batch:
                issues.append(self._convert_jira_issue(issue))
            
            start_at += batch_size
            time.sleep(self.config['jira']['rate_limit_delay'])
            
            if len(batch) < batch_size:
                break
                
        return issues
    
    def _convert_jira_issue(self, issue) -> JiraIssueData:
        """Convert JIRA issue to internal data structure"""
        return JiraIssueData(
            key=issue.key,
            summary=issue.fields.summary,
            description=getattr(issue.fields, 'description', '') or '',
            status=issue.fields.status.name,
            priority=getattr(issue.fields.priority, 'name', 'Undefined') if issue.fields.priority else 'Undefined',
            issue_type=issue.fields.issuetype.name,
            project=issue.fields.project.key,
            created=datetime.fromisoformat(issue.fields.created.replace('Z', '+00:00')),
            updated=datetime.fromisoformat(issue.fields.updated.replace('Z', '+00:00')),
            assignee=getattr(issue.fields.assignee, 'displayName', 'Unassigned') if issue.fields.assignee else 'Unassigned',
            reporter=getattr(issue.fields.reporter, 'displayName', 'Unknown') if issue.fields.reporter else 'Unknown',
            labels=issue.fields.labels or [],
            components=[c.name for c in issue.fields.components] or []
        )
    
    def _filter_closed_with_open_deps(self, closed_issues: List[JiraIssueData], open_issues: List[JiraIssueData]) -> List[JiraIssueData]:
        """Filter closed issues to only include those with open dependencies"""
        if not self.config['processing']['include_closed_with_open_deps']:
            return []
        
        open_keys = {issue.key for issue in open_issues}
        filtered = []
        
        for closed_issue in closed_issues:
            # Check if any open issue references this closed issue
            # This is a simplified check - in practice, you'd query JIRA for actual links
            if any(closed_issue.key in open_issue.description for open_issue in open_issues):
                filtered.append(closed_issue)
        
        return filtered
    
    @retry(stop_max_attempt_number=3, wait_exponential_multiplier=1000)
    def _fetch_github_issues(self) -> List[GitHubIssueData]:
        """Fetch GitHub issues from configured repositories"""
        self.logger.info("Fetching GitHub issues...")
        
        all_issues = []
        github_config = self.config['github']
        
        # Fetch from specific repositories
        for category, repos in github_config['repositories'].items():
            for repo_name in repos:
                try:
                    issues = self._fetch_github_repo_issues(repo_name, category)
                    all_issues.extend(issues)
                except Exception as e:
                    self.logger.error(f"Error fetching from {repo_name}: {e}")
                    continue
        
        # Fetch from collection organizations (sample)
        for org_name in github_config['collection_orgs']:
            try:
                issues = self._fetch_github_org_sample(org_name)
                all_issues.extend(issues)
            except Exception as e:
                self.logger.error(f"Error fetching from org {org_name}: {e}")
                continue
        
        self.logger.info(f"Fetched {len(all_issues)} GitHub issues")
        return all_issues
    
    def _fetch_github_repo_issues(self, repo_name: str, category: str) -> List[GitHubIssueData]:
        """Fetch issues from a specific GitHub repository"""
        repo = self.github.get_repo(repo_name)
        issues = []
        
        filters = self.config['github']['filters']
        since_date = datetime.now() - timedelta(days=filters['updated_since_days'])
        
        # Fetch issues
        for issue in repo.get_issues(state='open', since=since_date):
            if any(label.name in filters['labels_exclude'] for label in issue.labels):
                continue
                
            issues.append(self._convert_github_issue(issue, repo_name, category))
            
            if len(issues) >= self.config['github']['batch_size']:
                break
        
        time.sleep(self.config['github']['rate_limit_delay'])
        return issues
    
    def _fetch_github_org_sample(self, org_name: str, max_repos: int = 10) -> List[GitHubIssueData]:
        """Fetch a sample of issues from an organization's repositories"""
        org = self.github.get_organization(org_name)
        issues = []
        repo_count = 0
        
        for repo in org.get_repos(sort='updated', direction='desc'):
            if repo_count >= max_repos:
                break
                
            try:
                repo_issues = self._fetch_github_repo_issues(repo.full_name, 'collections')
                issues.extend(repo_issues[:10])  # Limit to 10 issues per repo
                repo_count += 1
            except Exception as e:
                self.logger.warning(f"Skipping repo {repo.full_name}: {e}")
                continue
        
        return issues
    
    def _convert_github_issue(self, issue, repo_name: str, category: str) -> GitHubIssueData:
        """Convert GitHub issue to internal data structure"""
        org_name = repo_name.split('/')[0]
        
        return GitHubIssueData(
            repository=repo_name,
            number=issue.number,
            title=issue.title,
            body=issue.body or '',
            state=issue.state,
            created=issue.created_at,
            updated=issue.updated_at,
            author=issue.user.login,
            url=issue.html_url,
            labels=[label.name for label in issue.labels],
            organization=org_name,
            issue_type='pull_request' if hasattr(issue, 'pull_request') and issue.pull_request else 'issue'
        )
    
    def _load_to_neo4j(self, jira_issues: List[JiraIssueData], github_issues: List[GitHubIssueData]):
        """Load data to Neo4j database"""
        self.logger.info("Loading data to Neo4j...")
        
        with self.neo4j_driver.session() as session:
            # Load JIRA issues
            for issue in jira_issues:
                session.execute_write(self._create_jira_issue, issue)
                self.processed_items["jira"] += 1
            
            # Load GitHub issues
            for issue in github_issues:
                session.execute_write(self._create_github_issue, issue)
                self.processed_items["github"] += 1
            
            # Create cross-references
            links_created = session.execute_write(self._create_cross_references)
            self.processed_items["links"] = links_created
            
            # Extract and link technologies
            session.execute_write(self._extract_technologies, jira_issues, github_issues)
            
            # Create component relationships
            session.execute_write(self._create_component_relationships)
    
    def _create_jira_issue(self, tx, issue: JiraIssueData):
        """Create JIRA issue node in Neo4j"""
        query = """
        MERGE (j:JiraIssue {key: $key})
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
        
        MERGE (p:JiraProject {key: $project})
        SET p.name = CASE 
            WHEN $project = 'AAPRFE' THEN 'Ansible Automation Platform RFEs'
            WHEN $project = 'ANSTRAT' THEN 'Ansible Strategy'
            ELSE $project
        END
        
        MERGE (j)-[:BELONGS_TO]->(p)
        """
        
        tx.run(query, 
            key=issue.key,
            summary=issue.summary,
            description=issue.description,
            status=issue.status,
            priority=issue.priority,
            issueType=issue.issue_type,
            project=issue.project,
            created=issue.created.isoformat(),
            updated=issue.updated.isoformat(),
            assignee=issue.assignee,
            reporter=issue.reporter,
            labels=issue.labels,
            components=issue.components
        )
    
    def _create_github_issue(self, tx, issue: GitHubIssueData):
        """Create GitHub issue node in Neo4j"""
        query = """
        MERGE (g:GitHubIssue {repository: $repository, number: $number})
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
        
        MERGE (r:GitHubRepository {fullName: $repository})
        SET r.name = split($repository, '/')[1],
            r.owner = $organization,
            r.category = $category
        
        MERGE (o:GitHubOrganization {name: $organization})
        
        MERGE (g)-[:BELONGS_TO]->(r)
        MERGE (r)-[:OWNED_BY]->(o)
        """
        
        # Determine category based on repository
        category = self._get_repo_category(issue.repository)
        
        tx.run(query,
            repository=issue.repository,
            number=issue.number,
            title=issue.title,
            body=issue.body,
            state=issue.state,
            created=issue.created.isoformat(),
            updated=issue.updated.isoformat(),
            author=issue.author,
            url=issue.url,
            labels=issue.labels,
            organization=issue.organization,
            type=issue.issue_type,
            category=category
        )
    
    def _get_repo_category(self, repo_name: str) -> str:
        """Determine repository category"""
        repo_categories = self.config['github']['repositories']
        for category, repos in repo_categories.items():
            if repo_name in repos:
                return category
        return 'collections' if 'ansible-collections' in repo_name else 'other'
    
    def _create_cross_references(self, tx) -> int:
        """Create cross-reference relationships between JIRA and GitHub"""
        patterns = self.config['processing']['jira_reference_patterns']
        links_created = 0
        
        for pattern in patterns:
            query = f"""
            MATCH (g:GitHubIssue)
            WHERE g.body IS NOT NULL OR g.title IS NOT NULL
            WITH g, 
                 [x IN apoc.text.regexGroups(coalesce(g.body, "") + " " + coalesce(g.title, ""), "{pattern}") | x[0]] AS jiraRefs
            UNWIND jiraRefs AS jiraRef
            MATCH (j:JiraIssue {{key: jiraRef}})
            MERGE (g)-[:ADDRESSES]->(j)
            MERGE (j)-[:TRACKED_IN]->(g)
            RETURN count(*) as created
            """
            
            result = tx.run(query)
            links_created += result.single()['created']
        
        return links_created
    
    def _extract_technologies(self, tx, jira_issues: List[JiraIssueData], github_issues: List[GitHubIssueData]):
        """Extract and link technology mentions"""
        tech_patterns = self.config['processing']['technology_patterns']
        
        # Process JIRA issues
        for issue in jira_issues:
            text = f"{issue.summary} {issue.description}".lower()
            for pattern in tech_patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    tech_name = match if isinstance(match, str) else match[0]
                    self._create_technology_link(tx, 'JiraIssue', issue.key, tech_name)
        
        # Process GitHub issues
        for issue in github_issues:
            text = f"{issue.title} {issue.body}".lower()
            for pattern in tech_patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    tech_name = match if isinstance(match, str) else match[0]
                    self._create_technology_link(tx, 'GitHubIssue', f"{issue.repository}#{issue.number}", tech_name)
    
    def _create_technology_link(self, tx, node_type: str, node_id: str, tech_name: str):
        """Create technology relationship"""
        if node_type == 'JiraIssue':
            query = """
            MATCH (item:JiraIssue {key: $nodeId})
            MERGE (tech:Technology {name: $techName})
            MERGE (item)-[:INVOLVES]->(tech)
            """
        else:
            repo, number = node_id.split('#')
            query = """
            MATCH (item:GitHubIssue {repository: $repo, number: $number})
            MERGE (tech:Technology {name: $techName})
            MERGE (item)-[:INVOLVES]->(tech)
            """
            tx.run(query, repo=repo, number=int(number), techName=tech_name.lower())
            return
        
        tx.run(query, nodeId=node_id, techName=tech_name.lower())
    
    def _create_component_relationships(self, tx):
        """Create component relationships based on mapping"""
        component_mapping = self.config['processing']['component_mapping']
        
        for component, keywords in component_mapping.items():
            for keyword in keywords:
                # Link JIRA issues to components
                query = """
                MATCH (j:JiraIssue)
                WHERE any(comp IN j.components WHERE toLower(comp) CONTAINS $keyword)
                   OR toLower(j.summary) CONTAINS $keyword
                   OR toLower(j.description) CONTAINS $keyword
                MERGE (c:Component {name: $component})
                MERGE (j)-[:AFFECTS]->(c)
                """
                tx.run(query, keyword=keyword.lower(), component=component)
                
                # Link GitHub repositories to components
                query = """
                MATCH (r:GitHubRepository)
                WHERE toLower(r.name) CONTAINS $keyword
                   OR toLower(r.fullName) CONTAINS $keyword
                MERGE (c:Component {name: $component})
                MERGE (r)-[:IMPLEMENTS]->(c)
                """
                tx.run(query, keyword=keyword.lower(), component=component)
    
    def run_full_sync(self):
        """Run full synchronization"""
        self.logger.info("Starting full JIRA-GitHub sync...")
        start_time = time.time()
        
        try:
            # Extract data
            jira_issues = self._fetch_jira_issues()
            github_issues = self._fetch_github_issues()
            
            # Load to Neo4j
            self._load_to_neo4j(jira_issues, github_issues)
            
            # Cleanup stale data
            self._cleanup_stale_data()
            
            duration = time.time() - start_time
            self.logger.info(f"Full sync completed in {duration:.2f}s. Processed: {self.processed_items}")
            
        except Exception as e:
            self.logger.error(f"Full sync failed: {e}")
            raise
    
    def _cleanup_stale_data(self):
        """Remove stale data from Neo4j"""
        with self.neo4j_driver.session() as session:
            session.execute_write(self._run_cleanup_query)
    
    def _run_cleanup_query(self, tx):
        """Execute cleanup query"""
        query = """
        CALL apoc.custom.callProcedure('cleanupStaleData') YIELD result
        RETURN result
        """
        result = tx.run(query)
        self.logger.info(f"Cleanup result: {result.single()['result']}")
    
    def close(self):
        """Close all connections"""
        if hasattr(self, 'neo4j_driver'):
            self.neo4j_driver.close()

def main():
    """Main entry point"""
    if len(sys.argv) != 2:
        print("Usage: python jira_github_etl.py <config_path>")
        sys.exit(1)
    
    config_path = sys.argv[1]
    etl = JiraGitHubETL(config_path)
    
    try:
        etl.run_full_sync()
    finally:
        etl.close()

if __name__ == "__main__":
    main()
