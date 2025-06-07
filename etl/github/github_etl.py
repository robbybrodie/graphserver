#!/usr/bin/env python3
"""
GitHub ETL Script for Neo4j Graph Database
Extracts issues, PRs, and repository data from GitHub API and loads them into Neo4j
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from github import Github
from neo4j import GraphDatabase
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GitHubETL:
    def __init__(self):
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.github_repos = os.getenv('GITHUB_REPOS', '').split(',')
        self.neo4j_uri = os.getenv('NEO4J_URI')
        self.neo4j_user = os.getenv('NEO4J_USER')
        self.neo4j_password = os.getenv('NEO4J_PASSWORD')
        
        # Validate required environment variables
        required_vars = [
            'GITHUB_TOKEN', 'GITHUB_REPOS',
            'NEO4J_URI', 'NEO4J_USER', 'NEO4J_PASSWORD'
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {missing_vars}")
        
        # Initialize GitHub client
        self.github = Github(self.github_token)
        
        # Initialize Neo4j driver
        self.driver = GraphDatabase.driver(
            self.neo4j_uri,
            auth=(self.neo4j_user, self.neo4j_password)
        )
        
        # Load Cypher queries from config
        self.load_cypher_queries()
    
    def load_cypher_queries(self):
        """Load Cypher queries from mounted config"""
        try:
            with open('/app/config/github-cypher', 'r') as f:
                self.github_cypher = f.read()
        except FileNotFoundError:
            logger.warning("Cypher config not found, using default query")
            self.github_cypher = """
            MERGE (i:GitHubIssue {number: $number, repo: $repo})
            SET i.title = $title,
                i.body = $body,
                i.state = $state,
                i.created = datetime($created),
                i.updated = datetime($updated)
            
            MERGE (r:Repository {name: $repo})
            SET r.owner = $owner,
                r.full_name = $full_name
            
            MERGE (i)-[:BELONGS_TO]->(r)
            
            MERGE (u:User {login: $author})
            MERGE (i)-[:CREATED_BY]->(u)
            
            FOREACH (assignee IN $assignees |
              MERGE (a:User {login: assignee})
              MERGE (i)-[:ASSIGNED_TO]->(a)
            )
            
            FOREACH (label IN $labels |
              MERGE (l:Label {name: label})
              MERGE (i)-[:HAS_LABEL]->(l)
            )
            """
    
    def fetch_repository_issues(self, repo_full_name: str) -> List[Dict]:
        """Fetch issues from a GitHub repository"""
        try:
            repo = self.github.get_repo(repo_full_name)
            
            # Get issues updated in the last 24 hours for incremental sync
            since = datetime.now() - timedelta(days=1)
            
            issues = []
            for issue in repo.get_issues(state='all', since=since):
                # Skip pull requests (they appear as issues in GitHub API)
                if issue.pull_request:
                    continue
                
                issue_data = {
                    'number': issue.number,
                    'title': issue.title,
                    'body': issue.body or '',
                    'state': issue.state,
                    'created': issue.created_at.isoformat(),
                    'updated': issue.updated_at.isoformat(),
                    'repository': repo.full_name,
                    'organization': repo.owner.login,
                    'author': issue.user.login,
                    'url': issue.html_url,
                    'assignees': [assignee.login for assignee in issue.assignees],
                    'labels': [label.name for label in issue.labels]
                }
                issues.append(issue_data)
            
            return issues
            
        except Exception as e:
            logger.error(f"Error fetching issues from {repo_full_name}: {e}")
            return []
    
    def fetch_repository_prs(self, repo_full_name: str) -> List[Dict]:
        """Fetch pull requests from a GitHub repository"""
        try:
            repo = self.github.get_repo(repo_full_name)
            
            # Get PRs updated in the last 24 hours for incremental sync
            since = datetime.now() - timedelta(days=1)
            
            prs = []
            for pr in repo.get_pulls(state='all', sort='updated', direction='desc'):
                # Only get PRs updated since yesterday
                if pr.updated_at < since:
                    break
                
                pr_data = {
                    'number': pr.number,
                    'title': pr.title,
                    'body': pr.body or '',
                    'state': pr.state,
                    'created': pr.created_at.isoformat(),
                    'updated': pr.updated_at.isoformat(),
                    'merged': pr.merged,
                    'merged_at': pr.merged_at.isoformat() if pr.merged_at else None,
                    'repository': repo.full_name,
                    'organization': repo.owner.login,
                    'author': pr.user.login,
                    'url': pr.html_url,
                    'assignees': [assignee.login for assignee in pr.assignees],
                    'labels': [label.name for label in pr.labels],
                    'base_branch': pr.base.ref,
                    'head_branch': pr.head.ref
                }
                prs.append(pr_data)
            
            return prs
            
        except Exception as e:
            logger.error(f"Error fetching PRs from {repo_full_name}: {e}")
            return []
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def load_issues_to_neo4j(self, issues: List[Dict]):
        """Load GitHub issues into Neo4j"""
        with self.driver.session() as session:
            for issue in issues:
                try:
                    session.run(self.github_cypher, issue)
                    logger.info(f"Loaded issue: {issue['repository']}#{issue['number']}")
                except Exception as e:
                    logger.error(f"Failed to load issue {issue['repository']}#{issue['number']}: {e}")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def load_prs_to_neo4j(self, prs: List[Dict]):
        """Load GitHub pull requests into Neo4j"""
        # Use the same Cypher query from config for PRs
        try:
            with open('/app/config/github-pr-cypher', 'r') as f:
                pr_cypher = f.read()
        except FileNotFoundError:
            logger.warning("PR Cypher config not found, using default query")
            pr_cypher = """
            MERGE (pr:PullRequest {repository: $repository, number: $number})
            SET pr.title = $title,
                pr.body = $body,
                pr.state = $state,
                pr.merged = $merged,
                pr.created = datetime($created),
                pr.updated = datetime($updated),
                pr.merged_at = CASE WHEN $merged_at IS NOT NULL THEN datetime($merged_at) ELSE NULL END,
                pr.author = $author,
                pr.url = $url,
                pr.base_branch = $base_branch,
                pr.head_branch = $head_branch,
                pr.labels = $labels,
                pr.organization = $organization,
                pr.lastSynced = datetime()
            
            MERGE (r:Repository {full_name: $repository})
            SET r.name = split($repository, '/')[1],
                r.owner = $organization
            
            MERGE (o:GitHubOrganization {name: $organization})
            
            MERGE (pr)-[:BELONGS_TO]->(r)
            MERGE (r)-[:OWNED_BY]->(o)
            
            MERGE (u:User {name: $author})
            MERGE (pr)-[:CREATED_BY]->(u)
            
            FOREACH (label IN $labels |
              MERGE (l:Label {name: label})
              MERGE (pr)-[:HAS_LABEL]->(l)
            )
            """
        
        with self.driver.session() as session:
            for pr in prs:
                try:
                    session.run(pr_cypher, pr)
                    logger.info(f"Loaded PR: {pr['repository']}#{pr['number']}")
                except Exception as e:
                    logger.error(f"Failed to load PR {pr['repository']}#{pr['number']}: {e}")
    
    def run_etl(self):
        """Run the complete ETL process"""
        logger.info("Starting GitHub ETL process")
        
        total_issues = 0
        total_prs = 0
        
        for repo_name in self.github_repos:
            if not repo_name.strip():
                continue
                
            logger.info(f"Processing repository: {repo_name}")
            
            try:
                # Fetch and load issues
                issues = self.fetch_repository_issues(repo_name)
                if issues:
                    self.load_issues_to_neo4j(issues)
                    total_issues += len(issues)
                    logger.info(f"Processed {len(issues)} issues from {repo_name}")
                
                # Fetch and load pull requests
                prs = self.fetch_repository_prs(repo_name)
                if prs:
                    self.load_prs_to_neo4j(prs)
                    total_prs += len(prs)
                    logger.info(f"Processed {len(prs)} PRs from {repo_name}")
                
            except Exception as e:
                logger.error(f"Error processing repository {repo_name}: {e}")
                continue
        
        logger.info(f"GitHub ETL completed. Total issues: {total_issues}, Total PRs: {total_prs}")
    
    def close(self):
        """Close Neo4j driver connection"""
        if self.driver:
            self.driver.close()

def main():
    etl = None
    try:
        etl = GitHubETL()
        etl.run_etl()
    except Exception as e:
        logger.error(f"ETL process failed: {e}")
        sys.exit(1)
    finally:
        if etl:
            etl.close()

if __name__ == "__main__":
    main()
