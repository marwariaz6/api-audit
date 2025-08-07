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
import csv

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
            base_scores = {'title': 95, 'meta': 90, 'headings': 95, 'images': 75, 'content': 90, 'technical': 95}
            word_count = random.randint(800, 1500)
            images_with_alt = 8
            images_without_alt = 5  # Increased to test additional images section
        elif quality_factor == 'good':
            base_scores = {'title': 75, 'meta': 70, 'headings': 80, 'images': 60, 'content': 75, 'technical': 80}
            word_count = random.randint(400, 800)
            images_with_alt = 5
            images_without_alt = 6  # Increased to test additional images section
        else:
            base_scores = {'title': 45, 'meta': 30, 'headings': 50, 'images': 20, 'content': 40, 'technical': 55}
            word_count = random.randint(150, 400)
            images_with_alt = 2
            images_without_alt = 8  # Increased to test additional images section

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
                    [{'alt': f'{page_type} image {i}', 'src': f'/images/{page_type}/hero-image-{i}.jpg'} for i in range(images_with_alt)] +
                    [{'alt': '', 'src': f'/wp-content/uploads/2024/gallery/missing-alt-image-{i}.jpg'} for i in range(min(3, images_without_alt))] +
                    [{'alt': '', 'src': f'/assets/images/products/product-showcase-{i}.png'} for i in range(3, min(6, images_without_alt))] +
                    [{'alt': '', 'src': f'/media/banners/promotional-banner-{i}-very-long-filename.jpg'} for i in range(6, images_without_alt)]
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

        all_scores = {'title': [], 'meta_description': [], 'headings': [], 'images': [], 'content': [], 'technical': [], 'overall': []}

        for url, audit_data in multi_page_results.items():
            try:
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
            except Exception as e:
                logger.error(f"Error analyzing data for {url}: {e}")
                continue

        # Calculate average scores
        for metric, scores in all_scores.items():
            if scores:
                overall_stats['avg_scores'][metric] = round(sum(scores) / len(scores))

        return analyzed_pages, overall_stats

    def analyze_seo_data(self, audit_data):
        """Analyze audit data and generate insights"""
        if not audit_data or len(audit_data) == 0:
            return None

        page_data = audit_data[0] if isinstance(audit_data, list) and len(audit_data) > 0 else audit_data

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
            'scores': {},
            'missing_alt_images': [] # Add this to store missing image URLs
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
        for img in images:
            if not img.get('alt'):
                analysis['images_without_alt'] += 1
                analysis['missing_alt_images'].append(img.get('src', '')) # Store missing image URL

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

        # Add internal links as a separate metric score
        if analysis['internal_links'] < 3:
            internal_link_score = 40
        elif analysis['internal_links'] < 8:
            internal_link_score = 70
        else:
            internal_link_score = 95

        analysis['scores']['internal_links'] = internal_link_score

        return analysis

    def calculate_scores(self, analysis):
        """Calculate SEO scores for different aspects"""
        try:
            scores = {}

            # Title score
            title = analysis.get('title', '')
            title_score = 100
            if not title:
                title_score = 0
            elif len(title) < 30 or len(title) > 60:
                title_score = 70
            scores['title'] = title_score

            # Meta description score
            meta_desc = analysis.get('meta_description', '')
            meta_score = 100
            if not meta_desc:
                meta_score = 0
            elif len(meta_desc) < 120 or len(meta_desc) > 160:
                meta_score = 75
            scores['meta_description'] = meta_score

            # Headings score
            h1_tags = analysis.get('h1_tags', [])
            h2_tags = analysis.get('h2_tags', [])
            h1_count = len(h1_tags) if isinstance(h1_tags, list) else 0
            h2_count = len(h2_tags) if isinstance(h2_tags, list) else 0

            headings_score = 100
            if h1_count == 0:
                headings_score = 20
            elif h1_count > 1:
                headings_score = 60
            elif h2_count == 0:
                headings_score = 70
            scores['headings'] = headings_score

            # Images score
            total_images = analysis.get('total_images', 0)
            images_without_alt = analysis.get('images_without_alt', 0)

            if total_images > 0:
                alt_ratio = (total_images - images_without_alt) / total_images
                images_score = int(alt_ratio * 100)
            else:
                images_score = 100
            scores['images'] = images_score

            # Content score
            word_count = analysis.get('word_count', 0)
            content_score = 100
            if word_count < 300:
                content_score = 50
            elif word_count < 500:
                content_score = 75
            scores['content'] = content_score

            # Technical score (placeholder)
            scores['technical'] = 85

            # Overall score
            if scores:
                scores['overall'] = int(sum(scores.values()) / len(scores))
            else:
                scores['overall'] = 0

            return scores

        except Exception as e:
            logger.error(f"Error calculating scores: {e}")
            return {'title': 0, 'meta_description': 0, 'headings': 0, 'images': 0, 'content': 0, 'technical': 0, 'overall': 0}

    def generate_recommendations(self, analysis):
        """Generate actionable SEO recommendations"""
        issues = []

        # Title issues
        if not analysis.get('title'):
            issues.append("Add a title tag to your page")
        elif len(analysis.get('title', '')) < 30:
            issues.append("Title tag is too short (should be 30-60 characters)")
        elif len(analysis.get('title', '')) > 60:
            issues.append("Title tag is too long (should be 30-60 characters)")

        # Meta description issues
        if not analysis.get('meta_description'):
            issues.append("Add a meta description to your page")
        elif len(analysis.get('meta_description', '')) < 120:
            issues.append("Meta description is too short (should be 120-160 characters)")
        elif len(analysis.get('meta_description', '')) > 160:
            issues.append("Meta description is too long (should be 120-160 characters)")

        # Heading issues
        h1_count = len(analysis.get('h1_tags', []))
        h2_count = len(analysis.get('h2_tags', []))
        if h1_count == 0:
            issues.append("Add an H1 tag to your page")
        elif h1_count > 1:
            issues.append("Use only one H1 tag per page")
        if h2_count == 0:
            issues.append("Add H2 tags to structure your content better")

        # Content issues
        if analysis.get('word_count', 0) < 300:
            issues.append("Add more content - pages should have at least 300 words")

        # Image issues
        if analysis.get('images_without_alt', 0) > 0:
            issues.append(f"Add alt text to {analysis['images_without_alt']} images")

        # Link issues
        if analysis.get('internal_links', 0) < 3:
            issues.append("Add more internal links to improve site navigation")

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
        """Generate comprehensive metric-by-metric PDF report"""
        try:
            doc = SimpleDocTemplate(filename, pagesize=A4)
            story = []

            # Title page
            story.append(Paragraph("Multi-Page SEO Audit Report", self.title_style))
            story.append(Spacer(1, 20))
        except Exception as e:
            logger.error(f"Error initializing PDF report: {e}")
            return None

        # Overall statistics
        if not analyzed_pages:
            return None

        homepage_url = list(analyzed_pages.keys())[0]
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

        # Overall Page Scores Summary
        story.append(Paragraph("🔹 Overall Page Scores", self.heading_style))
        overall_page_data = [['Page URL', 'Overall Score']]

        for url, analysis in analyzed_pages.items():
            # Create clickable URL
            clickable_url = self.create_clickable_url(url)
            page_score = analysis['scores']['overall']
            overall_page_data.append([clickable_url, f"{page_score}/100"])

        overall_page_table = self.create_metric_table(overall_page_data, 'overall')
        story.append(overall_page_table)
        story.append(Spacer(1, 30))

        # Metric-by-metric analysis
        self.add_metric_analysis(story, analyzed_pages, "🔹 Title Tag Optimization", "title")
        self.add_metric_analysis(story, analyzed_pages, "🔹 Meta Description", "meta_description")
        self.add_metric_analysis(story, analyzed_pages, "🔹 Heading Structure", "headings")
        self.add_metric_analysis(story, analyzed_pages, "🔹 Image Optimization", "images")
        self.add_metric_analysis(story, analyzed_pages, "🔹 Content Quality", "content")
        self.add_metric_analysis(story, analyzed_pages, "🔹 Internal Linking", "internal_links")

        # Add comprehensive missing images page at the end
        self.add_missing_images_page(story, analyzed_pages)

        # Add Technical SEO Audit introduction page
        self.add_technical_seo_intro_page(story)

        # Add backlink audit pages
        try:
            self.add_backlink_title_page(story)
            self.add_backlink_summary_page(story)
            # Get server URL from request context if available
            server_url = ""
            try:
                from flask import request
                if request:
                    server_url = request.url_root.rstrip('/')
            except:
                pass
            self.add_referring_domains_page(story, homepage_url, server_url)
        except Exception as e:
            logger.error(f"Error adding backlink pages: {e}")
            # Add fallback message
            story.append(Paragraph("Backlink audit data temporarily unavailable", self.body_style))

        try:
            doc.build(story)
        except Exception as e:
            logger.error(f"Error building PDF document: {e}")
            return None

    def create_clickable_url(self, url, max_width=2.0):
        """Create a clickable URL paragraph with proper wrapping"""
        # Create a custom style for URLs with smaller font and wrapping
        url_style = ParagraphStyle(
            'ClickableURL',
            parent=self.body_style,
            fontSize=8,
            leading=10,
            wordWrap='LTR',
            allowWidows=1,
            allowOrphans=1,
            spaceAfter=2,
            spaceBefore=2
        )

        # Create clickable link with proper HTML formatting
        clickable_url = f'<link href="{url}" color="blue">{url}</link>'
        return Paragraph(clickable_url, url_style)

    def get_metric_issue(self, analysis, metric):
        """Get specific issue description for a metric"""
        issues_map = {
            'title': self.get_title_issues(analysis),
            'meta_description': self.get_meta_issues(analysis),
            'headings': self.get_heading_issues(analysis),
            'images': self.get_image_issues(analysis),
            'content': self.get_content_issues(analysis),
            'internal_links': self.get_internal_link_issues(analysis)
        }

        return issues_map.get(metric, "No specific issues")

    def get_title_issues(self, analysis):
        """Get title-specific issues"""
        title = analysis.get('title', '')
        if not title:
            return "Missing title tag"
        elif len(title) < 30:
            return "Too short (< 30 chars)"
        elif len(title) > 60:
            return "Too long (> 60 chars)"
        else:
            return "Optimized"

    def get_meta_issues(self, analysis):
        """Get meta description issues"""
        meta_desc = analysis.get('meta_description', '')
        if not meta_desc:
            return "Missing meta description"
        elif len(meta_desc) < 120:
            return "Too short (< 120 chars)"
        elif len(meta_desc) > 160:
            return "Too long (> 160 chars)"
        else:
            return "Optimized"

    def get_heading_issues(self, analysis):
        """Get heading structure issues"""
        h1_count = len(analysis.get('h1_tags', []))
        h2_count = len(analysis.get('h2_tags', []))

        if h1_count == 0:
            return "Missing H1 tag"
        elif h1_count > 1:
            return "Multiple H1 tags"
        elif h2_count == 0:
            return "No H2 tags for structure"
        else:
            return "Well structured"

    def get_image_issues(self, analysis):
        """Get image optimization issues"""
        total_images = analysis.get('total_images', 0)
        missing_alt = analysis.get('images_without_alt', 0)

        if total_images == 0:
            return "No images found"
        elif missing_alt > 0:
            return f"{missing_alt} missing alt text"
        else:
            return "All images optimized"

    def get_content_issues(self, analysis):
        """Get content quality issues"""
        word_count = analysis.get('word_count', 0)
        if word_count < 300:
            return f"Low content ({word_count} words)"
        elif word_count < 500:
            return "Good content length"
        else:
            return "Comprehensive content"

    def get_internal_link_issues(self, analysis):
        """Get internal linking issues"""
        internal_links = analysis.get('internal_links', 0)
        if internal_links < 3:
            return f"Few internal links ({internal_links})"
        elif internal_links < 10:
            return "Good internal linking"
        else:
            return "Excellent internal linking"

    def get_metric_issues_table_data(self, analyzed_pages, metric):
        """Get detailed issues table data with current values and visual indicators"""
        table_data = []

        # Define table headers based on metric
        headers = {
            'title': ['Page URL', 'Issue', 'Current Title Tag', 'Status'],
            'meta_description': ['Page URL', 'Issue', 'Current Meta Description', 'Status'],
            'headings': ['Page URL', 'Issue', 'Current Structure', 'Status'],
            'images': ['Page URL', 'Issue', 'Image Details', 'Status'],
            'content': ['Page URL', 'Issue', 'Content Stats', 'Status'],
            'internal_links': ['Page URL', 'Issue', 'Link Count', 'Status']
        }

        table_data.append(headers.get(metric, ['Page URL', 'Issue', 'Current Value', 'Status']))

        for url, analysis in analyzed_pages.items():
            clickable_url = self.create_clickable_url(url)
            score = analysis['scores'].get(metric, 0)
            status = "PASS" if score >= 80 else "FAIL"

            if metric == 'title':
                title = analysis.get('title', '')
                if not title:
                    issue = "Missing title tag"
                    current_value = "(No title tag found)"
                elif len(title) < 30:
                    issue = f"Too short ({len(title)} chars)"
                    current_value = title[:50] + "..." if len(title) > 50 else title
                elif len(title) > 60:
                    issue = f"Too long ({len(title)} chars)"
                    current_value = title[:50] + "..." if len(title) > 50 else title
                else:
                    issue = "Optimized"
                    current_value = title[:50] + "..." if len(title) > 50 else title

            elif metric == 'meta_description':
                meta_desc = analysis.get('meta_description', '')
                if not meta_desc:
                    issue = "Missing meta description"
                    current_value = "(No meta description found)"
                elif len(meta_desc) < 120:
                    issue = f"Too short ({len(meta_desc)} chars)"
                    current_value = meta_desc[:60] + "..." if len(meta_desc) > 60 else meta_desc
                elif len(meta_desc) > 160:
                    issue = f"Too long ({len(meta_desc)} chars)"
                    current_value = meta_desc[:60] + "..." if len(meta_desc) > 60 else meta_desc
                else:
                    issue = "Optimized"
                    current_value = meta_desc[:60] + "..." if len(meta_desc) > 60 else meta_desc

            elif metric == 'headings':
                h1_count = len(analysis.get('h1_tags', []))
                h2_count = len(analysis.get('h2_tags', []))
                h3_count = len(analysis.get('h3_tags', []))

                if h1_count == 0:
                    issue = "Missing H1 tag"
                elif h1_count > 1:
                    issue = f"Multiple H1 tags ({h1_count})"
                elif h2_count == 0:
                    issue = "No H2 tags"
                else:
                    issue = "Well structured"

                current_value = f"H1:{h1_count}, H2:{h2_count}, H3:{h3_count}"

            elif metric == 'images':
                total_images = analysis.get('total_images', 0)
                missing_alt = analysis.get('images_without_alt', 0)

                if total_images == 0:
                    issue = "No images found"
                    current_value = "0 images"
                elif missing_alt > 0:
                    issue = f"{missing_alt} missing alt text"
                    current_value = f"{total_images} total, {missing_alt} without alt"
                else:
                    issue = "All images optimized"
                    current_value = f"{total_images} images, all with alt text"

            elif metric == 'content':
                word_count = analysis.get('word_count', 0)
                if word_count < 300:
                    issue = f"Low content ({word_count} words)"
                elif word_count < 500:
                    issue = "Moderate content"
                else:
                    issue = "Comprehensive content"

                current_value = f"{word_count} words"

            elif metric == 'internal_links':
                internal_links = analysis.get('internal_links', 0)
                if internal_links < 3:
                    issue = f"Few internal links"
                elif internal_links < 8:
                    issue = "Good internal linking"
                else:
                    issue = "Excellent internal linking"

                current_value = f"{internal_links} internal links"

            else:
                issue = "Unknown metric"
                current_value = "N/A"

            table_data.append([clickable_url, issue, current_value, status])

        return table_data

    def get_metric_recommendations(self, metric):
        """Get actionable recommendations for a specific metric"""
        recommendations = {
            'title': [
                "Write unique, descriptive titles for each page (30-60 characters)",
                "Include primary keywords naturally in title tags",
                "Place most important keywords at the beginning of titles",
                "Avoid keyword stuffing and maintain readability",
                "Use your brand name consistently across titles"
            ],
            'meta_description': [
                "Write compelling meta descriptions for all pages (120-160 characters)",
                "Include a clear call-to-action in meta descriptions",
                "Use primary and secondary keywords naturally",
                "Make each meta description unique and relevant to page content",
                "Test different descriptions to improve click-through rates"
            ],
            'headings': [
                "Use only one H1 tag per page as the main headline",
                "Structure content with H2 and H3 tags in logical hierarchy",
                "Include target keywords in heading tags naturally",
                "Make headings descriptive and user-friendly",
                "Use headings to break up content and improve readability"
            ],
            'images': [
                "Add descriptive alt text to all images",
                "Use keywords in alt text when relevant and natural",
                "Optimize image file sizes for faster loading",
                "Use descriptive file names for images",
                "Implement proper image compression and WebP format when possible"
            ],
            'content': [
                "Create comprehensive, valuable content (minimum 300 words)",
                "Focus on user intent and provide clear answers",
                "Use target keywords naturally throughout content",
                "Include related keywords and semantic variations",
                "Update content regularly to maintain freshness and relevance"
            ],
            'internal_links': [
                "Add 3-8 relevant internal links per page",
                "Use descriptive anchor text for internal links",
                "Link to relevant pages that provide additional value",
                "Create a logical site structure with clear navigation paths",
                "Use internal linking to distribute page authority throughout your site"
            ],
            'overall': [
                "Focus on improving the lowest-scoring metrics first",
                "Monitor SEO performance regularly with analytics tools",
                "Create a content strategy based on keyword research",
                "Build quality backlinks from relevant, authoritative websites",
                "Keep up with SEO best practices and algorithm updates"
            ]
        }

        return recommendations.get(metric, [])

    def create_metric_table(self, data, metric_type):
        """Create a standardized metric table with proper text wrapping"""
        if not data or len(data) == 0:
            return Table([['No data available']])
            
        # Wrap text in cells and ensure proper column widths
        wrapped_data = []
        for row in data:
            if not isinstance(row, (list, tuple)):
                continue
            wrapped_row = []
            for cell in row:
                # Wrap long text to prevent overflow
                if isinstance(cell, str) and len(cell) > 50:
                    wrapped_cell = Paragraph(cell, self.body_style)
                else:
                    wrapped_cell = cell
                wrapped_row.append(wrapped_cell)
            wrapped_data.append(wrapped_row)

        if metric_type == 'overall':
            table = Table(wrapped_data, colWidths=[4.2*inch, 1.3*inch])
        else:
            table = Table(wrapped_data, colWidths=[2.8*inch, 0.8*inch, 2.9*inch])

        # Basic table style with text wrapping support
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('WORDWRAP', (0, 0), (-1, -1), True)
        ]

        # Color code scores with error handling
        score_column = 1 if metric_type == 'overall' else 1
        for i, row in enumerate(data[1:], 1):
            try:
                if len(row) > score_column:
                    score_text = row[score_column]
                    if isinstance(score_text, str) and '/' in score_text:
                        score_value = int(score_text.split('/')[0])
                        row_color = self.get_score_color(score_value)

                        table_style.append(('BACKGROUND', (score_column, i), (score_column, i), row_color))
                        table_style.append(('TEXTCOLOR', (score_column, i), (score_column, i), white))
                        table_style.append(('FONTNAME', (score_column, i), (score_column, i), 'Helvetica-Bold'))

                # Alternate row background for readability
                if i % 2 == 0:
                    bg_color = HexColor('#f8f9fa')
                    table_style.append(('BACKGROUND', (0, i), (0, i), bg_color))
                    if metric_type != 'overall' and len(row) > 2:
                        table_style.append(('BACKGROUND', (2, i), (2, i), bg_color))
            except (IndexError, ValueError) as e:
                logger.error(f"Error processing table row {i}: {e}")
                continue

        table.setStyle(TableStyle(table_style))
        return table

    def create_issues_table(self, data):
        """Create a detailed issues table with proper text wrapping and column management"""
        # Wrap long text in cells to prevent overflow (URLs are already wrapped as clickable paragraphs)
        wrapped_data = []
        for row in data:
            wrapped_row = []
            for i, cell in enumerate(row):
                if isinstance(cell, str):
                    # Wrap long text content for non-URL columns
                    if i == 1 and len(cell) > 20:  # Issue column
                        wrapped_cell = Paragraph(cell, ParagraphStyle(
                            'WrappedIssue',
                            parent=self.body_style,
                            fontSize=8,
                            wordWrap='LTR'
                        ))
                    elif i == 2 and len(cell) > 40:  # Current value column
                        wrapped_cell = Paragraph(cell, ParagraphStyle(
                            'WrappedValue',
                            parent=self.body_style,
                            fontSize=8,
                            wordWrap='LTR'
                        ))
                    else:
                        wrapped_cell = cell
                else:
                    wrapped_cell = cell
                wrapped_row.append(wrapped_cell)
            wrapped_data.append(wrapped_row)

        # Optimize column widths to fit content better with more space for URLs
        table = Table(wrapped_data, colWidths=[2.2*inch, 1.2*inch, 2.3*inch, 0.8*inch])

        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#A23B72')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('ALIGN', (3, 0), (3, -1), 'CENTER'),  # Status column centered
            ('ALIGN', (0, 0), (2, -1), 'LEFT'),     # Other columns left-aligned
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTSIZE', (3, 1), (3, -1), 9),  # Status text
            ('FONTNAME', (3, 1), (3, -1), 'Helvetica-Bold'),  # Bold status text
            ('WORDWRAP', (0, 0), (-1, -1), True)
        ]

        # Color code status column and alternate row backgrounds with error handling
        for i in range(1, len(data)):
            try:
                row = data[i] if i < len(data) else []
                status_text = row[3] if len(row) > 3 else ""

                # Color code status column
                if status_text == "PASS":
                    table_style.append(('BACKGROUND', (3, i), (3, i), HexColor('#4CAF50')))
                    table_style.append(('TEXTCOLOR', (3, i), (3, i), white))
                elif status_text == "FAIL":
                    table_style.append(('BACKGROUND', (3, i), (3, i), HexColor('#F44336')))
                    table_style.append(('TEXTCOLOR', (3, i), (3, i), white))

                # Alternate row backgrounds for other columns
                if i % 2 == 0 and len(row) > 2:
                    bg_color = HexColor('#f8f9fa')
                    table_style.append(('BACKGROUND', (0, i), (2, i), bg_color))
            except (IndexError, ValueError) as e:
                logger.error(f"Error processing issues table row {i}: {e}")
                continue

        table.setStyle(TableStyle(table_style))
        return table

    def add_metric_analysis(self, story, analyzed_pages, title, metric):
        """Add metric-by-metric analysis section"""
        story.append(Paragraph(title, self.heading_style))

        # Create metric-specific table
        table_data = [['Page URL', 'Score', 'Issue/Status']]

        for url, analysis in analyzed_pages.items():
            clickable_url = self.create_clickable_url(url)
            score = analysis['scores'].get(metric, 0)
            issue = self.get_metric_issue(analysis, metric)

            table_data.append([clickable_url, f"{score}/100", issue])

        metric_table = self.create_metric_table(table_data, metric)
        story.append(metric_table)
        story.append(Spacer(1, 15))

        # Add detailed Issues Found section with current values
        story.append(Paragraph("Issues Found:", self.subheading_style))
        issues_table_data = self.get_metric_issues_table_data(analyzed_pages, metric)

        if len(issues_table_data) > 1:  # More than just headers
            issues_table = self.create_issues_table(issues_table_data)
            story.append(issues_table)
        else:
            story.append(Paragraph("• No issues found for this metric", self.body_style))

        story.append(Spacer(1, 15))

        # Add Actionable Recommendations section
        recommendations = self.get_metric_recommendations(metric)
        story.append(Paragraph("Actionable Recommendations:", self.subheading_style))
        for recommendation in recommendations:
            story.append(Paragraph(f"• {recommendation}", self.body_style))
        story.append(Spacer(1, 20))

    def add_additional_missing_images(self, story, analyzed_pages):
        """Add additional missing image URLs that weren't shown in the main table"""
        has_additional_images = False

        for url, analysis in analyzed_pages.items():
            missing_images = analysis.get('missing_alt_images', [])
            if len(missing_images) > 3:
                has_additional_images = True
                break

        if has_additional_images:
            story.append(Paragraph("Additional Missing Alt Text Images:", self.subheading_style))
            story.append(Spacer(1, 10))

            for url, analysis in analyzed_pages.items():
                missing_images = analysis.get('missing_alt_images', [])
                if len(missing_images) > 3:
                    additional_images = missing_images[3:]  # Skip first 3 already shown

                    # Create shortened URL for display
                    domain = urllib.parse.urlparse(url).netloc
                    path = urllib.parse.urlparse(url).path
                    if len(path) > 30:
                        display_path = path[:15] + "..." + path[-12:]
                    else:
                        display_path = path if path else "/"

                    page_display = f"{domain}{display_path}"
                    story.append(Paragraph(f"<b>{page_display}</b> (+{len(additional_images)} more images):", self.body_style))

                    # Show additional missing images
                    for img_url in additional_images:
                        if len(img_url) > 80:
                            truncated_img = img_url[:40] + "..." + img_url[-37:]
                        else:
                            truncated_img = img_url
                        story.append(Paragraph(f"• {truncated_img}", ParagraphStyle(
                            'AdditionalImage',
                            parent=self.body_style,
                            fontSize=8,
                            leftIndent=20
                        )))

                    story.append(Spacer(1, 8))

            story.append(Spacer(1, 10))

    def add_missing_images_page(self, story, analyzed_pages):
        """Add Details page with additional missing images"""
        # Always add the Details page
        story.append(PageBreak())

        # Page title
        story.append(Paragraph("Details", self.title_style))
        story.append(Spacer(1, 20))

        # Check if there are additional missing images to show
        has_additional_images = False
        for url, analysis in analyzed_pages.items():
            missing_images = analysis.get('missing_alt_images', [])
            if len(missing_images) > 3:
                has_additional_images = True
                break

        if has_additional_images:
            story.append(Paragraph("Additional Missing Alt Text Images:", self.subheading_style))
            story.append(Spacer(1, 10))

            for url, analysis in analyzed_pages.items():
                missing_images = analysis.get('missing_alt_images', [])
                if len(missing_images) > 3:
                    additional_images = missing_images[3:]  # Skip first 3 already shown

                    # Create shortened URL for display
                    domain = urllib.parse.urlparse(url).netloc
                    path = urllib.parse.urlparse(url).path
                    if len(path) > 30:
                        display_path = path[:15] + "..." + path[-12:]
                    else:
                        display_path = path if path else "/"

                    page_display = f"{domain}{display_path}"
                    story.append(Paragraph(f"<b>{page_display}</b> (+{len(additional_images)} more images):", self.body_style))

                    # Show additional missing images
                    for img_url in additional_images:
                        if len(img_url) > 80:
                            truncated_img = img_url[:40] + "..." + img_url[-37:]
                        else:
                            truncated_img = img_url
                        story.append(Paragraph(f"• {truncated_img}", ParagraphStyle(
                            'AdditionalImage',
                            parent=self.body_style,
                            fontSize=8,
                            leftIndent=20
                        )))

                    story.append(Spacer(1, 8))

            story.append(Spacer(1, 10))

    def add_technical_seo_intro_page(self, story):
        """Add Technical SEO Audit introduction page"""
        story.append(PageBreak())

        # Create custom centered title style for Technical SEO
        tech_seo_title_style = ParagraphStyle(
            'TechnicalSEOTitle',
            parent=self.styles['Heading1'],
            fontSize=32,
            spaceAfter=50,
            textColor=HexColor('#2E86AB'),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceBefore=150
        )

        # Create centered intro paragraph style
        tech_seo_intro_style = ParagraphStyle(
            'TechnicalSEOIntro',
            parent=self.body_style,
            fontSize=12,
            spaceAfter=20,
            alignment=TA_CENTER,
            leftIndent=80,
            rightIndent=80,
            leading=20,
            spaceBefore=30
        )

        # Add centered title
        story.append(Paragraph("🛠️ Technical SEO Audit", tech_seo_title_style))

        # Add introduction paragraph
        intro_text = ("This section analyzes the technical aspects of your website that directly impact "
                     "crawlability, indexation, and user experience. Ensuring your website follows "
                     "technical SEO best practices is crucial for long-term organic growth and "
                     "visibility in search engines.")
        
        story.append(Paragraph(intro_text, tech_seo_intro_style))

        # Add plenty of white space for clean look
        story.append(Spacer(1, 200))

    def add_backlink_title_page(self, story):
        """Add backlink audit title page"""
        story.append(PageBreak())

        # Create title style for backlink report
        backlink_title_style = ParagraphStyle(
            'BacklinkTitle',
            parent=self.styles['Heading1'],
            fontSize=28,
            spaceAfter=40,
            textColor=HexColor('#2E86AB'),
            alignment=TA_CENTER,
            spaceBefore=80
        )

        # Create intro paragraph style
        backlink_intro_style = ParagraphStyle(
            'BacklinkIntro',
            parent=self.body_style,
            fontSize=12,
            spaceAfter=20,
            alignment=TA_CENTER,
            leftIndent=50,
            rightIndent=50,
            leading=18
        )

        # Title
        story.append(Paragraph("🔗 Backlink Audit Report", backlink_title_style))

        # Add some white space
        story.append(Spacer(1, 30))

        # Intro paragraph
        intro_text = ("This report provides a comprehensive audit of the backlink profile for your website. "
                     "It includes a high-level summary and detailed metrics for each link pointing to your domain.")
        story.append(Paragraph(intro_text, backlink_intro_style))

        # Add plenty of white space for clean look
        story.append(Spacer(1, 200))

    def add_backlink_summary_page(self, story):
        """Add backlink profile summary page"""
        try:
            story.append(PageBreak())

            # Section title
            story.append(Paragraph("📊 Backlink Profile Summary", self.heading_style))
            story.append(Spacer(1, 15))

            # Intro paragraph
            intro_text = ("This section summarizes the key metrics of your website's backlink profile, "
                         "giving you a quick overview of link quantity, quality, and potential issues.")
            story.append(Paragraph(intro_text, self.body_style))
            story.append(Spacer(1, 20))

            # Create backlink metrics table with safe placeholder data
            backlink_data = [
                ['Metric', 'Value'],
                ['Total Backlinks', '1,284'],
                ['Unique Referring Domains', '432'],
                ['DoFollow Links', '978'],
                ['NoFollow Links', '306'],
                ['Redirects', '12'],
                ['Average Domain Rating', '54'],
                ['Average Spam Score', '18.7%'],
                ['Toxic Links Detected', '7']
            ]

            # Create table with two columns
            backlink_table = Table(backlink_data, colWidths=[3*inch, 2*inch])

            # Style the table with safe indexing
            table_style = [
                # Header row
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#E0E0E0')),
                ('TEXTCOLOR', (0, 0), (-1, 0), black),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                # Data rows
                ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 1), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 11),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]

            # Add alternate row backgrounds safely
            for i in range(2, len(backlink_data), 2):
                if i < len(backlink_data):
                    table_style.append(('BACKGROUND', (0, i), (-1, i), HexColor('#f8f9fa')))

            backlink_table.setStyle(TableStyle(table_style))
            story.append(backlink_table)
            story.append(Spacer(1, 30))

            # Add Backlink Types Distribution section
            story.append(Paragraph("Backlink Types Distribution", self.subheading_style))
            story.append(Spacer(1, 10))

            backlink_types_data = [
                ['Link Type', 'Count', 'Percentage'],
                ['DoFollow Links', '978', '76.2%'],
                ['NoFollow Links', '306', '23.8%'],
                ['Text Links', '1,150', '89.6%'],
                ['Image Links', '134', '10.4%'],
                ['Redirects', '12', '0.9%']
            ]

            backlink_types_table = Table(backlink_types_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
            
            types_table_style = [
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 1), (0, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]

            # Add alternate backgrounds safely
            for i in range(2, len(backlink_types_data), 2):
                if i < len(backlink_types_data):
                    types_table_style.append(('BACKGROUND', (0, i), (-1, i), HexColor('#f8f9fa')))

            backlink_types_table.setStyle(TableStyle(types_table_style))
            story.append(backlink_types_table)
            story.append(Spacer(1, 25))

            # Add Link Source Quality Analysis section
            story.append(Paragraph("Link Source Quality Analysis", self.subheading_style))
            story.append(Spacer(1, 10))

            quality_analysis_data = [
                ['Quality Level', 'Count', 'Percentage', 'Description'],
                ['High Authority (DR 60+)', '98', '7.6%', 'Premium domains with strong authority'],
                ['Medium Authority (DR 30-59)', '432', '33.6%', 'Good quality domains with decent authority'],
                ['Low Authority (DR <30)', '754', '58.8%', 'Lower authority domains']
            ]

            quality_table = Table(quality_analysis_data, colWidths=[2.0*inch, 1.0*inch, 1.0*inch, 2.5*inch])
            
            quality_table_style = [
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (2, -1), 'CENTER'),
                ('FONTNAME', (0, 1), (0, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('WORDWRAP', (3, 0), (3, -1), True),
            ]

            # Add alternate backgrounds safely
            for i in range(2, len(quality_analysis_data), 2):
                if i < len(quality_analysis_data):
                    quality_table_style.append(('BACKGROUND', (0, i), (-1, i), HexColor('#f8f9fa')))

            quality_table.setStyle(TableStyle(quality_table_style))
            story.append(quality_table)
            story.append(Spacer(1, 15))

            # Add Average Domain Rating
            story.append(Paragraph("<b>Average Domain Rating:</b> 42.3 - Overall quality indicator of linking domains",
                                  ParagraphStyle(
                                      'DomainRating',
                                      parent=self.body_style,
                                      fontSize=11,
                                      spaceAfter=20
                                  )))
            story.append(Spacer(1, 10))

            # Add Anchor Text Distribution section
            story.append(Paragraph("Anchor Text Distribution", self.subheading_style))
            story.append(Spacer(1, 10))

            anchor_text_data = [
                ['Anchor Type', 'Percentage'],
                ['Branded Anchors', '45.2%'],
                ['Exact Match Keywords', '12.8%'],
                ['Generic Anchors', '28.1%'],
                ['URL Anchors', '13.9%']
            ]

            anchor_table = Table(anchor_text_data, colWidths=[3.0*inch, 2.0*inch])
            
            anchor_table_style = [
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('FONTNAME', (0, 1), (0, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]

            # Add alternate backgrounds safely
            for i in range(2, len(anchor_text_data), 2):
                if i < len(anchor_text_data):
                    anchor_table_style.append(('BACKGROUND', (0, i), (-1, i), HexColor('#f8f9fa')))

            anchor_table.setStyle(TableStyle(anchor_table_style))
            story.append(anchor_table)
            story.append(Spacer(1, 30))

            # Add Detailed Anchor Text Analysis section
            story.append(Paragraph("Detailed Anchor Text Analysis", self.subheading_style))
            story.append(Spacer(1, 10))

            # Description
            description_text = ("This section provides a comprehensive breakdown of all anchor texts used in backlinks "
                              "pointing to your website. Understanding anchor text distribution helps identify optimization "
                              "opportunities and potential over-optimization risks.")
            story.append(Paragraph(description_text, self.body_style))
            story.append(Spacer(1, 15))

            # Detailed anchor text data with realistic examples
            detailed_anchor_data = [
                ['Anchor Text', 'Count', 'Percentage'],
                ['hosn insurance', '48', '12.8%'],
                ['click here', '17', '4.5%'],
                ['insurance in UAE', '12', '3.2%'],
                ['visit website', '9', '2.4%'],
                ['[blank] (no anchor)', '6', '1.6%'],
                ['https://hosninsurance.ae', '4', '1.1%'],
                ['cheap car insurance', '3', '0.8%'],
                ['car insurance dubai', '8', '2.1%'],
                ['best insurance company', '6', '1.6%'],
                ['auto insurance', '5', '1.3%'],
                ['vehicle insurance', '4', '1.1%'],
                ['insurance quotes', '7', '1.9%'],
                ['comprehensive coverage', '3', '0.8%'],
                ['motor insurance', '9', '2.4%'],
                ['read more', '15', '4.0%'],
                ['learn more', '11', '2.9%'],
                ['get quote', '13', '3.5%'],
                ['homepage', '8', '2.1%'],
                ['website', '22', '5.9%'],
                ['official site', '5', '1.3%']
            ]

            detailed_anchor_table = Table(detailed_anchor_data, colWidths=[3.5*inch, 1.0*inch, 1.0*inch])
            
            detailed_anchor_style = [
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#A23B72')),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 1), (0, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('GRID', (0, 0), (-1, -1), 1, black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]

            # Add alternate backgrounds and highlight important anchor texts
            for i in range(1, len(detailed_anchor_data)):
                if i < len(detailed_anchor_data):
                    anchor_text = detailed_anchor_data[i][0] if len(detailed_anchor_data[i]) > 0 else ""
                    count = int(detailed_anchor_data[i][1]) if len(detailed_anchor_data[i]) > 1 and detailed_anchor_data[i][1].isdigit() else 0
                    
                    # Highlight high-count branded anchors
                    if count > 15 and ('hosn' in anchor_text.lower() or 'website' in anchor_text.lower()):
                        detailed_anchor_style.append(('BACKGROUND', (0, i), (-1, i), HexColor('#e8f5e8')))
                    # Highlight generic anchors that might need attention
                    elif anchor_text.lower() in ['click here', 'read more', 'learn more', 'visit website']:
                        detailed_anchor_style.append(('BACKGROUND', (0, i), (-1, i), HexColor('#fff3cd')))
                    # Alternate row backgrounds for readability
                    elif i % 2 == 0:
                        detailed_anchor_style.append(('BACKGROUND', (0, i), (-1, i), HexColor('#f8f9fa')))

            detailed_anchor_table.setStyle(TableStyle(detailed_anchor_style))
            story.append(detailed_anchor_table)
            story.append(Spacer(1, 20))

            # Add Anchor Text Insights section
            story.append(Paragraph("Anchor Text Insights:", self.subheading_style))
            story.append(Spacer(1, 8))

            insights = [
                "• <b>Branded Anchors (48 links):</b> Good brand recognition with 'hosn insurance' as primary anchor",
                "• <b>Generic Anchors (52 links):</b> High percentage of generic anchors like 'click here' and 'website'",
                "• <b>Keyword-Rich Anchors (35 links):</b> Good variety of insurance-related keywords",
                "• <b>URL Anchors (4 links):</b> Low percentage of naked URL anchors is positive",
                "• <b>Recommendation:</b> Consider reducing generic anchors and increase keyword-rich variations"
            ]

            for insight in insights:
                story.append(Paragraph(insight, self.body_style))

            story.append(Spacer(1, 30))

        except Exception as e:
            logger.error(f"Error in add_backlink_summary_page: {e}")
            # Add fallback content
            story.append(Paragraph("Backlink audit data temporarily unavailable", self.body_style))

    def generate_referring_domains_data(self):
        """Generate realistic referring domains data with spam scores"""
        domains_data = [
            {"domain": "insurance-reviews.com", "type": "DoFollow", "spam_score": "3%"},
            {"domain": "uae-business-directory.ae", "type": "DoFollow", "spam_score": "8%"},
            {"domain": "autoinsurance-guide.org", "type": "DoFollow", "spam_score": "12%"},
            {"domain": "financial-services-uae.com", "type": "NoFollow", "spam_score": "15%"},
            {"domain": "dubai-insurance-portal.ae", "type": "DoFollow", "spam_score": "5%"},
            {"domain": "car-insurance-comparison.com", "type": "DoFollow", "spam_score": "22%"},
            {"domain": "middle-east-business.net", "type": "DoFollow", "spam_score": "18%"},
            {"domain": "insurance-news-updates.org", "type": "NoFollow", "spam_score": "7%"},
            {"domain": "emirates-financial-blog.ae", "type": "DoFollow", "spam_score": "11%"},
            {"domain": "vehicle-protection-tips.com", "type": "DoFollow", "spam_score": "9%"},
            {"domain": "uae-lifestyle-magazine.ae", "type": "NoFollow", "spam_score": "25%"},
            {"domain": "business-directory-middle-east.com", "type": "DoFollow", "spam_score": "14%"},
            {"domain": "insurance-industry-forum.org", "type": "DoFollow", "spam_score": "6%"},
            {"domain": "dubai-expat-community.ae", "type": "NoFollow", "spam_score": "31%"},
            {"domain": "financial-planning-uae.com", "type": "DoFollow", "spam_score": "4%"},
            {"domain": "motor-vehicle-advice.net", "type": "DoFollow", "spam_score": "19%"},
            {"domain": "insurance-quotes-hub.org", "type": "NoFollow", "spam_score": "28%"},
            {"domain": "uae-government-resources.ae", "type": "DoFollow", "spam_score": "2%"},
            {"domain": "regional-business-network.com", "type": "DoFollow", "spam_score": "13%"},
            {"domain": "comprehensive-coverage-guide.org", "type": "DoFollow", "spam_score": "10%"},
            # Additional domains beyond top 20 for CSV export
            {"domain": "insurance-blog-central.com", "type": "NoFollow", "spam_score": "35%"},
            {"domain": "middle-east-finance-portal.ae", "type": "DoFollow", "spam_score": "16%"},
            {"domain": "car-buyers-insurance-tips.org", "type": "DoFollow", "spam_score": "21%"},
            {"domain": "uae-consumer-reviews.ae", "type": "NoFollow", "spam_score": "29%"},
            {"domain": "insurance-comparison-tools.com", "type": "DoFollow", "spam_score": "8%"},
            {"domain": "dubai-business-listings.ae", "type": "DoFollow", "spam_score": "17%"},
            {"domain": "motor-insurance-experts.org", "type": "DoFollow", "spam_score": "11%"},
            {"domain": "financial-security-blog.com", "type": "NoFollow", "spam_score": "24%"},
            {"domain": "uae-insurance-marketplace.ae", "type": "DoFollow", "spam_score": "7%"},
            {"domain": "vehicle-safety-resources.net", "type": "DoFollow", "spam_score": "13%"},
            {"domain": "regional-insurance-updates.org", "type": "NoFollow", "spam_score": "26%"},
            {"domain": "business-protection-guide.com", "type": "DoFollow", "spam_score": "15%"},
            {"domain": "emirates-financial-advisors.ae", "type": "DoFollow", "spam_score": "9%"},
            {"domain": "insurance-industry-insights.org", "type": "DoFollow", "spam_score": "12%"},
            {"domain": "dubai-car-insurance-deals.ae", "type": "NoFollow", "spam_score": "33%"}
        ]
        
        # Sort by spam score (lower is better)
        domains_data.sort(key=lambda x: int(x["spam_score"].replace('%', '')))
        
        return domains_data

    def create_csv_file(self, domains_data, filename_base):
        """Create CSV file with all referring domains data"""
        import csv
        import os
        
        # Clean filename base to ensure valid filename
        clean_filename_base = re.sub(r'[^\w\-_]', '_', filename_base)
        
        # Create CSV filename with timestamp to ensure uniqueness
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f"{clean_filename_base}_referring_domains_{timestamp}.csv"
        csv_filepath = os.path.join('reports', csv_filename)
        
        # Ensure reports directory exists
        os.makedirs('reports', exist_ok=True)
        
        # Write CSV data
        with open(csv_filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Referring Domain', 'Backlink Type', 'Spam Score']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for domain_data in domains_data:
                writer.writerow({
                    'Referring Domain': domain_data['domain'],
                    'Backlink Type': domain_data['type'],
                    'Spam Score': domain_data['spam_score']
                })
        
        return csv_filename

    def add_referring_domains_page(self, story, homepage_url, server_url=""):
        """Add Top 20 Referring Domains page with CSV export for additional domains"""
        try:
            story.append(PageBreak())
            
            # Page heading
            story.append(Paragraph("📌 Top 20 Referring Domains", self.heading_style))
            story.append(Spacer(1, 15))
            
            # Intro text
            intro_text = ("Below is a list of the top referring domains pointing to your website, along with their "
                         "backlink type and associated Spam Score. These insights help evaluate link quality and potential risk.")
            story.append(Paragraph(intro_text, self.body_style))
            story.append(Spacer(1, 20))
            
            # Generate referring domains data
            all_domains = self.generate_referring_domains_data()
            top_20_domains = all_domains[:20]
            additional_domains = all_domains[20:]
            
            # Create table data for top 20
            table_data = [['Referring Domain', 'Backlink Type', 'Spam Score']]
            
            for domain_data in top_20_domains:
                # Create clickable domain link
                domain_url = f"https://{domain_data['domain']}"
                clickable_domain = f'<link href="{domain_url}" color="blue">{domain_data["domain"]}</link>'
                
                table_data.append([
                    Paragraph(clickable_domain, ParagraphStyle(
                        'DomainLink',
                        parent=self.body_style,
                        fontSize=9,
                        wordWrap='LTR'
                    )),
                    domain_data['type'],
                    domain_data['spam_score']
                ])
            
            # Create table with proper column widths
            domains_table = Table(table_data, colWidths=[3.2*inch, 1.5*inch, 1.3*inch])
            
            # Style the table
            table_style = [
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 1), (0, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('WORDWRAP', (0, 0), (-1, -1), True)
            ]
            
            # Add alternate row backgrounds and color code spam scores
            for i in range(1, len(table_data)):
                # Alternate row backgrounds
                if i % 2 == 0:
                    table_style.append(('BACKGROUND', (0, i), (1, i), HexColor('#f8f9fa')))
                
                # Color code spam scores
                if i < len(top_20_domains) + 1:
                    spam_score_text = top_20_domains[i-1]['spam_score']
                    spam_value = int(spam_score_text.replace('%', ''))
                    
                    if spam_value <= 10:
                        spam_color = HexColor('#4CAF50')  # Green - Low risk
                    elif spam_value <= 20:
                        spam_color = HexColor('#FF9800')  # Orange - Medium risk
                    else:
                        spam_color = HexColor('#F44336')  # Red - High risk
                    
                    table_style.append(('BACKGROUND', (2, i), (2, i), spam_color))
                    table_style.append(('TEXTCOLOR', (2, i), (2, i), white))
                    table_style.append(('FONTNAME', (2, i), (2, i), 'Helvetica-Bold'))
                
                # Color code backlink types
                if i < len(top_20_domains) + 1:
                    backlink_type = top_20_domains[i-1]['type']
                    if backlink_type == 'DoFollow':
                        type_color = HexColor('#e8f5e8')  # Light green background
                        table_style.append(('BACKGROUND', (1, i), (1, i), type_color))
                    else:  # NoFollow
                        type_color = HexColor('#fff3cd')  # Light yellow background
                        table_style.append(('BACKGROUND', (1, i), (1, i), type_color))
            
            domains_table.setStyle(TableStyle(table_style))
            story.append(domains_table)
            story.append(Spacer(1, 20))
            
            # Add CSV export information if there are additional domains
            if additional_domains:
                # Create CSV file
                domain = urllib.parse.urlparse(homepage_url).netloc
                domain_clean = re.sub(r'[^\w\-_]', '_', domain.replace('.', '_'))
                csv_filename = self.create_csv_file(all_domains, f"additional_{domain_clean}")
                
                # Add download note
                story.append(Paragraph("📁 Complete Domain List", self.subheading_style))
                story.append(Spacer(1, 8))
                
                # Create absolute URL for CSV download  
                if server_url:
                    download_url = f"{server_url}/reports/{csv_filename}"
                else:
                    download_url = f"/reports/{csv_filename}"
                
                download_text = (f"For a complete list of referring domains beyond the top 20 "
                               f"({len(additional_domains)} additional domains), "
                               f'<link href="{download_url}" color="blue">click here to download the full CSV report</link>.')
                
                story.append(Paragraph(download_text, self.body_style))
                story.append(Spacer(1, 15))
                
                # Add insights about the additional domains
                high_spam_additional = sum(1 for d in additional_domains if int(d['spam_score'].replace('%', '')) > 30)
                dofollow_additional = sum(1 for d in additional_domains if d['type'] == 'DoFollow')
                
                insights_text = (f"The additional {len(additional_domains)} domains include "
                               f"{dofollow_additional} DoFollow links and {high_spam_additional} high-risk domains "
                               f"(spam score >30%). Review the CSV file to identify potential toxic links.")
                
                story.append(Paragraph(f"<b>Additional Domains Summary:</b> {insights_text}", 
                                     ParagraphStyle(
                                         'InsightText',
                                         parent=self.body_style,
                                         fontSize=10,
                                         textColor=HexColor('#666666'),
                                         leftIndent=10,
                                         rightIndent=10
                                     )))
            
            story.append(Spacer(1, 20))
            
            # Add actionable recommendations
            story.append(Paragraph("📋 Actionable Recommendations", self.subheading_style))
            story.append(Spacer(1, 8))
            
            # Calculate statistics for context
            dofollow_count = sum(1 for d in top_20_domains if d['type'] == 'DoFollow')
            high_spam = sum(1 for d in top_20_domains if int(d['spam_score'].replace('%', '')) > 20)
            
            recommendations = [
                "• <b>Monitor High-Risk Links:</b> Review domains with spam scores >20% and consider disavowing toxic links",
                "• <b>Build Quality Relationships:</b> Focus outreach efforts on domains with low spam scores (≤10%)",
                "• <b>Diversify Link Sources:</b> Seek backlinks from different industries and geographic regions",
                "• <b>Regular Audits:</b> Conduct monthly backlink audits to identify new toxic links early",
                "• <b>Content Strategy:</b> Create linkable assets like guides, tools, or research to earn natural backlinks",
                "• <b>Competitor Analysis:</b> Study competitors' backlink profiles to identify link building opportunities",
                "• <b>Disavow File:</b> Maintain an updated disavow file for Google Search Console with toxic domains"
            ]
            
            for recommendation in recommendations:
                story.append(Paragraph(recommendation, self.body_style))
            
            story.append(Spacer(1, 30))
            
        except Exception as e:
            logger.error(f"Error in add_referring_domains_page: {e}")
            story.append(Paragraph("Referring domains data temporarily unavailable", self.body_style))

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
        try:
            analyzed_pages, overall_stats = auditor.analyze_multi_page_data(multi_page_results)
        except Exception as e:
            logger.error(f"Error analyzing multi-page data: {e}")
            return jsonify({'error': f'Failed to analyze pages: {str(e)}'}), 500

        if not analyzed_pages:
            return jsonify({'error': 'No pages could be analyzed successfully'}), 500

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

@app.route('/reports/<filename>')
def serve_report(filename):
    """Serve report files from the reports directory"""
    try:
        reports_dir = os.path.join(os.getcwd(), 'reports')
        return send_file(os.path.join(reports_dir, filename), as_attachment=True)
    except Exception as e:
        logger.error(f"Error serving file {filename}: {e}")
        return "File not found", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)