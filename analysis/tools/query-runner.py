#!/usr/bin/env python3
"""
Query Runner Tool for Graph Analysis
Executes pre-built Cypher queries and formats results for analysis
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
import csv
from neo4j import GraphDatabase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class QueryRunner:
    def __init__(self):
        self.neo4j_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        self.neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
        self.neo4j_password = os.getenv('NEO4J_PASSWORD')
        
        if not self.neo4j_password:
            raise ValueError("NEO4J_PASSWORD environment variable is required")
        
        # Initialize Neo4j driver
        self.driver = GraphDatabase.driver(
            self.neo4j_uri,
            auth=(self.neo4j_user, self.neo4j_password)
        )
        
        # Query directory
        self.query_dir = Path(__file__).parent.parent / 'queries'
        
    def list_available_queries(self) -> Dict[str, List[str]]:
        """List all available query files and their queries"""
        available = {}
        
        for query_file in self.query_dir.glob('*.cypher'):
            category = query_file.stem
            queries = self._parse_query_file(query_file)
            available[category] = [q['name'] for q in queries]
        
        return available
    
    def _parse_query_file(self, file_path: Path) -> List[Dict[str, str]]:
        """Parse a Cypher file and extract individual queries"""
        with open(file_path, 'r') as f:
            content = f.read()
        
        queries = []
        current_query = []
        current_name = None
        
        for line in content.split('\n'):
            line = line.strip()
            
            # Skip empty lines and file-level comments
            if not line or (line.startswith('//') and not current_name):
                if line.startswith('// ') and '. ' in line:
                    # This is a query name
                    current_name = line[3:].strip()
                continue
            
            # Start of new query
            if line.startswith('// ') and '. ' in line:
                # Save previous query if exists
                if current_name and current_query:
                    queries.append({
                        'name': current_name,
                        'query': '\n'.join(current_query).strip()
                    })
                
                # Start new query
                current_name = line[3:].strip()
                current_query = []
            elif current_name:
                # Add line to current query (skip comments within query)
                if not line.startswith('//'):
                    current_query.append(line)
        
        # Add final query
        if current_name and current_query:
            queries.append({
                'name': current_name,
                'query': '\n'.join(current_query).strip()
            })
        
        return queries
    
    def run_query(self, category: str, query_name: str, parameters: Dict = None) -> List[Dict]:
        """Run a specific query and return results"""
        query_file = self.query_dir / f"{category}.cypher"
        
        if not query_file.exists():
            raise ValueError(f"Query category '{category}' not found")
        
        queries = self._parse_query_file(query_file)
        target_query = None
        
        for q in queries:
            if query_name in q['name'] or q['name'].startswith(query_name):
                target_query = q['query']
                break
        
        if not target_query:
            available = [q['name'] for q in queries]
            raise ValueError(f"Query '{query_name}' not found in {category}. Available: {available}")
        
        logger.info(f"Running query: {query_name}")
        
        with self.driver.session() as session:
            result = session.run(target_query, parameters or {})
            records = [record.data() for record in result]
        
        logger.info(f"Query returned {len(records)} records")
        return records
    
    def run_all_queries_in_category(self, category: str) -> Dict[str, List[Dict]]:
        """Run all queries in a category"""
        query_file = self.query_dir / f"{category}.cypher"
        
        if not query_file.exists():
            raise ValueError(f"Query category '{category}' not found")
        
        queries = self._parse_query_file(query_file)
        results = {}
        
        for query_info in queries:
            try:
                records = self.run_query_direct(query_info['query'])
                results[query_info['name']] = records
            except Exception as e:
                logger.error(f"Failed to run query '{query_info['name']}': {e}")
                results[query_info['name']] = {'error': str(e)}
        
        return results
    
    def run_query_direct(self, query: str, parameters: Dict = None) -> List[Dict]:
        """Run a query directly from string"""
        with self.driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]
    
    def export_results(self, results: List[Dict], output_file: str, format: str = 'json'):
        """Export query results to file"""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if format.lower() == 'json':
            with open(output_path, 'w') as f:
                json.dump(results, f, indent=2, default=str)
        
        elif format.lower() == 'csv':
            if not results:
                logger.warning("No results to export")
                return
            
            with open(output_path, 'w', newline='') as f:
                if results:
                    writer = csv.DictWriter(f, fieldnames=results[0].keys())
                    writer.writeheader()
                    for row in results:
                        # Convert complex objects to strings
                        clean_row = {}
                        for k, v in row.items():
                            if isinstance(v, (list, dict)):
                                clean_row[k] = json.dumps(v, default=str)
                            else:
                                clean_row[k] = v
                        writer.writerow(clean_row)
        
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        logger.info(f"Results exported to {output_path}")
    
    def generate_report(self, category: str, output_dir: str = 'reports'):
        """Generate a comprehensive report for a query category"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_dir = Path(output_dir) / f"{category}_{timestamp}"
        report_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Generating {category} report in {report_dir}")
        
        # Run all queries in category
        results = self.run_all_queries_in_category(category)
        
        # Export individual query results
        for query_name, query_results in results.items():
            if isinstance(query_results, dict) and 'error' in query_results:
                logger.error(f"Skipping failed query: {query_name}")
                continue
            
            # Clean filename
            safe_name = "".join(c for c in query_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_name = safe_name.replace(' ', '_')
            
            # Export as JSON
            self.export_results(
                query_results, 
                report_dir / f"{safe_name}.json",
                'json'
            )
            
            # Export as CSV if results exist
            if query_results:
                self.export_results(
                    query_results,
                    report_dir / f"{safe_name}.csv", 
                    'csv'
                )
        
        # Generate summary report
        summary = {
            'category': category,
            'timestamp': timestamp,
            'queries_run': len(results),
            'successful_queries': len([r for r in results.values() if not isinstance(r, dict) or 'error' not in r]),
            'total_records': sum(len(r) for r in results.values() if isinstance(r, list)),
            'query_results': {
                name: {
                    'record_count': len(res) if isinstance(res, list) else 0,
                    'status': 'success' if isinstance(res, list) else 'error'
                }
                for name, res in results.items()
            }
        }
        
        with open(report_dir / 'summary.json', 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        logger.info(f"Report generated: {report_dir}")
        return report_dir
    
    def close(self):
        """Close Neo4j driver connection"""
        if self.driver:
            self.driver.close()

def main():
    parser = argparse.ArgumentParser(description='Run graph analysis queries')
    parser.add_argument('--list', action='store_true', help='List available queries')
    parser.add_argument('--category', help='Query category (e.g., relationship-mapping)')
    parser.add_argument('--query', help='Specific query name or partial match')
    parser.add_argument('--output', help='Output file path')
    parser.add_argument('--format', choices=['json', 'csv'], default='json', help='Output format')
    parser.add_argument('--report', action='store_true', help='Generate full category report')
    parser.add_argument('--report-dir', default='reports', help='Report output directory')
    
    args = parser.parse_args()
    
    runner = QueryRunner()
    
    try:
        if args.list:
            available = runner.list_available_queries()
            print("\nAvailable Query Categories and Queries:")
            print("=" * 50)
            for category, queries in available.items():
                print(f"\n{category.upper()}:")
                for i, query in enumerate(queries, 1):
                    print(f"  {i}. {query}")
        
        elif args.report and args.category:
            report_dir = runner.generate_report(args.category, args.report_dir)
            print(f"Report generated: {report_dir}")
        
        elif args.category and args.query:
            results = runner.run_query(args.category, args.query)
            
            if args.output:
                runner.export_results(results, args.output, args.format)
            else:
                print(json.dumps(results, indent=2, default=str))
        
        elif args.category:
            results = runner.run_all_queries_in_category(args.category)
            
            if args.output:
                # Export all results as single file
                all_results = {}
                for query_name, query_results in results.items():
                    if isinstance(query_results, list):
                        all_results[query_name] = query_results
                
                runner.export_results(all_results, args.output, args.format)
            else:
                for query_name, query_results in results.items():
                    print(f"\n=== {query_name} ===")
                    if isinstance(query_results, dict) and 'error' in query_results:
                        print(f"ERROR: {query_results['error']}")
                    else:
                        print(json.dumps(query_results[:5], indent=2, default=str))  # Show first 5 results
                        if len(query_results) > 5:
                            print(f"... and {len(query_results) - 5} more records")
        
        else:
            parser.print_help()
    
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        sys.exit(1)
    
    finally:
        runner.close()

if __name__ == "__main__":
    main()
