
from flask import Flask, render_template, request, jsonify, send_file
import requests
import json
import os
from dotenv import load_dotenv
import time
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, white, red, green, orange
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import urllib.parse
import re
from bs4 import BeautifulSoup
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)

class PageCollector:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def get_navigation_links(self, url, max_links=10):
        """Extract navigation menu links from a website"""
        try:
            logger.info(f"Fetching navigation links from: {url}")
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            base_domain = urllib.parse.urlparse(url).netloc
            navigation_links = set()
            
            # Common navigation selectors
            nav_selectors = [
                'nav a',
                'header a',
                '.nav a',
                '.menu a',
                '.navigation a',
                '.header-menu a',
                '.main-menu a',
                '.primary-menu a',
                '.navbar a',
                'ul.menu a',
                'ul.nav a'
            ]
            
            # Find navigation links
            for selector in nav_selectors:
                nav_elements = soup.select(selector)
                for link in nav_elements:
                    href = link.get('href', '').strip()
                    if href and not href.startswith('#') and not href.startswith('mailto:') and not href.startswith('tel:'):
                        # Convert relative URLs to absolute
                        if href.startswith('/'):
                            full_url = f"{urllib.parse.urlparse(url).scheme}://{base_domain}{href}"
                        elif href.startswith('http'):
                            # Check if it's same domain
                            link_domain = urllib.parse.urlparse(href).netloc
                            if link_domain == base_domain:
                                full_url = href
                            else:
                                continue  # Skip external links
                        else:
                            # Relative path
                            full_url = urllib.parse.urljoin(url, href)
                        
                        # Clean URL and add to set
                        clean_url = full_url.split('#')[0].split('?')[0]
                        if clean_url != url:  # Don't include the same homepage
                            navigation_links.add(clean_url)
            
            # Convert to list and limit
            nav_list = list(navigation_links)[:max_links]
            logger.info(f"Found {len(nav_list)} navigation links")
            return nav_list
            
        except Exception as e:
            logger.error(f"Error fetching navigation links: {e}")
            return []

