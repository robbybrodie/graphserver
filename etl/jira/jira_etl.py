#!/usr/bin/env python3
"""
JIRA ETL Script for Neo4j Graph Database
Extracts issues from JIRA API and loads them into Neo4j
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests
from neo4j import GraphDatabase
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class JiraETL:
    def __init__(self):
        self.jira_url = os.getenv('JIRA_URL')
        self.jira_username = os.getenv('JIRA_USERNAME')
        self.jira_api_token = os.getenv('JIRA_API_TOKEN')
        self.neo4j_uri = os.getenv('NEO4J_URI')
        self.neo4j_user = os.getenv('NEO4J_USER')
        self.neo4j_password = os.getenv('NEO4J_PASSWORD')
        self.jira_projects = os.getenv('JIRA_PROJECTS', '').split(',')
        
        # Validate required environment variables
        required_vars = [
            'JIRA_URL', 'JIRA_USERNAME', 'JIRA_API_TOKEN',
            'NEO4J_URI', 'NEO4J_USER', 'NEO4J_PASSWORD'
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {missing_vars}")
        
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
            with open('/app/config/jira-cypher', 'r') as f:
                self.jira_cypher = f.read()
        except FileNotFoundError:
            logger.warning("Cypher config not found, using default query")
            self.jira_cypher = """
            MERGE (i:Issue {key: $key})
            SET i.summary = $summary,
                i.description = $description,
                i.status = $status,
                i.priority = $priority,
                i.created = datetime($created),
                i.updated = datetime($updated)
            
            MERGE (p:Project {key: $project_key})
            SET p.name = $project_name
            
            MERGE (i)-[:BELONGS_TO]->(p)
            
            FOREACH (assignee IN CASE WHEN $assignee IS NOT NULL THEN [$assignee] ELSE [] END |
              MERGE (u:User {name: assignee})
              MERGE (i)-[:ASSIGNED_TO]->(u)
            )
            
            MERGE (r:User {name: $reporter})
            MERGE (i)-[:REPORTED_BY]->(r)
            """
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def fetch_jira_issues(self, project_key: str, start_at: int = 0, max_results: int = 100) -> Dict:
        """Fetch issues from JIRA API with retry logic"""
        url = f"{self.jira_url}/rest/api/3/search"
        
        # Get issues updated in the last 24 hours for incremental sync
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        params = {
            'jql': f'project = {project_key} AND updated >= "{yesterday}"',
            'startAt': start_at,
            'maxResults': max_results,
            'fields': 'key,summary,description,status,priority,assignee,reporter,created,updated,project'
        }
        
        response = requests.get(
            url,
            params=params,
            auth=(self.jira_username, self.jira_api_token),
            headers={'Accept': 'application/json'},
            timeout=30
        )
        
        response.raise_for_status()
        return response.json()
    
    def transform_issue(self, issue: Dict) -> Dict:
        """Transform JIRA issue to Neo4j format"""
        fields = issue['fields']
        
        return {
            'key': issue['key'],
            'summary': fields.get('summary', ''),
            'description': fields.get('description', {}).get('content', [{}])[0].get('content', [{}])[0].get('text', '') if fields.get('description') else '',
            'status': fields.get('status', {}).get('name', ''),
            'priority': fields.get('priority', {}).get('name', ''),
            'assignee': fields.get('assignee', {}).get('displayName') if fields.get('assignee') else None,
            'reporter': fields.get('reporter', {}).get('displayName', ''),
            'created': fields.get('created', ''),
            'updated': fields.get('updated', ''),
            'project_key': fields.get('project', {}).get('key', ''),
            'project_name': fields.get('project', {}).get('name', '')
        }
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def load_to_neo4j(self, issues: List[Dict]):
        """Load transformed issues into Neo4j"""
        with self.driver.session() as session:
            for issue in issues:
                try:
                    session.run(self.jira_cypher, issue)
                    logger.info(f"Loaded issue: {issue['key']}")
                except Exception as e:
                    logger.error(f"Failed to load issue {issue['key']}: {e}")
    
    def run_etl(self):
        """Run the complete ETL process"""
        logger.info("Starting JIRA ETL process")
        
        total_issues = 0
        
        for project_key in self.jira_projects:
            if not project_key.strip():
                continue
                
            logger.info(f"Processing project: {project_key}")
            
            start_at = 0
            max_results = 100
            
            while True:
                try:
                    # Fetch issues from JIRA
                    response = self.fetch_jira_issues(project_key, start_at, max_results)
                    issues = response.get('issues', [])
                    
                    if not issues:
                        break
                    
                    # Transform issues
                    transformed_issues = [self.transform_issue(issue) for issue in issues]
                    
                    # Load to Neo4j
                    self.load_to_neo4j(transformed_issues)
                    
                    total_issues += len(issues)
                    logger.info(f"Processed {len(issues)} issues from {project_key}")
                    
                    # Check if we've reached the end
                    if len(issues) < max_results:
                        break
                    
                    start_at += max_results
                    
                except Exception as e:
                    logger.error(f"Error processing project {project_key}: {e}")
                    break
        
        logger.info(f"JIRA ETL completed. Total issues processed: {total_issues}")
    
    def close(self):
        """Close Neo4j driver connection"""
        if self.driver:
            self.driver.close()

def main():
    etl = None
    try:
        etl = JiraETL()
        etl.run_etl()
    except Exception as e:
        logger.error(f"ETL process failed: {e}")
        sys.exit(1)
    finally:
        if etl:
            etl.close()

if __name__ == "__main__":
    main()
