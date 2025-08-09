
import requests
from bs4 import BeautifulSoup
import urllib.parse
import csv
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import xml.etree.ElementTree as ET
import re
import logging
from urllib.robotparser import RobotFileParser
from collections import deque
import argparse
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WebsiteCrawler:
    def __init__(self, base_domain, max_depth=3, delay=1.0, max_pages=200, respect_robots=True):
        self.base_domain = base_domain.rstrip('/')
        self.domain = urllib.parse.urlparse(base_domain).netloc
        self.max_depth = max_depth
        self.delay = delay
        self.max_pages = max_pages
        self.respect_robots = respect_robots
        
        # Tracking sets
        self.visited_urls = set()
        self.crawled_pages = set()
        self.all_internal_links = set()
        self.broken_links = []
        self.sitemap_urls = set()
        
        # Session for reusing connections
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; SEO-Crawler/1.0; +https://example.com/bot)'
        })
        
        # Robots.txt parser
        self.rp = None
        if respect_robots:
            self._load_robots_txt()
    
    def _load_robots_txt(self):
        """Load and parse robots.txt"""
        try:
            robots_url = f"{self.base_domain}/robots.txt"
            self.rp = RobotFileParser()
            self.rp.set_url(robots_url)
            self.rp.read()
            logger.info(f"Loaded robots.txt from {robots_url}")
        except Exception as e:
            logger.warning(f"Could not load robots.txt: {e}")
            self.rp = None
    
    def _can_fetch(self, url):
        """Check if URL can be fetched according to robots.txt"""
        if not self.rp:
            return True
        return self.rp.can_fetch('*', url)
    
    def _is_internal_url(self, url):
        """Check if URL is internal to the domain"""
        parsed = urllib.parse.urlparse(url)
        return parsed.netloc == self.domain or parsed.netloc == ''
    
    def _normalize_url(self, url):
        """Normalize URL by removing fragments and optional query parameters"""
        parsed = urllib.parse.urlparse(url)
        # Remove fragment
        normalized = urllib.parse.urlunparse((
            parsed.scheme, parsed.netloc, parsed.path, 
            parsed.params, parsed.query, ''
        ))
        return normalized.rstrip('/')
    
    def _resolve_url(self, base_url, link):
        """Resolve relative URLs to absolute URLs"""
        if not link:
            return None
        
        # Handle javascript: and mailto: links
        if link.startswith(('javascript:', 'mailto:', 'tel:', '#')):
            return None
        
        # Resolve relative URLs
        absolute_url = urllib.parse.urljoin(base_url, link)
        return self._normalize_url(absolute_url)
    
    def _extract_anchor_info(self, link_element):
        """Extract anchor text, image alt, or icon info from link element"""
        # Check for image inside link
        img = link_element.find('img')
        if img:
            alt_text = img.get('alt', '').strip()
            return f"Image: {alt_text}" if alt_text else "Image: (no alt text)"
        
        # Check for icon inside link
        icon = link_element.find('i')
        if icon:
            icon_class = icon.get('class', [])
            if isinstance(icon_class, list):
                icon_class = ' '.join(icon_class)
            return f"Icon: {icon_class}" if icon_class else "Icon: (no class)"
        
        # Get text content
        text = link_element.get_text(strip=True)
        return text if text else "(no anchor text)"
    
    def _get_page_content(self, url):
        """Fetch page content with error handling"""
        try:
            if self.respect_robots and not self._can_fetch(url):
                logger.info(f"Robots.txt disallows crawling: {url}")
                return None
            
            response = self.session.get(url, timeout=10, allow_redirects=True)
            response.raise_for_status()
            
            # Only process HTML content
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' not in content_type:
                return None
            
            return response.text, response.url  # Return final URL after redirects
        
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def _check_link_status(self, url):
        """Check if a link is broken by testing HTTP status"""
        try:
            # Try HEAD request first
            response = self.session.head(url, timeout=10, allow_redirects=True)
            return response.status_code
        except:
            try:
                # Fallback to GET request
                response = self.session.get(url, timeout=10, allow_redirects=True)
                return response.status_code
            except:
                return 0  # Connection error
    
    def _crawl_page(self, url, depth):
        """Crawl a single page and extract links"""
        if depth > self.max_depth or len(self.crawled_pages) >= self.max_pages:
            return []
        
        if url in self.visited_urls:
            return []
        
        self.visited_urls.add(url)
        logger.info(f"Crawling: {url} (depth: {depth})")
        
        # Fetch page content
        content_result = self._get_page_content(url)
        if not content_result:
            return []
        
        content, final_url = content_result
        self.crawled_pages.add(final_url)
        
        # Parse HTML
        soup = BeautifulSoup(content, 'html.parser')
        
        # Extract all links
        links = []
        found_links = []
        
        for link_element in soup.find_all('a', href=True):
            href = link_element.get('href')
            absolute_url = self._resolve_url(final_url, href)
            
            if not absolute_url:
                continue
            
            # Extract anchor information
            anchor_info = self._extract_anchor_info(link_element)
            
            # Determine if internal or external
            is_internal = self._is_internal_url(absolute_url)
            link_type = "Internal" if is_internal else "External"
            
            # Store link info
            link_info = {
                'source_page': final_url,
                'target_url': absolute_url,
                'anchor_text': anchor_info,
                'link_type': link_type,
                'link_element': link_element
            }
            
            found_links.append(link_info)
            
            # Add internal links to crawling queue and tracking set
            if is_internal and absolute_url not in self.visited_urls:
                links.append(absolute_url)
                self.all_internal_links.add(absolute_url)
        
        # Check all found links for broken status
        self._check_links_batch(found_links)
        
        # Add delay between requests
        time.sleep(self.delay)
        
        return links
    
    def _check_links_batch(self, link_infos):
        """Check multiple links for broken status using threading"""
        def check_single_link(link_info):
            url = link_info['target_url']
            status_code = self._check_link_status(url)
            
            # Mark as broken if status code >= 400 or connection error
            if status_code >= 400 or status_code == 0:
                self.broken_links.append({
                    'source_page': link_info['source_page'],
                    'broken_url': url,
                    'anchor_text': link_info['anchor_text'],
                    'link_type': link_info['link_type'],
                    'status_code': status_code if status_code > 0 else 'Connection Error'
                })
                logger.warning(f"Broken link found: {url} (Status: {status_code})")
        
        # Use threading for link checking
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(check_single_link, link_info) for link_info in link_infos]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error checking link: {e}")
    
    def crawl_website(self):
        """Main crawling method using BFS"""
        logger.info(f"Starting crawl of {self.base_domain}")
        
        # Initialize queue with base domain
        queue = deque([(self.base_domain, 0)])
        
        while queue and len(self.crawled_pages) < self.max_pages:
            url, depth = queue.popleft()
            
            # Get links from current page
            new_links = self._crawl_page(url, depth)
            
            # Add new links to queue
            for link in new_links:
                if link not in self.visited_urls:
                    queue.append((link, depth + 1))
        
        logger.info(f"Crawl complete. Visited {len(self.crawled_pages)} pages, found {len(self.broken_links)} broken links")
    
    def _fetch_sitemap(self, sitemap_url=None):
        """Fetch and parse sitemap.xml"""
        if not sitemap_url:
            sitemap_url = f"{self.base_domain}/sitemap.xml"
        
        try:
            response = self.session.get(sitemap_url, timeout=10)
            response.raise_for_status()
            
            # Parse XML
            root = ET.fromstring(response.content)
            
            # Handle different sitemap formats
            namespaces = {
                'sitemap': 'http://www.sitemaps.org/schemas/sitemap/0.9'
            }
            
            urls = set()
            
            # Check for sitemap index
            for sitemap in root.findall('.//sitemap:sitemap', namespaces):
                loc_element = sitemap.find('sitemap:loc', namespaces)
                if loc_element is not None:
                    # Recursively fetch sub-sitemaps
                    sub_urls = self._fetch_sitemap(loc_element.text)
                    urls.update(sub_urls)
            
            # Extract URL locations
            for url_element in root.findall('.//sitemap:url', namespaces):
                loc_element = url_element.find('sitemap:loc', namespaces)
                if loc_element is not None:
                    clean_url = self._normalize_url(loc_element.text)
                    urls.add(clean_url)
            
            logger.info(f"Found {len(urls)} URLs in sitemap")
            return urls
        
        except Exception as e:
            logger.error(f"Error fetching sitemap from {sitemap_url}: {e}")
            return set()
    
    def find_orphan_pages(self, sitemap_url=None):
        """Find orphan pages by comparing sitemap with crawled internal links"""
        logger.info("Finding orphan pages...")
        
        # Fetch sitemap URLs
        self.sitemap_urls = self._fetch_sitemap(sitemap_url)
        
        if not self.sitemap_urls:
            logger.warning("No sitemap found or sitemap is empty")
            return []
        
        # Find orphan pages (in sitemap but not internally linked)
        orphan_pages = []
        
        for sitemap_url in self.sitemap_urls:
            is_linked = sitemap_url in self.all_internal_links or sitemap_url in self.crawled_pages
            
            orphan_pages.append({
                'url': sitemap_url,
                'found_in_sitemap': 'Yes',
                'internally_linked': 'Yes' if is_linked else 'No'
            })
        
        # Filter to only orphan pages
        true_orphans = [page for page in orphan_pages if page['internally_linked'] == 'No']
        
        logger.info(f"Found {len(true_orphans)} orphan pages out of {len(self.sitemap_urls)} sitemap URLs")
        return orphan_pages
    
    def save_broken_links_csv(self, filename='broken_links.csv'):
        """Save broken links to CSV file"""
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Source Page URL', 'Broken Link URL', 'Anchor Text / Current Value', 'Link Type', 'Status Code']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for link in self.broken_links:
                writer.writerow({
                    'Source Page URL': link['source_page'],
                    'Broken Link URL': link['broken_url'],
                    'Anchor Text / Current Value': link['anchor_text'],
                    'Link Type': link['link_type'],
                    'Status Code': link['status_code']
                })
        
        logger.info(f"Saved {len(self.broken_links)} broken links to {filename}")
    
    def save_orphan_pages_csv(self, orphan_pages, filename='orphan_pages.csv'):
        """Save orphan pages to CSV file"""
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Orphan Page URL', 'Found in Sitemap?', 'Internally Linked?']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for page in orphan_pages:
                writer.writerow({
                    'Orphan Page URL': page['url'],
                    'Found in Sitemap?': page['found_in_sitemap'],
                    'Internally Linked?': page['internally_linked']
                })
        
        logger.info(f"Saved {len(orphan_pages)} sitemap pages analysis to {filename}")