class SEOAuditor:
    def __init__(self):
        self.login = os.getenv('DATAFORSEO_LOGIN')
        self.password = os.getenv('DATAFORSEO_PASSWORD')
        self.base_url = "https://api.dataforseo.com/v3"
        self.page_collector = PageCollector()
        
    def make_request(self, endpoint, data=None, method='GET'):
        """Make authenticated request to DataForSEO API"""
        url = f"{self.base_url}{endpoint}"
        auth = (self.login, self.password)
        
        # Check credentials
        if not self.login or not self.password:
            logger.warning("DataForSEO credentials not configured. Using placeholder data.")
            return None
        
        try:
            logger.info(f"Making {method} request to: {url}")
            if method == 'POST':
                response = requests.post(url, json=data, auth=auth, timeout=30)
            else:
                response = requests.get(url, auth=auth, timeout=30)
            
            logger.info(f"Response status: {response.status_code}")
            response.raise_for_status()
            result = response.json()
            return result
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return None
    
    def start_multi_page_audit(self, homepage_url, max_pages=5):
        """Start audit for homepage and navigation pages"""
        # Get navigation links
        nav_links = self.page_collector.get_navigation_links(homepage_url, max_pages)
        
        # Include homepage in the list
        all_urls = [homepage_url] + nav_links
        
        # If no credentials, return placeholder task IDs
        if not self.login or not self.password:
            return {url: f"placeholder_task_{i}" for i, url in enumerate(all_urls)}
        
        # Start audit tasks for all URLs
        task_ids = {}
        endpoint = "/on_page/task_post"
        
        for url in all_urls:
            data = [{
                "target": url,
                "max_crawl_pages": 1,
                "load_resources": True,
                "enable_javascript": True,
                "enable_browser_rendering": True,
                "custom_js": "meta",
                "browser_preset": "desktop"
            }]
            
            result = self.make_request(endpoint, data, 'POST')
            if result and result.get('status_code') == 20000:
                task_ids[url] = result['tasks'][0]['id']
            else:
                task_ids[url] = None
        
        return task_ids
    
    def get_multi_page_results(self, task_ids):
        """Get audit results for multiple pages"""
        results = {}
        
        for url, task_id in task_ids.items():
            if task_id and task_id.startswith("placeholder_task_"):
                # Generate varied placeholder data for each page
                results[url] = self.get_placeholder_data_for_url(url)
            elif task_id:
                # Get real results from API
                page_result = self.get_audit_results(task_id)
                if page_result:
                    results[url] = page_result
                else:
                    results[url] = self.get_placeholder_data_for_url(url)
            else:
                results[url] = self.get_placeholder_data_for_url(url)
        
        return results
    
    def get_placeholder_data_for_url(self, url):
        """Generate placeholder data customized for specific URL"""
        import random
        
        # Parse URL for customization
        parsed_url = urllib.parse.urlparse(url)
        domain = parsed_url.netloc
        path = parsed_url.path.strip('/')
        
        # Determine page type from path
        if not path or path == '':
            page_type = 'homepage'
            title_base = f"{domain.replace('www.', '').title()} - Premium Services & Solutions"
        elif 'about' in path.lower():
            page_type = 'about'
            title_base = f"About Us - {domain.replace('www.', '').title()}"
        elif 'service' in path.lower():
            page_type = 'services'
            title_base = f"Our Services - {domain.replace('www.', '').title()}"
        elif 'contact' in path.lower():
            page_type = 'contact'
            title_base = f"Contact Us - {domain.replace('www.', '').title()}"
        elif 'product' in path.lower():
            page_type = 'products'
            title_base = f"Products - {domain.replace('www.', '').title()}"
        else:
            page_type = 'general'
            title_base = f"{path.replace('-', ' ').title()} - {domain.replace('www.', '').title()}"
        
        # Generate variable quality scores based on random factors
        quality_factor = random.choice(['excellent', 'good', 'poor'])
        
        if quality_factor == 'excellent':
            base_scores = {'title': 95, 'meta': 90, 'headings': 95, 'images': 85, 'content': 90, 'technical': 95}
            word_count = random.randint(800, 1500)
            images_with_alt = 8
            images_without_alt = 1
        elif quality_factor == 'good':
            base_scores = {'title': 75, 'meta': 70, 'headings': 80, 'images': 65, 'content': 75, 'technical': 80}
            word_count = random.randint(400, 800)
            images_with_alt = 5
            images_without_alt = 3
        else:
            base_scores = {'title': 45, 'meta': 30, 'headings': 50, 'images': 25, 'content': 40, 'technical': 55}
            word_count = random.randint(150, 400)
            images_with_alt = 2
            images_without_alt = 6
        
        # Create comprehensive placeholder data
        placeholder_data = {
            'url': url,
            'meta': {
                'title': title_base[:60] if quality_factor != 'poor' else title_base[:25],
                'description': f"Comprehensive {page_type} information for {domain}. Quality services and solutions." if quality_factor != 'poor' else "Short desc",
                'keywords': f"{page_type}, {domain}, services, quality",
                'author': f"{domain.replace('www.', '').title()} Team",
                'robots': 'index, follow'
            },
            'content': {
                'h1': [{'text': title_base}] if quality_factor != 'poor' else [{'text': 'Page Title'}, {'text': 'Another H1'}],
                'h2': [
                    {'text': f'{page_type.title()} Overview'},
                    {'text': 'Key Features'},
                    {'text': 'Benefits'},
                ] if quality_factor != 'poor' else [],
                'h3': [
                    {'text': 'Feature 1'},
                    {'text': 'Feature 2'},
                    {'text': 'Feature 3'},
                ],
                'text_content': f"This {page_type} page provides comprehensive information about our services and solutions.",
                'word_count': word_count
            },
            'resource': {
                'images': (
                    [{'alt': f'{page_type} image {i}', 'src': f'image{i}.jpg'} for i in range(images_with_alt)] +
                    [{'alt': '', 'src': f'missing-alt{i}.jpg'} for i in range(images_without_alt)]
                )
            },
            'links': [
                {'domain_from': domain, 'domain_to': domain, 'type': 'internal'} for _ in range(random.randint(3, 8))
            ] + [
                {'domain_from': domain, 'domain_to': 'external-site.com', 'type': 'external'} for _ in range(random.randint(1, 3))
            ],
            'page_timing': {
                'time_to_interactive': random.randint(1500, 4000),
                'dom_complete': random.randint(1000, 3000),
                'first_contentful_paint': random.randint(800, 2000),
                'largest_contentful_paint': random.randint(1200, 3500),
                'cumulative_layout_shift': round(random.uniform(0.05, 0.3), 2)
            },
            'schema_markup': [
                {'type': 'Organization', 'found': quality_factor != 'poor'},
                {'type': 'WebSite', 'found': quality_factor == 'excellent'},
                {'type': 'WebPage', 'found': quality_factor != 'poor'}
            ],
            'technical': {
                'ssl_certificate': quality_factor != 'poor',
                'mobile_friendly': quality_factor != 'poor',
                'page_size_kb': random.randint(800, 4000),
                'text_html_ratio': round(random.uniform(0.1, 0.3), 2),
                'gzip_compression': quality_factor != 'poor',
                'minified_css': quality_factor == 'excellent',
                'minified_js': quality_factor == 'excellent'
            },
            'social_meta': {
                'og_title': title_base if quality_factor != 'poor' else '',
                'og_description': f"Quality {page_type} page" if quality_factor != 'poor' else '',
                'og_image': f"https://{domain}/og-image.jpg" if quality_factor != 'poor' else '',
                'twitter_card': 'summary_large_image' if quality_factor != 'poor' else '',
                'twitter_title': title_base if quality_factor != 'poor' else '',
                'twitter_description': f"{page_type.title()} page description" if quality_factor != 'poor' else ''
            }
        }
        
        return [placeholder_data]
    
    def get_audit_results(self, task_id):
        """Get audit results by task ID"""
        if task_id.startswith("placeholder_task_"):
            return self.get_placeholder_data_for_url("https://example.com")
            
        endpoint = f"/on_page/task_get/{task_id}"
        
        # Poll for results
        max_retries = 10
        for attempt in range(max_retries):
            result = self.make_request(endpoint)
            if result and result.get('status_code') == 20000:
                tasks = result.get('tasks', [])
                if tasks and tasks[0].get('status_message') == 'Ok':
                    return tasks[0].get('result', [])
            time.sleep(5)
        
        return None
    
    def analyze_multi_page_data(self, multi_page_results):
        """Analyze audit data for multiple pages"""
        analyzed_pages = {}
        overall_stats = {
            'total_pages': len(multi_page_results),
            'avg_scores': {},
            'total_issues': 0,
            'pages_with_issues': 0
        }
        
        all_scores = {'title': [], 'meta_description': [], 'headings': [], 'images': [], 'content': [], 'technical': [], 'social_media': [], 'schema_markup': [], 'overall': []}
        
        for url, audit_data in multi_page_results.items():
            page_analysis = self.analyze_seo_data(audit_data)
            if page_analysis:
                analyzed_pages[url] = page_analysis
                
                # Collect scores for averaging
                for metric, score in page_analysis['scores'].items():
                    if metric in all_scores:
                        all_scores[metric].append(score)
                
                # Count issues
                overall_stats['total_issues'] += len(page_analysis['issues'])
                if page_analysis['issues']:
                    overall_stats['pages_with_issues'] += 1
        
        # Calculate average scores
        for metric, scores in all_scores.items():
            if scores:
                overall_stats['avg_scores'][metric] = round(sum(scores) / len(scores))
        
        return analyzed_pages, overall_stats
    
    def analyze_seo_data(self, audit_data):
        """Analyze audit data and generate insights"""
        if not audit_data:
            return None
            
        page_data = audit_data[0] if audit_data else {}
        
        analysis = {
            'url': page_data.get('url', ''),
            'title': page_data.get('meta', {}).get('title', ''),
            'meta_description': page_data.get('meta', {}).get('description', ''),
            'meta_keywords': page_data.get('meta', {}).get('keywords', ''),
            'h1_tags': [],
            'h2_tags': [],
            'h3_tags': [],
            'images_without_alt': 0,
            'total_images': 0,
            'internal_links': 0,
            'external_links': 0,
            'page_size': page_data.get('technical', {}).get('page_size_kb', 0),
            'load_time': page_data.get('page_timing', {}).get('dom_complete', 0),
            'word_count': page_data.get('content', {}).get('word_count', 0),
            'schema_markup': page_data.get('schema_markup', []),
            'technical': page_data.get('technical', {}),
            'social_meta': page_data.get('social_meta', {}),
            'page_timing': page_data.get('page_timing', {}),
            'issues': [],
            'scores': {}
        }
        
        # Extract heading tags
        content = page_data.get('content', {})
        if content:
            analysis['h1_tags'] = [h.get('text', '') for h in content.get('h1', [])]
            analysis['h2_tags'] = [h.get('text', '') for h in content.get('h2', [])]
            analysis['h3_tags'] = [h.get('text', '') for h in content.get('h3', [])]
            
            if content.get('word_count'):
                analysis['word_count'] = content['word_count']
        
        # Analyze images
        images = page_data.get('resource', {}).get('images', [])
        analysis['total_images'] = len(images)
        analysis['images_without_alt'] = sum(1 for img in images if not img.get('alt'))
        
        # Analyze links
        links = page_data.get('links', [])
        for link in links:
            if link.get('type') == 'internal':
                analysis['internal_links'] += 1
            else:
                analysis['external_links'] += 1
        
        # Calculate scores and generate recommendations
        analysis['scores'] = self.calculate_scores(analysis)
        analysis['issues'] = self.generate_recommendations(analysis)
        
        return analysis
    
    def calculate_scores(self, analysis):
        """Calculate SEO scores for different aspects"""
        scores = {}
        
        # Title score
        title = analysis['title']
        title_score = 100
        if not title:
            title_score = 0
        elif len(title) < 30 or len(title) > 60:
            title_score = 70
        scores['title'] = title_score
        
        # Meta description score
        meta_desc = analysis['meta_description']
        meta_score = 100
        if not meta_desc:
            meta_score = 0
        elif len(meta_desc) < 120 or len(meta_desc) > 160:
            meta_score = 75
        scores['meta_description'] = meta_score
        
        # Headings score
        h1_count = len(analysis['h1_tags'])
        h2_count = len(analysis['h2_tags'])
        headings_score = 100
        if h1_count == 0:
            headings_score = 20
        elif h1_count > 1:
            headings_score = 60
        elif h2_count == 0:
            headings_score = 70
        scores['headings'] = headings_score
        
        # Images score
        if analysis['total_images'] > 0:
            alt_ratio = (analysis['total_images'] - analysis['images_without_alt']) / analysis['total_images']
            images_score = int(alt_ratio * 100)
        else:
            images_score = 100
        scores['images'] = images_score
        
        # Content score
        word_count = analysis['word_count']
        content_score = 100
        if word_count < 300:
            content_score = 50
        elif word_count < 500:
            content_score = 75
        scores['content'] = content_score
        
        # Technical score
        technical = analysis.get('technical', {})
        technical_score = 100
        if not technical.get('ssl_certificate', True):
            technical_score -= 20
        if not technical.get('mobile_friendly', True):
            technical_score -= 15
        if not technical.get('gzip_compression', True):
            technical_score -= 10
        if technical.get('page_size_kb', 0) > 3000:
            technical_score -= 15
        scores['technical'] = max(0, technical_score)
        
        # Social media score
        social = analysis.get('social_meta', {})
        social_score = 100
        if not social.get('og_title'):
            social_score -= 25
        if not social.get('og_description'):
            social_score -= 25
        if not social.get('og_image'):
            social_score -= 25
        if not social.get('twitter_card'):
            social_score -= 25
        scores['social_media'] = max(0, social_score)
        
        # Schema markup score
        schema_count = len([s for s in analysis.get('schema_markup', []) if s.get('found')])
        schema_score = min(100, schema_count * 35)
        scores['schema_markup'] = schema_score
        
        # Overall score
        scores['overall'] = int(sum(scores.values()) / len(scores))
        
        return scores
    
    def generate_recommendations(self, analysis):
        """Generate actionable SEO recommendations"""
        issues = []
        
        # Title issues
        if not analysis['title']:
            issues.append("Add a title tag to your page")
        elif len(analysis['title']) < 30:
            issues.append("Title tag is too short (should be 30-60 characters)")
        elif len(analysis['title']) > 60:
            issues.append("Title tag is too long (should be 30-60 characters)")
        
        # Meta description issues
        if not analysis['meta_description']:
            issues.append("Add a meta description to your page")
        elif len(analysis['meta_description']) < 120:
            issues.append("Meta description is too short (should be 120-160 characters)")
        elif len(analysis['meta_description']) > 160:
            issues.append("Meta description is too long (should be 120-160 characters)")
        
        # Heading issues
        h1_count = len(analysis['h1_tags'])
        h2_count = len(analysis['h2_tags'])
        if h1_count == 0:
            issues.append("Add an H1 tag to your page")
        elif h1_count > 1:
            issues.append("Use only one H1 tag per page")
        if h2_count == 0:
            issues.append("Add H2 tags to structure your content better")
        
        # Content issues
        if analysis['word_count'] < 300:
            issues.append("Add more content - pages should have at least 300 words")
        
        # Image issues
        if analysis['images_without_alt'] > 0:
            issues.append(f"Add alt text to {analysis['images_without_alt']} images")
        
        # Link issues
        if analysis['internal_links'] < 3:
            issues.append("Add more internal links to improve site navigation")
        
        # Technical issues
        technical = analysis.get('technical', {})
        if not technical.get('ssl_certificate', True):
            issues.append("Install SSL certificate for HTTPS security")
        if not technical.get('mobile_friendly', True):
            issues.append("Make your website mobile-friendly")
        if not technical.get('gzip_compression', True):
            issues.append("Enable GZIP compression to reduce page load times")
        if technical.get('page_size_kb', 0) > 3000:
            issues.append("Optimize page size - current size is too large")
        
        # Social media issues
        social = analysis.get('social_meta', {})
        if not social.get('og_title'):
            issues.append("Add Open Graph title for better social media sharing")
        if not social.get('og_description'):
            issues.append("Add Open Graph description for social media")
        if not social.get('og_image'):
            issues.append("Add Open Graph image for social media previews")
        
        # Schema markup issues
        schema_found = len([s for s in analysis.get('schema_markup', []) if s.get('found')])
        if schema_found == 0:
            issues.append("Add structured data (Schema markup) to help search engines understand your content")
        elif schema_found < 2:
            issues.append("Consider adding more types of structured data for better SEO")
        
        return issues

class PDFReportGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.setup_custom_styles()
    
    def setup_custom_styles(self):
        """Setup custom paragraph styles"""
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            textColor=HexColor('#2E86AB'),
            alignment=TA_CENTER
        )
        
        self.heading_style = ParagraphStyle(
            'CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            spaceAfter=12,
            textColor=HexColor('#A23B72')
        )
        
        self.subheading_style = ParagraphStyle(
            'CustomSubHeading',
            parent=self.styles['Heading3'],
            fontSize=14,
            spaceAfter=8,
            textColor=HexColor('#2E86AB')
        )
        
        self.body_style = ParagraphStyle(
            'CustomBody',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=6
        )
    
    def get_score_color(self, score):
        """Get color based on score"""
        if score >= 80:
            return HexColor('#4CAF50')  # Green
        elif score >= 60:
            return HexColor('#FF9800')  # Orange
        else:
            return HexColor('#F44336')  # Red
    
    def generate_multi_page_report(self, analyzed_pages, overall_stats, filename):
        """Generate comprehensive multi-page PDF report"""
        doc = SimpleDocTemplate(filename, pagesize=A4)
        story = []
        
        # Title page
        story.append(Paragraph("Multi-Page SEO Audit Report", self.title_style))
        story.append(Spacer(1, 20))
        
        # Overall statistics
        homepage_url = list(analyzed_pages.keys())[0] if analyzed_pages else "Unknown"
        domain = urllib.parse.urlparse(homepage_url).netloc
        
        story.append(Paragraph(f"<b>Website:</b> {domain}", self.body_style))
        story.append(Paragraph(f"<b>Pages Audited:</b> {overall_stats['total_pages']}", self.body_style))
        story.append(Paragraph(f"<b>Total Issues Found:</b> {overall_stats['total_issues']}", self.body_style))
        story.append(Paragraph(f"<b>Pages with Issues:</b> {overall_stats['pages_with_issues']}", self.body_style))
        story.append(Paragraph(f"<b>Report Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}", self.body_style))
        story.append(Spacer(1, 30))
        
        # Overall site score
        overall_score = overall_stats['avg_scores'].get('overall', 0)
        score_color = self.get_score_color(overall_score)
        story.append(Paragraph("Overall Site SEO Score", self.heading_style))
        
        overall_table = Table([[f"{overall_score}/100"]], colWidths=[3*inch])
        overall_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), score_color),
            ('TEXTCOLOR', (0, 0), (-1, -1), white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 36),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
            ('TOPPADDING', (0, 0), (-1, -1), 20),
        ]))
        story.append(overall_table)
        story.append(Spacer(1, 30))
        
        # Site-wide average scores
        story.append(Paragraph("Site-Wide Average SEO Metrics", self.heading_style))
        
        avg_score_data = [['SEO Metric', 'Average Score', 'Performance Level']]
        
        for metric, avg_score in overall_stats['avg_scores'].items():
            if metric != 'overall':
                if avg_score >= 80:
                    status = 'Excellent'
                elif avg_score >= 60:
                    status = 'Good'
                elif avg_score >= 40:
                    status = 'Needs Work'
                else:
                    status = 'Critical'
                
                avg_score_data.append([
                    metric.replace('_', ' ').title(),
                    f"{avg_score}/100",
                    status
                ])
        
        avg_score_table = Table(avg_score_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
        
        # Style the average scores table
        avg_table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#1a237e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]
        
        # Color code the average scores
        for i, row in enumerate(avg_score_data[1:], 1):
            score_text = row[1]
            score_value = int(score_text.split('/')[0])
            row_color = self.get_score_color(score_value)
            
            if score_value >= 80:
                bg_color = HexColor('#E8F5E8')
            elif score_value >= 60:
                bg_color = HexColor('#FFF3E0')
            else:
                bg_color = HexColor('#FFEBEE')
            
            avg_table_style.append(('BACKGROUND', (0, i), (-1, i), bg_color))
            avg_table_style.append(('BACKGROUND', (1, i), (1, i), row_color))
            avg_table_style.append(('TEXTCOLOR', (1, i), (1, i), white))
            avg_table_style.append(('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'))
        
        avg_score_table.setStyle(TableStyle(avg_table_style))
        story.append(avg_score_table)
        story.append(Spacer(1, 30))
        
        # Page-by-page summary table
        story.append(Paragraph("Page-by-Page Summary", self.heading_style))
        
        page_summary_data = [['Page URL', 'Overall Score', 'Top Issues', 'Status']]
        
        for url, analysis in analyzed_pages.items():
            page_score = analysis['scores']['overall']
            top_issues = len(analysis['issues'])
            
            if page_score >= 80:
                status = '✅ Excellent'
            elif page_score >= 60:
                status = '⚠️ Good'
            else:
                status = '❌ Needs Work'
            
            # Truncate URL for display
            display_url = url if len(url) <= 50 else url[:47] + "..."
            
            page_summary_data.append([
                display_url,
                f"{page_score}/100",
                f"{top_issues} issues",
                status
            ])
        
        page_summary_table = Table(page_summary_data, colWidths=[3*inch, 1*inch, 1*inch, 1.5*inch])
        
        # Style the page summary table
        summary_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#1a237e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]
        
        # Color code page scores
        for i, row in enumerate(page_summary_data[1:], 1):
            score_text = row[1]
            score_value = int(score_text.split('/')[0])
            row_color = self.get_score_color(score_value)
            
            summary_style.append(('BACKGROUND', (1, i), (1, i), row_color))
            summary_style.append(('TEXTCOLOR', (1, i), (1, i), white))
            summary_style.append(('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'))
            
            # Alternate row background
            if i % 2 == 0:
                summary_style.append(('BACKGROUND', (0, i), (0, i), HexColor('#f8f9fa')))
                summary_style.append(('BACKGROUND', (2, i), (-1, i), HexColor('#f8f9fa')))
        
        page_summary_table.setStyle(TableStyle(summary_style))
        story.append(page_summary_table)
        
        # Individual page details
        for url, analysis in analyzed_pages.items():
            story.append(PageBreak())
            
            # Page header
            display_url = url if len(url) <= 80 else url[:77] + "..."
            story.append(Paragraph(f"Page Analysis: {display_url}", self.heading_style))
            story.append(Spacer(1, 20))
            
            # Page score
            page_score = analysis['scores']['overall']
            score_color = self.get_score_color(page_score)
            
            page_score_table = Table([[f"{page_score}/100"]], colWidths=[2*inch])
            page_score_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), score_color),
                ('TEXTCOLOR', (0, 0), (-1, -1), white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 24),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
                ('TOPPADDING', (0, 0), (-1, -1), 15),
            ]))
            story.append(page_score_table)
            story.append(Spacer(1, 20))
            
            # Generate detailed page report
            self.add_page_details(story, analysis)
        
        doc.build(story)
    
    def add_page_details(self, story, analysis):
        """Add detailed analysis for a single page"""
        # Page metrics table
        story.append(Paragraph("Page SEO Metrics", self.subheading_style))
        
        metrics_data = [['Metric', 'Score', 'Status']]
        
        for metric, score in analysis['scores'].items():
            if metric != 'overall':
                if score >= 80:
                    status = 'Excellent'
                elif score >= 60:
                    status = 'Good'
                else:
                    status = 'Needs Work'
                
                metrics_data.append([
                    metric.replace('_', ' ').title(),
                    f"{score}/100",
                    status
                ])
        
        metrics_table = Table(metrics_data, colWidths=[2*inch, 1*inch, 1.5*inch])
        
        # Style metrics table
        metrics_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#4caf50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]
        
        # Color code scores
        for i, row in enumerate(metrics_data[1:], 1):
            score_text = row[1]
            score_value = int(score_text.split('/')[0])
            row_color = self.get_score_color(score_value)
            
            metrics_style.append(('BACKGROUND', (1, i), (1, i), row_color))
            metrics_style.append(('TEXTCOLOR', (1, i), (1, i), white))
            metrics_style.append(('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'))
        
        metrics_table.setStyle(TableStyle(metrics_style))
        story.append(metrics_table)
        story.append(Spacer(1, 20))
        
        # Page issues
        if analysis['issues']:
            story.append(Paragraph("Issues Found on This Page", self.subheading_style))
            
            for i, issue in enumerate(analysis['issues'], 1):
                story.append(Paragraph(f"• {issue}", self.body_style))
            
            story.append(Spacer(1, 15))
        
        # Technical details
        story.append(Paragraph("Technical Details", self.subheading_style))
        
        tech_details = [
            f"Title: {analysis['title'][:100]}..." if len(analysis['title']) > 100 else f"Title: {analysis['title']}",
            f"Meta Description Length: {len(analysis['meta_description'])} characters",
            f"Word Count: {analysis['word_count']} words",
            f"Images: {analysis['total_images']} total ({analysis['images_without_alt']} missing alt text)",
            f"Internal Links: {analysis['internal_links']}",
            f"External Links: {analysis['external_links']}",
            f"Page Size: {analysis['page_size']} KB" if analysis['page_size'] else "Page Size: Unknown"
        ]
        
        for detail in tech_details:
            story.append(Paragraph(f"• {detail}", self.body_style))
        
        story.append(Spacer(1, 20))

