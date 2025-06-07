#!/usr/bin/env python3
"""
Cross-Reference ETL Script for Neo4j Graph Database
Identifies and creates relationships between Jira and GitHub items
based on text analysis and key matching patterns.

This script runs after the discrete Jira and GitHub ETL processes
and creates the cross-system relationships that enable analysis.
"""

import os
import sys
import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
import requests
from neo4j import GraphDatabase
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CrossReferenceETL:
    def __init__(self):
        self.neo4j_uri = os.getenv('NEO4J_URI')
        self.neo4j_user = os.getenv('NEO4J_USER')
        self.neo4j_password = os.getenv('NEO4J_PASSWORD')
        
        # Validate required environment variables
        required_vars = ['NEO4J_URI', 'NEO4J_USER', 'NEO4J_PASSWORD']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {missing_vars}")
        
        # Initialize Neo4j driver
        self.driver = GraphDatabase.driver(
            self.neo4j_uri,
            auth=(self.neo4j_user, self.neo4j_password)
        )
        
        # Load configuration
        self.load_configuration()
        
        # Statistics tracking
        self.stats = {
            'jira_github_links': 0,
            'github_jira_links': 0,
            'technology_extractions': 0,
            'component_mappings': 0,
            'hierarchy_relationships': 0
        }
    
    def load_configuration(self):
        """Load cross-reference patterns and configuration"""
        try:
            with open('/app/config/cross-reference-config', 'r') as f:
                config = json.load(f)
                self.jira_patterns = config.get('jira_patterns', [
                    r'[A-Z]+-\d+',  # Standard Jira keys like ABC-123
                    r'JIRA[:\s]+([A-Z]+-\d+)',  # "JIRA: ABC-123"
                    r'jira\..*?([A-Z]+-\d+)',  # URLs with Jira keys
                ])
                self.github_patterns = config.get('github_patterns', [
                    r'#(\d+)',  # Issue numbers like #123
                    r'github\.com/[\w-]+/[\w-]+/issues/(\d+)',  # Full GitHub URLs
                    r'GH[:\s]+#?(\d+)',  # "GH: #123" or "GH: 123"
                ])
                self.technology_patterns = config.get('technology_patterns', [
                    r'\b(ansible|python|kubernetes|openshift|docker|podman)\b',
                    r'\b(terraform|helm|yaml|json|api)\b',
                    r'\b(automation|devops|ci/cd|pipeline)\b'
                ])
                self.component_mapping = config.get('component_mapping', {
                    'automation-platform': ['ansible', 'automation', 'aap'],
                    'container-platform': ['kubernetes', 'openshift', 'k8s'],
                    'ci-cd': ['pipeline', 'ci/cd', 'jenkins', 'tekton'],
                    'infrastructure': ['terraform', 'infrastructure', 'iac']
                })
        except FileNotFoundError:
            logger.warning("Cross-reference config not found, using defaults")
            self._set_default_patterns()
    
    def _set_default_patterns(self):
        """Set default patterns when config file is not available"""
        self.jira_patterns = [r'[A-Z]+-\d+']
        self.github_patterns = [r'#(\d+)']
        self.technology_patterns = [r'\b(ansible|python|kubernetes)\b']
        self.component_mapping = {
            'automation': ['ansible', 'automation'],
            'platform': ['kubernetes', 'openshift']
        }
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def create_jira_github_references(self):
        """Create relationships from GitHub items to Jira items"""
        logger.info("Creating Jira-GitHub cross-references...")
        
        with self.driver.session() as session:
            for pattern in self.jira_patterns:
                # Find GitHub issues that reference Jira keys
                query = """
                MATCH (g:GitHubIssue)
                WHERE g.title IS NOT NULL OR g.body IS NOT NULL
                WITH g, 
                     apoc.text.regexGroups(coalesce(g.title, '') + ' ' + coalesce(g.body, ''), $pattern) AS matches
                UNWIND matches AS match
                WITH g, match[0] AS jiraKey
                WHERE jiraKey IS NOT NULL
                MATCH (j:Issue {key: jiraKey})
                MERGE (g)-[:ADDRESSES]->(j)
                MERGE (j)-[:TRACKED_IN]->(g)
                RETURN count(*) as links_created
                """
                
                result = session.run(query, pattern=pattern)
                links = result.single()['links_created']
                self.stats['jira_github_links'] += links
                logger.info(f"Created {links} GitHub->Jira links with pattern: {pattern}")
                
                # Find GitHub PRs that reference Jira keys
                query = """
                MATCH (pr:PullRequest)
                WHERE pr.title IS NOT NULL OR pr.body IS NOT NULL
                WITH pr, 
                     apoc.text.regexGroups(coalesce(pr.title, '') + ' ' + coalesce(pr.body, ''), $pattern) AS matches
                UNWIND matches AS match
                WITH pr, match[0] AS jiraKey
                WHERE jiraKey IS NOT NULL
                MATCH (j:Issue {key: jiraKey})
                MERGE (pr)-[:IMPLEMENTS]->(j)
                MERGE (j)-[:IMPLEMENTED_IN]->(pr)
                RETURN count(*) as links_created
                """
                
                result = session.run(query, pattern=pattern)
                links = result.single()['links_created']
                self.stats['jira_github_links'] += links
                logger.info(f"Created {links} PR->Jira links with pattern: {pattern}")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def create_github_jira_references(self):
        """Create relationships from Jira items to GitHub items"""
        logger.info("Creating GitHub-Jira cross-references...")
        
        with self.driver.session() as session:
            for pattern in self.github_patterns:
                # Find Jira issues that reference GitHub issue numbers
                # This is more complex as we need repository context
                query = """
                MATCH (j:Issue)
                WHERE j.description IS NOT NULL OR j.summary IS NOT NULL
                WITH j, 
                     apoc.text.regexGroups(coalesce(j.description, '') + ' ' + coalesce(j.summary, ''), $pattern) AS matches
                UNWIND matches AS match
                WITH j, match[1] AS githubNumber
                WHERE githubNumber IS NOT NULL
                // Try to find matching GitHub issues (may need repository context)
                MATCH (g:GitHubIssue {number: toInteger(githubNumber)})
                // Create relationship if we find a match
                MERGE (j)-[:REFERENCES]->(g)
                MERGE (g)-[:REFERENCED_BY]->(j)
                RETURN count(*) as links_created
                """
                
                result = session.run(query, pattern=pattern)
                links = result.single()['links_created']
                self.stats['github_jira_links'] += links
                logger.info(f"Created {links} Jira->GitHub links with pattern: {pattern}")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def extract_technologies(self):
        """Extract technology mentions and create relationships"""
        logger.info("Extracting technology mentions...")
        
        with self.driver.session() as session:
            for pattern in self.technology_patterns:
                # Extract from Jira issues
                query = """
                MATCH (j:Issue)
                WHERE j.description IS NOT NULL OR j.summary IS NOT NULL
                WITH j, 
                     apoc.text.regexGroups(toLower(coalesce(j.description, '') + ' ' + coalesce(j.summary, '')), $pattern) AS matches
                UNWIND matches AS match
                WITH j, match[0] AS tech
                WHERE tech IS NOT NULL
                MERGE (t:Technology {name: tech})
                MERGE (j)-[:INVOLVES]->(t)
                RETURN count(*) as extractions
                """
                
                result = session.run(query, pattern=pattern)
                extractions = result.single()['extractions']
                self.stats['technology_extractions'] += extractions
                
                # Extract from GitHub issues
                query = """
                MATCH (g:GitHubIssue)
                WHERE g.body IS NOT NULL OR g.title IS NOT NULL
                WITH g, 
                     apoc.text.regexGroups(toLower(coalesce(g.body, '') + ' ' + coalesce(g.title, '')), $pattern) AS matches
                UNWIND matches AS match
                WITH g, match[0] AS tech
                WHERE tech IS NOT NULL
                MERGE (t:Technology {name: tech})
                MERGE (g)-[:INVOLVES]->(t)
                RETURN count(*) as extractions
                """
                
                result = session.run(query, pattern=pattern)
                extractions += result.single()['extractions']
                
                # Extract from GitHub PRs
                query = """
                MATCH (pr:PullRequest)
                WHERE pr.body IS NOT NULL OR pr.title IS NOT NULL
                WITH pr, 
                     apoc.text.regexGroups(toLower(coalesce(pr.body, '') + ' ' + coalesce(pr.title, '')), $pattern) AS matches
                UNWIND matches AS match
                WITH pr, match[0] AS tech
                WHERE tech IS NOT NULL
                MERGE (t:Technology {name: tech})
                MERGE (pr)-[:INVOLVES]->(t)
                RETURN count(*) as extractions
                """
                
                result = session.run(query, pattern=pattern)
                extractions += result.single()['extractions']
                
                logger.info(f"Extracted {extractions} technology mentions with pattern: {pattern}")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def create_component_mappings(self):
        """Create component relationships based on keyword mapping"""
        logger.info("Creating component mappings...")
        
        with self.driver.session() as session:
            for component, keywords in self.component_mapping.items():
                for keyword in keywords:
                    # Map Jira issues to components
                    query = """
                    MATCH (j:Issue)
                    WHERE toLower(j.summary) CONTAINS $keyword 
                       OR toLower(j.description) CONTAINS $keyword
                       OR any(comp IN j.components WHERE toLower(comp) CONTAINS $keyword)
                    MERGE (c:Component {name: $component})
                    MERGE (j)-[:AFFECTS]->(c)
                    RETURN count(*) as mappings
                    """
                    
                    result = session.run(query, keyword=keyword.lower(), component=component)
                    mappings = result.single()['mappings']
                    self.stats['component_mappings'] += mappings
                    
                    # Map GitHub repositories to components
                    query = """
                    MATCH (r:Repository)
                    WHERE toLower(r.name) CONTAINS $keyword 
                       OR toLower(r.full_name) CONTAINS $keyword
                    MERGE (c:Component {name: $component})
                    MERGE (r)-[:IMPLEMENTS]->(c)
                    RETURN count(*) as mappings
                    """
                    
                    result = session.run(query, keyword=keyword.lower(), component=component)
                    mappings += result.single()['mappings']
                    
                    # Map GitHub issues to components via repository
                    query = """
                    MATCH (g:GitHubIssue)-[:BELONGS_TO]->(r:Repository)-[:IMPLEMENTS]->(c:Component {name: $component})
                    MERGE (g)-[:RELATES_TO]->(c)
                    RETURN count(*) as mappings
                    """
                    
                    result = session.run(query, component=component)
                    mappings += result.single()['mappings']
                    
                    logger.info(f"Created {mappings} component mappings for {component} with keyword: {keyword}")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def create_hierarchy_relationships(self):
        """Create hierarchy relationships within Jira issues"""
        logger.info("Creating Jira hierarchy relationships...")
        
        with self.driver.session() as session:
            # Create Epic -> Story relationships
            query = """
            MATCH (epic:Issue {issueType: 'Epic'})
            MATCH (story:Issue {issueType: 'Story'})
            WHERE story.description CONTAINS epic.key 
               OR story.summary CONTAINS epic.key
               OR epic.key IN story.labels
            MERGE (story)-[:CHILD_OF]->(epic)
            MERGE (epic)-[:PARENT_OF]->(story)
            RETURN count(*) as relationships
            """
            
            result = session.run(query)
            relationships = result.single()['relationships']
            self.stats['hierarchy_relationships'] += relationships
            logger.info(f"Created {relationships} Epic->Story relationships")
            
            # Create Story -> Task relationships
            query = """
            MATCH (story:Issue {issueType: 'Story'})
            MATCH (task:Issue)
            WHERE task.issueType IN ['Task', 'Sub-task', 'Bug']
              AND (task.description CONTAINS story.key 
                   OR task.summary CONTAINS story.key
                   OR story.key IN task.labels)
            MERGE (task)-[:CHILD_OF]->(story)
            MERGE (story)-[:PARENT_OF]->(task)
            RETURN count(*) as relationships
            """
            
            result = session.run(query)
            relationships = result.single()['relationships']
            self.stats['hierarchy_relationships'] += relationships
            logger.info(f"Created {relationships} Story->Task relationships")
            
            # Create project relationships
            query = """
            MATCH (issue:Issue)
            MERGE (p:Project {key: issue.project})
            MERGE (issue)-[:BELONGS_TO]->(p)
            RETURN count(*) as relationships
            """
            
            result = session.run(query)
            relationships = result.single()['relationships']
            logger.info(f"Created {relationships} Issue->Project relationships")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def create_user_relationships(self):
        """Create user relationships across systems"""
        logger.info("Creating user relationships...")
        
        with self.driver.session() as session:
            # Link users across systems by email/username matching
            query = """
            MATCH (j:Issue)
            WHERE j.assignee IS NOT NULL
            MERGE (u:User {name: j.assignee})
            MERGE (j)-[:ASSIGNED_TO]->(u)
            RETURN count(*) as relationships
            """
            
            result = session.run(query)
            relationships = result.single()['relationships']
            logger.info(f"Created {relationships} Jira user assignments")
            
            query = """
            MATCH (g:GitHubIssue)
            WHERE g.author IS NOT NULL
            MERGE (u:User {name: g.author})
            MERGE (g)-[:CREATED_BY]->(u)
            RETURN count(*) as relationships
            """
            
            result = session.run(query)
            relationships = result.single()['relationships']
            logger.info(f"Created {relationships} GitHub user relationships")
    
    def run_cross_reference_processing(self):
        """Run the complete cross-reference processing"""
        logger.info("Starting cross-reference ETL process")
        start_time = datetime.now()
        
        try:
            # Create cross-system references
            self.create_jira_github_references()
            self.create_github_jira_references()
            
            # Extract and link technologies
            self.extract_technologies()
            
            # Create component mappings
            self.create_component_mappings()
            
            # Create hierarchy relationships
            self.create_hierarchy_relationships()
            
            # Create user relationships
            self.create_user_relationships()
            
            # Update processing timestamp
            self.update_processing_metadata()
            
            duration = datetime.now() - start_time
            logger.info(f"Cross-reference processing completed in {duration}")
            logger.info(f"Statistics: {self.stats}")
            
        except Exception as e:
            logger.error(f"Cross-reference processing failed: {e}")
            raise
    
    def update_processing_metadata(self):
        """Update metadata about the processing run"""
        with self.driver.session() as session:
            query = """
            MERGE (meta:ProcessingMetadata {type: 'cross_reference'})
            SET meta.last_run = datetime(),
                meta.jira_github_links = $jira_github_links,
                meta.github_jira_links = $github_jira_links,
                meta.technology_extractions = $technology_extractions,
                meta.component_mappings = $component_mappings,
                meta.hierarchy_relationships = $hierarchy_relationships
            """
            
            session.run(query, **self.stats)
    
    def close(self):
        """Close Neo4j driver connection"""
        if self.driver:
            self.driver.close()

def main():
    etl = None
    try:
        etl = CrossReferenceETL()
        etl.run_cross_reference_processing()
    except Exception as e:
        logger.error(f"Cross-reference ETL process failed: {e}")
        sys.exit(1)
    finally:
        if etl:
            etl.close()

if __name__ == "__main__":
    main()