def main():
    parser = argparse.ArgumentParser(description='Website Crawler for Broken Links and Orphan Pages')
    parser.add_argument('domain', help='Base domain to crawl (e.g., https://example.com)')
    parser.add_argument('--max-depth', type=int, default=3, help='Maximum crawl depth (default: 3)')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between requests in seconds (default: 1.0)')
    parser.add_argument('--max-pages', type=int, default=200, help='Maximum pages to crawl (default: 200)')
    parser.add_argument('--sitemap', help='Custom sitemap URL (optional)')
    parser.add_argument('--ignore-robots', action='store_true', help='Ignore robots.txt restrictions')
    parser.add_argument('--output-dir', default='reports', help='Output directory for CSV files (default: reports)')
    
    args = parser.parse_args()
    
    # Ensure output directory exists
    import os
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Initialize crawler
    crawler = WebsiteCrawler(
        base_domain=args.domain,
        max_depth=args.max_depth,
        delay=args.delay,
        max_pages=args.max_pages,
        respect_robots=not args.ignore_robots
    )
    
    # Perform crawl
    start_time = datetime.now()
    crawler.crawl_website()
    
    # Find orphan pages
    orphan_pages = crawler.find_orphan_pages(args.sitemap)
    
    # Generate timestamp for filenames
    timestamp = start_time.strftime('%Y%m%d_%H%M%S')
    domain_name = urllib.parse.urlparse(args.domain).netloc.replace('.', '_')
    
    # Save results
    broken_links_file = os.path.join(args.output_dir, f'broken_links_{domain_name}_{timestamp}.csv')
    orphan_pages_file = os.path.join(args.output_dir, f'orphan_pages_{domain_name}_{timestamp}.csv')
    
    crawler.save_broken_links_csv(broken_links_file)
    crawler.save_orphan_pages_csv(orphan_pages, orphan_pages_file)
    
    # Print summary
    end_time = datetime.now()
    duration = end_time - start_time
    
    print(f"\n{'='*50}")
    print(f"CRAWL SUMMARY")
    print(f"{'='*50}")
    print(f"Domain: {args.domain}")
    print(f"Pages Crawled: {len(crawler.crawled_pages)}")
    print(f"Broken Links Found: {len(crawler.broken_links)}")
    print(f"Sitemap URLs: {len(crawler.sitemap_urls)}")
    print(f"Orphan Pages: {len([p for p in orphan_pages if p['internally_linked'] == 'No'])}")
    print(f"Crawl Duration: {duration}")
    print(f"\nOutput Files:")
    print(f"- {broken_links_file}")
    print(f"- {orphan_pages_file}")
    print(f"{'='*50}")

if __name__ == '__main__':
    main()