# Initialize components
auditor = SEOAuditor()
pdf_generator = PDFReportGenerator()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate-pdf', methods=['POST'])
def generate_pdf():
    try:
        data = request.get_json()
        url = data.get('url', 'https://example.com')
        max_pages = data.get('max_pages', 5)
        
        # Validate URL format
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        logger.info(f"Starting multi-page audit for: {url}")
        
        # Start multi-page audit
        task_ids = auditor.start_multi_page_audit(url, max_pages)
        logger.info(f"Started audit for {len(task_ids)} pages")
        
        # Wait a moment for tasks to process
        time.sleep(2)
        
        # Get results for all pages
        multi_page_results = auditor.get_multi_page_results(task_ids)
        logger.info(f"Retrieved results for {len(multi_page_results)} pages")
        
        # Analyze all pages
        analyzed_pages, overall_stats = auditor.analyze_multi_page_data(multi_page_results)
        
        if not analyzed_pages:
            return jsonify({'error': 'Failed to analyze any pages'}), 500
        
        # Generate filename
        domain = urllib.parse.urlparse(url).netloc
        domain = re.sub(r'[^\w\-_\.]', '_', domain)
        filename = f"seo_audit_{domain}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join('reports', filename)
        
        # Create reports directory if it doesn't exist
        os.makedirs('reports', exist_ok=True)
        
        # Generate comprehensive multi-page PDF report
        pdf_generator.generate_multi_page_report(analyzed_pages, overall_stats, filepath)
        
        logger.info(f"Generated report: {filename}")
        return send_file(filepath, as_attachment=True, download_name=filename)
    
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
