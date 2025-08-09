
import os
import csv
from crawler import WebsiteCrawler
from datetime import datetime
import urllib.parse

def run_crawler_audit(domain, max_depth=2, max_pages=50, delay=1.0):
    """
    Run crawler audit and return results for integration with SEO audit tool
    
    Args:
        domain (str): Domain to crawl
        max_depth (int): Maximum crawl depth
        max_pages (int): Maximum pages to crawl
        delay (float): Delay between requests
    
    Returns:
        dict: Results containing broken links and orphan pages data
    """
    # Initialize crawler with reasonable defaults for SEO audit integration
    crawler = WebsiteCrawler(
        base_domain=domain,
        max_depth=max_depth,
        delay=delay,
        max_pages=max_pages,
        respect_robots=True
    )
    
    # Perform crawl
    crawler.crawl_website()
    
    # Find orphan pages
    orphan_pages = crawler.find_orphan_pages()
    
    # Return structured results
    return {
        'broken_links': crawler.broken_links,
        'orphan_pages': orphan_pages,
        'crawl_stats': {
            'pages_crawled': len(crawler.crawled_pages),
            'broken_links_count': len(crawler.broken_links),
            'orphan_pages_count': len([p for p in orphan_pages if p['internally_linked'] == 'No']),
            'sitemap_urls_count': len(crawler.sitemap_urls)
        }
    }

def save_crawler_results_csv(results, domain, output_dir='reports'):
    """
    Save crawler results to CSV files
    
    Args:
        results (dict): Results from run_crawler_audit
        domain (str): Domain name for filename
        output_dir (str): Output directory
    
    Returns:
        tuple: (broken_links_file, orphan_pages_file) paths
    """
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate timestamp and clean domain name
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    domain_name = urllib.parse.urlparse(domain).netloc.replace('.', '_')
    
    # File paths
    broken_links_file = os.path.join(output_dir, f'broken_links_{domain_name}_{timestamp}.csv')
    orphan_pages_file = os.path.join(output_dir, f'orphan_pages_{domain_name}_{timestamp}.csv')
    
    # Save broken links
    with open(broken_links_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Source Page URL', 'Broken Link URL', 'Anchor Text / Current Value', 'Link Type', 'Status Code']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for link in results['broken_links']:
            writer.writerow({
                'Source Page URL': link['source_page'],
                'Broken Link URL': link['broken_url'],
                'Anchor Text / Current Value': link['anchor_text'],
                'Link Type': link['link_type'],
                'Status Code': link['status_code']
            })
    
    # Save orphan pages
    with open(orphan_pages_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Orphan Page URL', 'Found in Sitemap?', 'Internally Linked?']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for page in results['orphan_pages']:
            writer.writerow({
                'Orphan Page URL': page['url'],
                'Found in Sitemap?': page['found_in_sitemap'],
                'Internally Linked?': page['internally_linked']
            })
    
    return broken_links_file, orphan_pages_file

# Example usage for testing
if __name__ == '__main__':
    # Test the integration
    domain = 'https://example.com'
    results = run_crawler_audit(domain, max_depth=2, max_pages=20)
    
    # Save results
    broken_file, orphan_file = save_crawler_results_csv(results, domain)
    
    print(f"Crawler audit complete!")
    print(f"Pages crawled: {results['crawl_stats']['pages_crawled']}")
    print(f"Broken links: {results['crawl_stats']['broken_links_count']}")
    print(f"Orphan pages: {results['crawl_stats']['orphan_pages_count']}")
    print(f"Results saved to: {broken_file}, {orphan_file}")
