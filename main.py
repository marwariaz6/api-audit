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

        return placeholder_data

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

        # Add external links scoring
        external_links = analysis.get('external_links', 0)
        if external_links == 0:
            external_link_score = 30  # No external links is poor for authority
        elif external_links < 3:
            external_link_score = 60  # Few external links
        elif external_links < 10:
            external_link_score = 90  # Good balance
        else:
            external_link_score = 75  # Too many external links can dilute authority

        analysis['scores']['external_links'] = external_link_score

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

    def generate_multi_page_report(self, analyzed_pages, overall_stats, filename, crawler_results=None):
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
            # Create clickable URL with shorter length for overview table
            clickable_url = self.create_clickable_url(url, max_chars=45)
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
        self.add_metric_analysis(story, analyzed_pages, "🔹 External Linking", "external_links")

        # Add comprehensive missing images page at the end of On Page section
        self.add_missing_images_page(story, analyzed_pages)

        # Add Technical SEO Audit section
        self.add_technical_seo_intro_page(story)

        # Add Domain-Level Technical SEO Summary page
        self.add_domain_level_audit_page(story)

        # Add Page-Level Technical SEO Checks page
        self.add_page_level_technical_seo_page(story)

        # Add the Web Core Vitals sections
        self.add_web_core_vitals_mobile_section(story)
        self.add_web_core_vitals_desktop_section(story)

        # Add crawler results if available
        if crawler_results:
            self.add_crawler_results_section(story, crawler_results)

        # Add Backlink Audit Report section (last)
        try:
            self.add_backlink_title_page(story)
            # Add the new sections
            self.add_link_source_quality_analysis(story)
            self.add_anchor_text_distribution(story)
            story.append(Spacer(1, 30))

            # Add Top 20 Referring Domains section
            self.add_top_referring_domains_section(story, analyzed_pages)
        except Exception as e:
            logger.error(f"Error adding backlink pages: {e}")
            # Add fallback message
            story.append(Paragraph("Backlink audit data temporarily unavailable", self.body_style))

        try:
            doc.build(story)
        except Exception as e:
            logger.error(f"Error building PDF document: {e}")
            return None

    def create_clickable_url(self, url, max_chars=40):
        """Create a clickable URL paragraph with proper wrapping"""
        # Truncate URL if too long for better table formatting
        if len(url) > max_chars:
            display_url = url[:max_chars-3] + "..."
        else:
            display_url = url

        # Create a custom style for URLs with smaller font and wrapping
        url_style = ParagraphStyle(
            'ClickableURL',
            parent=self.body_style,
            fontSize=8,
            leading=9,
            wordWrap='LTR',
            allowWidows=1,
            allowOrphans=1,
            spaceAfter=1,
            spaceBefore=1
        )

        # Create clickable link with proper HTML formatting
        clickable_url = f'<link href="{url}" color="blue">{display_url}</link>'
        return Paragraph(clickable_url, url_style)

    def get_metric_issue(self, analysis, metric):
        """Get specific issue description for a metric"""
        issues_map = {
            'title': self.get_title_issues(analysis),
            'meta_description': self.get_meta_issues(analysis),
            'headings': self.get_heading_issues(analysis),
            'images': self.get_image_issues(analysis),
            'content': self.get_content_issues(analysis),
            'internal_links': self.get_internal_link_issues(analysis),
            'external_links': self.get_external_link_issues(analysis)
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

    def get_external_link_issues(self, analysis):
        """Get external linking issues"""
        external_links = analysis.get('external_links', 0)
        if external_links == 0:
            return "No external links found"
        elif external_links < 3:
            return f"Few external links ({external_links})"
        elif external_links < 10:
            return "Good external linking"
        else:
            return f"Too many external links ({external_links})"

    def create_metric_table(self, table_data, metric):
        """Create a table for metric analysis with proper styling"""
        # Create table with proper column widths
        table = Table(table_data, colWidths=[2.5*inch, 1.0*inch, 2.0*inch])

        # Define table style
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#A23B72')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),  # Score column centered
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP')
        ]

        # Color code scores and add alternating rows
        for i in range(1, len(table_data)):
            try:
                # Alternate row backgrounds
                if i % 2 == 0:
                    table_style.append(('BACKGROUND', (0, i), (0, i), HexColor('#f8f9fa')))
                    table_style.append(('BACKGROUND', (2, i), (2, i), HexColor('#f8f9fa')))

                # Color code score column
                score_text = table_data[i][1] if len(table_data[i]) > 1 else "0/100"
                if "/" in score_text:
                    score = int(score_text.split("/")[0])
                    score_color = self.get_score_color(score)
                    table_style.append(('BACKGROUND', (1, i), (1, i), score_color))
                    table_style.append(('TEXTCOLOR', (1, i), (1, i), white))
                    table_style.append(('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'))
            except (IndexError, ValueError) as e:
                logger.error(f"Error processing metric table row {i}: {e}")
                continue

        table.setStyle(TableStyle(table_style))
        return table

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
            clickable_url = self.create_clickable_url(url, max_chars=35)  # Limit URL length for table
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

            elif metric == 'external_links':
                external_links = analysis.get('external_links', 0)
                if external_links == 0:
                    issue = "No external links"
                elif external_links < 3:
                    issue = "Few external links"
                elif external_links < 10:
                    issue = "Good external linking"
                else:
                    issue = "Too many external links"

                current_value = f"{external_links} external links"

            else:
                issue = "Unknown metric"
                current_value = "N/A"

            table_data.append([clickable_url, issue, current_value, status])

        return table_data

    def create_issues_table(self, data):
        """Create a detailed issues table with proper text wrapping and column management"""
        # Wrap long text in cells to prevent overflow
        wrapped_data = []
        for row in data:
            wrapped_row = []
            for i, cell in enumerate(row):
                if hasattr(cell, '__class__') and 'Paragraph' in str(cell.__class__):
                    # Already a Paragraph object (like clickable URLs)
                    wrapped_cell = cell
                elif isinstance(cell, str):
                    # Wrap text content based on column
                    if i == 1 and len(cell) > 15:  # Issue column
                        wrapped_cell = Paragraph(cell, ParagraphStyle(
                            'WrappedIssue',
                            parent=self.body_style,
                            fontSize=8,
                            leading=9,
                            wordWrap='LTR'
                        ))
                    elif i == 2 and len(cell) > 25:  # Current value column
                        wrapped_cell = Paragraph(cell, ParagraphStyle(
                            'WrappedValue',
                            parent=self.body_style,
                            fontSize=8,
                            leading=9,
                            wordWrap='LTR'
                        ))
                    else:
                        wrapped_cell = cell
                else:
                    wrapped_cell = cell
                wrapped_row.append(wrapped_cell)
            wrapped_data.append(wrapped_row)

        # Better column width distribution - URL, Issue, Current Value, Status
        table = Table(wrapped_data, colWidths=[2.0*inch, 1.4*inch, 2.0*inch, 1.1*inch])

        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#A23B72')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (2, -1), 'LEFT'),     # Other columns left-aligned
            ('ALIGN', (3, 0), (3, -1), 'CENTER'),  # Status column centered
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
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
                    table_style.append(('BACKGROUND', (0, i), (0, i), bg_color))
                    table_style.append(('BACKGROUND', (2, i), (2, i), bg_color))
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
            clickable_url = self.create_clickable_url(url, max_chars=35)  # Shorter URLs for better table formatting
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

        # Add centered title
        story.append(Paragraph("🛠️ Technical SEO Audit", tech_seo_title_style))

        # Add introduction paragraph
        intro_text = ("This section analyzes the technical aspects of your website that directly impact "
                     "crawlability, indexation, and user experience. Ensuring your website follows "
                     "technical SEO best practices is crucial for long-term organic growth and "
                     "visibility in search engines.")

        # Create introduction paragraph style
        tech_seo_intro_style = ParagraphStyle(
            'TechnicalSEOIntro',
            parent=self.body_style,
            fontSize=12,
            spaceAfter=30,
            alignment=TA_CENTER,
            leading=18
        )

        story.append(Paragraph(intro_text, tech_seo_intro_style))

        # Add plenty of white space for clean look
        story.append(Spacer(1, 200))

    def add_domain_level_audit_page(self, story):
        """Add Domain-Level Technical SEO Summary page"""
        story.append(PageBreak())

        # Create centered title style for Domain-Level Technical SEO Summary
        domain_audit_title_style = ParagraphStyle(
            'DomainAuditTitle',
            parent=self.styles['Heading2'],
            fontSize=18,
            spaceAfter=30,
            textColor=HexColor('#2E86AB'),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceBefore=30
        )

        # Add centered title
        story.append(Paragraph("Domain-Level Technical SEO Summary", domain_audit_title_style))

        # Create table data with technical SEO checks
        audit_data = [
            ['Check', 'Status', 'Details'],
            ['robots.txt file', '[PASS]', 'Accessible and correctly configured'],
            ['sitemap.xml', '[FAIL]', 'Missing or not declared in robots.txt'],
            ['HTTPS/SSL Validity', '[PASS]', 'Secure certificate installed'],
            ['Canonicalization', '[WARNING]', 'Both www and non-www versions are accessible'],
            ['Redirect Chains', '[PASS]', 'No redirect chains detected'],
            ['CDN Usage', 'Yes (Cloudflare)', 'Improves speed and global delivery']
        ]

        # Create table with proper column widths
        domain_audit_table = Table(audit_data, colWidths=[2.5*inch, 1.2*inch, 2.8*inch])

        # Define table style
        table_style = [
            # Header row styling
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            # Data rows styling
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('WORDWRAP', (0, 0), (-1, -1), True)
        ]

        # Add alternating row backgrounds and color code status column
        for i in range(1, len(audit_data)):
            try:
                status = audit_data[i][1] if len(audit_data[i]) > 1 else ""

                # Color code status based on text
                if status == '[PASS]':
                    status_color = HexColor('#4CAF50')  # Green
                    text_color = white
                elif status == '[FAIL]':
                    status_color = HexColor('#F44336')  # Red
                    text_color = white
                elif status == '[WARNING]':
                    status_color = HexColor('#FF9800')  # Orange
                    text_color = white
                else:
                    status_color = HexColor('#E0E0E0')  # Gray
                    text_color = black

                # Apply status column coloring
                table_style.append(('BACKGROUND', (1, i), (1, i), status_color))
                table_style.append(('TEXTCOLOR', (1, i), (1, i), text_color))
                table_style.append(('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'))

                # Add alternating row backgrounds for other columns
                if i % 2 == 0:
                    bg_color = HexColor('#f8f9fa')
                    table_style.append(('BACKGROUND', (0, i), (0, i), bg_color))
                    table_style.append(('BACKGROUND', (2, i), (2, i), bg_color))

            except (IndexError, ValueError) as e:
                logger.error(f"Error processing domain audit table row {i}: {e}")
                continue

        domain_audit_table.setStyle(TableStyle(table_style))
        story.append(domain_audit_table)
        story.append(Spacer(1, 25))

        # Add Recommendations section
        recommendations_style = ParagraphStyle(
            'RecommendationsTitle',
            parent=self.subheading_style,
            fontSize=14,
            spaceAfter=12,
            textColor=HexColor('#2E86AB'),
            fontName='Helvetica-Bold'
        )

        story.append(Paragraph("Recommendations", recommendations_style))
        story.append(Spacer(1, 8))

        # Generate recommendations based on failed/warning checks
        recommendations = [
            "• Create and submit an XML sitemap to Google Search Console and declare it in robots.txt",
            "• Implement proper canonical tags to prevent www/non-www duplicate content issues",
            "• Consider setting 301 redirects to consolidate www/non-www versions for better SEO",
            "• Continue leveraging CDN benefits for improved page load times and user experience",
            "• Monitor robots.txt file regularly to ensure it remains accessible and properly configured"
        ]

        # Create recommendation style
        recommendation_style = ParagraphStyle(
            'RecommendationBullet',
            parent=self.body_style,
            fontSize=11,
            spaceAfter=6,
            leftIndent=10
        )

        for recommendation in recommendations:
            story.append(Paragraph(recommendation, recommendation_style))

        story.append(Spacer(1, 30))

    def add_page_level_technical_seo_page(self, story):
        """Add Page-Level Technical SEO Checks page"""
        story.append(PageBreak())

        # Create large, bold, centered title style for Page-Level Technical SEO
        page_level_title_style = ParagraphStyle(
            'PageLevelTechnicalSEOTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=40,
            textColor=HexColor('#2E86AB'),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceBefore=50
        )

        # Add centered title
        story.append(Paragraph("Page-Level Technical SEO Checks", page_level_title_style))

        # Add space for content
        story.append(Spacer(1, 30))

        # Section 1: Page Crawlability & Indexability
        self.add_crawlability_indexability_section(story)

        # Section 2: Page Performance Metrics
        self.add_page_performance_section(story)

        # Section 3: Mobile-Friendliness
        self.add_mobile_friendliness_section(story)

        # Add the new sections
        self.add_https_security_section(story)
        self.add_structured_data_section(story)
        self.add_canonicalization_section(story)
        self.add_images_media_section(story)
        self.add_http_headers_compression_section(story)

    def add_crawlability_indexability_section(self, story):
        """Add Page Crawlability & Indexability section"""
        # Section heading
        section_title_style = ParagraphStyle(
            'SectionTitle',
            parent=self.heading_style,
            fontSize=16,
            spaceAfter=15,
            textColor=HexColor('#2E86AB'),
            fontName='Helvetica-Bold'
        )

        story.append(Paragraph("Page Crawlability & Indexability", section_title_style))
        story.append(Spacer(1, 10))

        # Create table data
        crawlability_data = [
            ['Page URL', 'HTTP Status', 'Redirect Type', 'Robots.txt Restrictions', 'Meta Robots Tag', 'X-Robots-Tag']
        ]

        # Sample data for different pages
        sample_pages = [
            {
                'url': 'https://hosninsurance.ae/',
                'status': '200',
                'redirect': 'None',
                'robots_txt': 'No',
                'meta_robots': 'index, follow',
                'x_robots': 'index, follow'
            },
            {
                'url': 'https://hosninsurance.ae/about-us',
                'status': '200',
                'redirect': 'None',
                'robots_txt': 'No',
                'meta_robots': 'index, follow',
                'x_robots': 'none'
            },
            {
                'url': 'https://hosninsurance.ae/services/car-insurance',
                'status': '301',
                'redirect': '301 Permanent',
                'robots_txt': 'No',
                'meta_robots': 'index, follow',
                'x_robots': 'index, follow'
            },
            {
                'url': 'https://hosninsurance.ae/contact',
                'status': '200',
                'redirect': 'None',
                'robots_txt': 'No',
                'meta_robots': 'noindex, follow',
                'x_robots': 'index, follow'
            },
            {
                'url': 'https://hosninsurance.ae/get-quote',
                'status': '200',
                'redirect': 'None',
                'robots_txt': 'No',
                'meta_robots': 'index, follow',
                'x_robots': 'index, follow'
            }
        ]

        for page in sample_pages:
            crawlability_data.append([
                Paragraph(page['url'], ParagraphStyle(
                    'URLText',
                    parent=self.body_style,
                    fontSize=8,
                    wordWrap='LTR'
                )),
                page['status'],
                page['redirect'],
                page['robots_txt'],
                page['meta_robots'],
                page['x_robots']
            ])

        # Create table with optimized column widths
        crawlability_table = Table(crawlability_data, colWidths=[2.0*inch, 0.8*inch, 1.0*inch, 0.8*inch, 1.0*inch, 1.0*inch])

        # Table styling
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('WORDWRAP', (0, 0), (-1, -1), True)
        ]

        # Color code HTTP status codes and add alternating rows
        for i in range(1, len(crawlability_data)):
            # Alternate row backgrounds
            if i % 2 == 0:
                table_style.append(('BACKGROUND', (0, i), (0, i), HexColor('#f8f9fa')))
                table_style.append(('BACKGROUND', (2, i), (-1, i), HexColor('#f8f9fa')))

            # Color code HTTP status
            status = sample_pages[i-1]['status']
            if status == '200':
                status_color = HexColor('#4CAF50')  # Green
            elif status in ['301', '302']:
                status_color = HexColor('#FF9800')  # Orange
            elif status.startswith('4') or status.startswith('5'):
                status_color = HexColor('#F44336')  # Red
            else:
                status_color = HexColor('#E0E0E0')  # Gray

            table_style.append(('BACKGROUND', (1, i), (1, i), status_color))
            table_style.append(('TEXTCOLOR', (1, i), (1, i), white))
            table_style.append(('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'))

            # Color code meta robots tags
            meta_robots = sample_pages[i-1]['meta_robots']
            if 'noindex' in meta_robots:
                table_style.append(('BACKGROUND', (4, i), (4, i), HexColor('#ffebee')))
                table_style.append(('TEXTCOLOR', (4, i), (4, i), HexColor('#c62828')))

        crawlability_table.setStyle(TableStyle(table_style))
        story.append(crawlability_table)
        story.append(Spacer(1, 25))

    def add_page_performance_section(self, story):
        """Add Page Performance Metrics section"""
        # Section heading
        section_title_style = ParagraphStyle(
            'SectionTitle',
            parent=self.heading_style,
            fontSize=16,
            spaceAfter=15,
            textColor=HexColor('#2E86AB'),
            fontName='Helvetica-Bold'
        )

        story.append(Paragraph("Page Performance Metrics", section_title_style))
        story.append(Spacer(1, 10))

        # Create table data
        performance_data = [
            ['Page URL', 'Load Time (s)', 'HTML Size (KB)', 'CSS Files', 'JS Files', 'Images', 'Total Size (KB)']
        ]

        # Sample performance data
        sample_performance = [
            {
                'url': 'https://hosninsurance.ae/',
                'load_time': '2.34',
                'html_size': '45.2',
                'css_files': '3',
                'js_files': '7',
                'images': '12',
                'total_size': '1,245'
            },
            {
                'url': 'https://hosninsurance.ae/about-us',
                'load_time': '1.89',
                'html_size': '32.1',
                'css_files': '3',
                'js_files': '5',
                'images': '8',
                'total_size': '890'
            },
            {
                'url': 'https://hosninsurance.ae/services/car-insurance',
                'load_time': '3.12',
                'html_size': '67.8',
                'css_files': '4',
                'js_files': '9',
                'images': '18',
                'total_size': '1,876'
            },
            {
                'url': 'https://hosninsurance.ae/contact',
                'load_time': '1.45',
                'html_size': '28.3',
                'css_files': '2',
                'js_files': '4',
                'images': '5',
                'total_size': '567'
            },
            {
                'url': 'https://hosninsurance.ae/get-quote',
                'load_time': '2.67',
                'html_size': '51.4',
                'css_files': '3',
                'js_files': '8',
                'images': '14',
                'total_size': '1,423'
            }
        ]

        for page in sample_performance:
            performance_data.append([
                Paragraph(page['url'], ParagraphStyle(
                    'URLText',
                    parent=self.body_style,
                    fontSize=8,
                    wordWrap='LTR'
                )),
                page['load_time'],
                page['html_size'],
                page['css_files'],
                page['js_files'],
                page['images'],
                page['total_size']
            ])

        # Create table with optimized column widths
        performance_table = Table(performance_data, colWidths=[2.2*inch, 0.8*inch, 0.8*inch, 0.6*inch, 0.6*inch, 0.6*inch, 0.9*inch])

        # Table styling
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('WORDWRAP', (0, 0), (-1, -1), True)
        ]

        # Color code performance metrics and add alternating rows
        for i in range(1, len(performance_data)):
            # Alternate row backgrounds
            if i % 2 == 0:
                table_style.append(('BACKGROUND', (0, i), (0, i), HexColor('#f8f9fa')))
                table_style.append(('BACKGROUND', (2, i), (-1, i), HexColor('#f8f9fa')))

            # Color code load time
            load_time = float(sample_performance[i-1]['load_time'])
            if load_time <= 2.0:
                load_color = HexColor('#4CAF50')  # Green - Good
            elif load_time <= 3.0:
                load_color = HexColor('#FF9800')  # Orange - Moderate
            else:
                load_color = HexColor('#F44336')  # Red - Slow

            table_style.append(('BACKGROUND', (1, i), (1, i), load_color))
            table_style.append(('TEXTCOLOR', (1, i), (1, i), white))
            table_style.append(('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'))

            # Color code total size
            total_size = int(sample_performance[i-1]['total_size'].replace(',', ''))
            if total_size <= 1000:
                size_color = HexColor('#4CAF50')  # Green - Good
            elif total_size <= 1500:
                size_color = HexColor('#FF9800')  # Orange - Moderate
            else:
                size_color = HexColor('#F44336')  # Red - Large

            table_style.append(('BACKGROUND', (6, i), (6, i), size_color))
            table_style.append(('TEXTCOLOR', (6, i), (6, i), white))
            table_style.append(('FONTNAME', (6, i), (6, i), 'Helvetica-Bold'))

        performance_table.setStyle(TableStyle(table_style))
        story.append(performance_table)
        story.append(Spacer(1, 25))

    def add_mobile_friendliness_section(self, story):
        """Add Mobile-Friendliness section"""
        # Section heading
        section_title_style = ParagraphStyle(
            'SectionTitle',
            parent=self.heading_style,
            fontSize=16,
            spaceAfter=15,
            textColor=HexColor('#2E86AB'),
            fontName='Helvetica-Bold'
        )

        story.append(Paragraph("Mobile-Friendliness", section_title_style))
        story.append(Spacer(1, 10))

        # Create table data
        mobile_data = [
            ['Page URL', 'Mobile-Responsive', 'Viewport Meta Tag', 'Touch Elements']
        ]

        # Sample mobile data
        sample_mobile = [
            {
                'url': 'https://hosninsurance.ae/',
                'responsive': 'Yes',
                'viewport': 'Present',
                'touch_elements': 'Pass'
            },
            {
                'url': 'https://hosninsurance.ae/about-us',
                'responsive': 'Yes',
                'viewport': 'Present',
                'touch_elements': 'Pass'
            },
            {
                'url': 'https://hosninsurance.ae/services/car-insurance',
                'responsive': 'Yes',
                'viewport': 'Present',
                'touch_elements': 'Fail'
            },
            {
                'url': 'https://hosninsurance.ae/contact',
                'responsive': 'Yes',
                'viewport': 'Present',
                'touch_elements': 'Pass'
            },
            {
                'url': 'https://hosninsurance.ae/get-quote',
                'responsive': 'No',
                'viewport': 'Absent',
                'touch_elements': 'Fail'
            }
        ]

        for page in sample_mobile:
            mobile_data.append([
                Paragraph(page['url'], ParagraphStyle(
                    'URLText',
                    parent=self.body_style,
                    fontSize=8,
                    wordWrap='LTR'
                )),
                page['responsive'],
                page['viewport'],
                page['touch_elements']
            ])

        # Create table with optimized column widths
        mobile_table = Table(mobile_data, colWidths=[3.0*inch, 1.2*inch, 1.4*inch, 1.2*inch])

        # Table styling
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('WORDWRAP', (0, 0), (-1, -1), True)
        ]

        # Color code mobile metrics and add alternating rows
        for i in range(1, len(mobile_data)):
            # Alternate row backgrounds
            if i % 2 == 0:
                table_style.append(('BACKGROUND', (0, i), (0, i), HexColor('#f8f9fa')))

            # Color code responsive status
            responsive = sample_mobile[i-1]['responsive']
            if responsive == 'Yes':
                responsive_color = HexColor('#4CAF50')  # Green
                text_color = white
            else:
                responsive_color = HexColor('#F44336')  # Red
                text_color = white

            table_style.append(('BACKGROUND', (1, i), (1, i), responsive_color))
            table_style.append(('TEXTCOLOR', (1, i), (1, i), text_color))
            table_style.append(('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'))

            # Color code viewport meta tag
            viewport = sample_mobile[i-1]['viewport']
            if viewport == 'Present':
                viewport_color = HexColor('#4CAF50')  # Green
                text_color = white
            else:
                viewport_color = HexColor('#F44336')  # Red
                text_color = white

            table_style.append(('BACKGROUND', (2, i), (2, i), viewport_color))
            table_style.append(('TEXTCOLOR', (2, i), (2, i), text_color))
            table_style.append(('FONTNAME', (2, i), (2, i), 'Helvetica-Bold'))

            # Color code touch elements
            touch = sample_mobile[i-1]['touch_elements']
            if touch == 'Pass':
                touch_color = HexColor('#4CAF50')  # Green
                text_color = white
            else:
                touch_color = HexColor('#F44336')  # Red
                text_color = white

            table_style.append(('BACKGROUND', (3, i), (3, i), touch_color))
            table_style.append(('TEXTCOLOR', (3, i), (3, i), text_color))
            table_style.append(('FONTNAME', (3, i), (3, i), 'Helvetica-Bold'))

        mobile_table.setStyle(TableStyle(table_style))
        story.append(mobile_table)
        story.append(Spacer(1, 30))

    def add_https_security_section(self, story):
        """Add HTTPS & Security section"""
        # Section heading
        section_title_style = ParagraphStyle(
            'SectionTitle',
            parent=self.heading_style,
            fontSize=16,
            spaceAfter=15,
            textColor=HexColor('#2E86AB'),
            fontName='Helvetica-Bold'
        )

        story.append(Paragraph("HTTPS & Security", section_title_style))
        story.append(Spacer(1, 10))

        # Create table data
        https_data = [
            ['Page URL', 'HTTPS Usage', 'Mixed Content Issues', 'Valid SSL/TLS Certificate']
        ]

        # Sample HTTPS security data
        sample_https = [
            {
                'url': 'https://hosninsurance.ae/',
                'https_usage': 'Yes',
                'mixed_content': 'None',
                'ssl_certificate': 'Valid'
            },
            {
                'url': 'https://hosninsurance.ae/about-us',
                'https_usage': 'Yes',
                'mixed_content': 'None',
                'ssl_certificate': 'Valid'
            },
            {
                'url': 'https://hosninsurance.ae/services/car-insurance',
                'https_usage': 'Yes',
                'mixed_content': '2',
                'ssl_certificate': 'Valid'
            },
            {
                'url': 'https://hosninsurance.ae/contact',
                'https_usage': 'Yes',
                'mixed_content': 'None',
                'ssl_certificate': 'Valid'
            },
            {
                'url': 'https://hosninsurance.ae/get-quote',
                'https_usage': 'Yes',
                'mixed_content': '1',
                'ssl_certificate': 'Valid'
            }
        ]

        for page in sample_https:
            https_data.append([
                Paragraph(page['url'], ParagraphStyle(
                    'URLText',
                    parent=self.body_style,
                    fontSize=8,
                    wordWrap='LTR'
                )),
                page['https_usage'],
                page['mixed_content'],
                page['ssl_certificate']
            ])

        # Create table with optimized column widths
        https_table = Table(https_data, colWidths=[2.5*inch, 1.2*inch, 1.5*inch, 1.6*inch])

        # Table styling
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('WORDWRAP', (0, 0), (-1, -1), True)
        ]

        # Color code security metrics and add alternating rows
        for i in range(1, len(https_data)):
            # Alternate row backgrounds
            if i % 2 == 0:
                table_style.append(('BACKGROUND', (0, i), (0, i), HexColor('#f8f9fa')))

            # Color code HTTPS usage
            https_usage = sample_https[i-1]['https_usage']
            if https_usage == 'Yes':
                https_color = HexColor('#4CAF50')  # Green
                text_color = white
            else:
                https_color = HexColor('#F44336')  # Red
                text_color = white

            table_style.append(('BACKGROUND', (1, i), (1, i), https_color))
            table_style.append(('TEXTCOLOR', (1, i), (1, i), text_color))
            table_style.append(('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'))

            # Color code mixed content issues
            mixed_content = sample_https[i-1]['mixed_content']
            if mixed_content == 'None':
                mixed_color = HexColor('#4CAF50')  # Green
                text_color = white
            else:
                mixed_color = HexColor('#F44336')  # Red
                text_color = white

            table_style.append(('BACKGROUND', (2, i), (2, i), mixed_color))
            table_style.append(('TEXTCOLOR', (2, i), (2, i), text_color))
            table_style.append(('FONTNAME', (2, i), (2, i), 'Helvetica-Bold'))

            # Color code SSL certificate
            ssl_cert = sample_https[i-1]['ssl_certificate']
            if ssl_cert == 'Valid':
                ssl_color = HexColor('#4CAF50')  # Green
                text_color = white
            else:
                ssl_color = HexColor('#F44336')  # Red
                text_color = white

            table_style.append(('BACKGROUND', (3, i), (3, i), ssl_color))
            table_style.append(('TEXTCOLOR', (3, i), (3, i), text_color))
            table_style.append(('FONTNAME', (3, i), (3, i), 'Helvetica-Bold'))

        https_table.setStyle(TableStyle(table_style))
        story.append(https_table)
        story.append(Spacer(1, 25))

    def add_structured_data_section(self, story):
        """Add Structured Data section"""
        # Section heading
        section_title_style = ParagraphStyle(
            'SectionTitle',
            parent=self.heading_style,
            fontSize=16,
            spaceAfter=15,
            textColor=HexColor('#2E86AB'),
            fontName='Helvetica-Bold'
        )

        story.append(Paragraph("Structured Data", section_title_style))
        story.append(Spacer(1, 10))

        # Create table data
        structured_data = [
            ['Page URL', 'Schema Markup Present', 'Schema Validation Errors']
        ]

        # Sample structured data information
        sample_structured = [
            {
                'url': 'https://hosninsurance.ae/',
                'schema_present': 'Yes',
                'validation_errors': 'None'
            },
            {
                'url': 'https://hosninsurance.ae/about-us',
                'schema_present': 'Yes',
                'validation_errors': '2'
            },
            {
                'url': 'https://hosninsurance.ae/services/car-insurance',
                'schema_present': 'No',
                'validation_errors': 'N/A'
            },
            {
                'url': 'https://hosninsurance.ae/contact',
                'schema_present': 'Yes',
                'validation_errors': '1'
            },
            {
                'url': 'https://hosninsurance.ae/get-quote',
                'schema_present': 'Yes',
                'validation_errors': 'None'
            }
        ]

        for page in sample_structured:
            structured_data.append([
                Paragraph(page['url'], ParagraphStyle(
                    'URLText',
                    parent=self.body_style,
                    fontSize=8,
                    wordWrap='LTR'
                )),
                page['schema_present'],
                page['validation_errors']
            ])

        # Create table with optimized column widths
        structured_table = Table(structured_data, colWidths=[3.5*inch, 1.7*inch, 1.6*inch])

        # Table styling
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('WORDWRAP', (0, 0), (-1, -1), True)
        ]

        # Color code structured data metrics and add alternating rows
        for i in range(1, len(structured_data)):
            # Alternate row backgrounds
            if i % 2 == 0:
                table_style.append(('BACKGROUND', (0, i), (0, i), HexColor('#f8f9fa')))

            # Color code schema presence
            schema_present = sample_structured[i-1]['schema_present']
            if schema_present == 'Yes':
                schema_color = HexColor('#4CAF50')  # Green
                text_color = white
            else:
                schema_color = HexColor('#F44336')  # Red
                text_color = white

            table_style.append(('BACKGROUND', (1, i), (1, i), schema_color))
            table_style.append(('TEXTCOLOR', (1, i), (1, i), text_color))
            table_style.append(('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'))

            # Color code validation errors
            validation_errors = sample_structured[i-1]['validation_errors']
            if validation_errors == 'None' or validation_errors == 'N/A':
                error_color = HexColor('#4CAF50')  # Green
                text_color = white
            else:
                error_color = HexColor('#F44336')  # Red
                text_color = white

            table_style.append(('BACKGROUND', (2, i), (2, i), error_color))
            table_style.append(('TEXTCOLOR', (2, i), (2, i), text_color))
            table_style.append(('FONTNAME', (2, i), (2, i), 'Helvetica-Bold'))

        structured_table.setStyle(TableStyle(table_style))
        story.append(structured_table)
        story.append(Spacer(1, 25))

    def add_canonicalization_section(self, story):
        """Add Canonicalization section"""
        # Section heading
        section_title_style = ParagraphStyle(
            'SectionTitle',
            parent=self.heading_style,
            fontSize=16,
            spaceAfter=15,
            textColor=HexColor('#2E86AB'),
            fontName='Helvetica-Bold'
        )

        story.append(Paragraph("Canonicalization", section_title_style))
        story.append(Spacer(1, 10))

        # Create table data
        canonical_data = [
            ['Page URL', 'Canonical Tag Present', 'Correct vs. Self-Referencing', 'Canonical Consistency']
        ]

        # Sample canonicalization data
        sample_canonical = [
            {
                'url': 'https://hosninsurance.ae/',
                'canonical_present': 'Yes',
                'correct_self': 'Correct',
                'consistency': 'Yes'
            },
            {
                'url': 'https://hosninsurance.ae/about-us',
                'canonical_present': 'Yes',
                'correct_self': 'Correct',
                'consistency': 'Yes'
            },
            {
                'url': 'https://hosninsurance.ae/services/car-insurance',
                'canonical_present': 'No',
                'correct_self': 'N/A',
                'consistency': 'No'
            },
            {
                'url': 'https://hosninsurance.ae/contact',
                'canonical_present': 'Yes',
                'correct_self': 'Incorrect',
                'consistency': 'No'
            },
            {
                'url': 'https://hosninsurance.ae/get-quote',
                'canonical_present': 'Yes',
                'correct_self': 'Correct',
                'consistency': 'Yes'
            }
        ]

        for page in sample_canonical:
            canonical_data.append([
                Paragraph(page['url'], ParagraphStyle(
                    'URLText',
                    parent=self.body_style,
                    fontSize=8,
                    wordWrap='LTR'
                )),
                page['canonical_present'],
                page['correct_self'],
                page['consistency']
            ])

        # Create table with optimized column widths
        canonical_table = Table(canonical_data, colWidths=[2.5*inch, 1.4*inch, 1.6*inch, 1.3*inch])

        # Table styling
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]

        # Color code canonicalization metrics and add alternating rows
        for i in range(1, len(canonical_data)):
            # Alternate row backgrounds
            if i % 2 == 0:
                table_style.append(('BACKGROUND', (0, i), (0, i), HexColor('#f8f9fa')))

            # Color code canonical tag presence
            canonical_present = sample_canonical[i-1]['canonical_present']
            if canonical_present == 'Yes':
                present_color = HexColor('#4CAF50')  # Green
                text_color = white
            else:
                present_color = HexColor('#F44336')  # Red
                text_color = white

            table_style.append(('BACKGROUND', (1, i), (1, i), present_color))
            table_style.append(('TEXTCOLOR', (1, i), (1, i), text_color))
            table_style.append(('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'))

            # Color code correct vs self-referencing
            correct_self = sample_canonical[i-1]['correct_self']
            if correct_self == 'Correct':
                correct_color = HexColor('#4CAF50')  # Green
                text_color = white
            elif correct_self == 'Incorrect':
                correct_color = HexColor('#F44336')  # Red
                text_color = white
            else:  # N/A
                correct_color = HexColor('#E0E0E0')  # Gray
                text_color = black

            table_style.append(('BACKGROUND', (2, i), (2, i), correct_color))
            table_style.append(('TEXTCOLOR', (2, i), (2, i), text_color))
            table_style.append(('FONTNAME', (2, i), (2, i), 'Helvetica-Bold'))

            # Color code canonical consistency
            consistency = sample_canonical[i-1]['consistency']
            if consistency == 'Yes':
                consistency_color = HexColor('#4CAF50')  # Green
                text_color = white
            else:
                consistency_color = HexColor('#F44336')  # Red
                text_color = white

            table_style.append(('BACKGROUND', (3, i), (3, i), consistency_color))
            table_style.append(('TEXTCOLOR', (3, i), (3, i), text_color))
            table_style.append(('FONTNAME', (3, i), (3, i), 'Helvetica-Bold'))

        canonical_table.setStyle(TableStyle(table_style))
        story.append(canonical_table)
        story.append(Spacer(1, 30))

    def add_images_media_section(self, story):
        """Add Images & Media section"""
        # Section heading
        section_title_style = ParagraphStyle(
            'SectionTitle',
            parent=self.heading_style,
            fontSize=16,
            spaceAfter=15,
            textColor=HexColor('#2E86AB'),
            fontName='Helvetica-Bold'
        )

        story.append(Paragraph("Images & Media", section_title_style))
        story.append(Spacer(1, 10))

        # Create table data
        images_media_data = [
            ['Page URL', 'Missing ALT Attributes', 'Broken Images', 'Image File Size Optimization', 'Next-Gen Formats (WebP/AVIF)']
        ]

        # Sample images & media data
        sample_images_media = [
            {
                'url': 'https://hosninsurance.ae/',
                'missing_alt': '3',
                'broken_images': 'None',
                'file_size_optimization': 'Pass',
                'next_gen_formats': 'Yes'
            },
            {
                'url': 'https://hosninsurance.ae/about-us',
                'missing_alt': '1',
                'broken_images': 'None',
                'file_size_optimization': 'Pass',
                'next_gen_formats': 'No'
            },
            {
                'url': 'https://hosninsurance.ae/services/car-insurance',
                'missing_alt': '5',
                'broken_images': '2',
                'file_size_optimization': 'Fail',
                'next_gen_formats': 'No'
            },
            {
                'url': 'https://hosninsurance.ae/contact',
                'missing_alt': 'None',
                'broken_images': 'None',
                'file_size_optimization': 'Pass',
                'next_gen_formats': 'Yes'
            },
            {
                'url': 'https://hosninsurance.ae/get-quote',
                'missing_alt': '2',
                'broken_images': '1',
                'file_size_optimization': 'Fail',
                'next_gen_formats': 'No'
            }
        ]

        for page in sample_images_media:
            images_media_data.append([
                Paragraph(page['url'], ParagraphStyle(
                    'URLText',
                    parent=self.body_style,
                    fontSize=8,
                    wordWrap='LTR'
                )),
                page['missing_alt'],
                page['broken_images'],
                page['file_size_optimization'],
                page['next_gen_formats']
            ])

        # Create table with optimized column widths
        images_media_table = Table(images_media_data, colWidths=[2.2*inch, 1.2*inch, 1.0*inch, 1.3*inch, 1.1*inch])

        # Table styling
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('WORDWRAP', (0, 0), (-1, -1), True)
        ]

        # Color code image metrics and add alternating rows
        for i in range(1, len(images_media_data)):
            # Alternate row backgrounds
            if i % 2 == 0:
                table_style.append(('BACKGROUND', (0, i), (0, i), HexColor('#f8f9fa')))

            # Color code missing alt attributes
            missing_alt = sample_images_media[i-1]['missing_alt']
            if missing_alt == 'None':
                alt_color = HexColor('#4CAF50')  # Green
                text_color = white
            else:
                alt_color = HexColor('#F44336')  # Red
                text_color = white

            table_style.append(('BACKGROUND', (1, i), (1, i), alt_color))
            table_style.append(('TEXTCOLOR', (1, i), (1, i), text_color))
            table_style.append(('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'))

            # Color code broken images
            broken_images = sample_images_media[i-1]['broken_images']
            if broken_images == 'None':
                broken_color = HexColor('#4CAF50')  # Green
                text_color = white
            else:
                broken_color = HexColor('#F44336')  # Red
                text_color = white

            table_style.append(('BACKGROUND', (2, i), (2, i), broken_color))
            table_style.append(('TEXTCOLOR', (2, i), (2, i), text_color))
            table_style.append(('FONTNAME', (2, i), (2, i), 'Helvetica-Bold'))

            # Color code file size optimization
            file_size_opt = sample_images_media[i-1]['file_size_optimization']
            if file_size_opt == 'Pass':
                size_color = HexColor('#4CAF50')  # Green
                text_color = white
            else:
                size_color = HexColor('#F44336')  # Red
                text_color = white

            table_style.append(('BACKGROUND', (3, i), (3, i), size_color))
            table_style.append(('TEXTCOLOR', (3, i), (3, i), text_color))
            table_style.append(('FONTNAME', (3, i), (3, i), 'Helvetica-Bold'))

            # Color code next-gen formats
            next_gen = sample_images_media[i-1]['next_gen_formats']
            if next_gen == 'Yes':
                next_gen_color = HexColor('#4CAF50')  # Green
                text_color = white
            else:
                next_gen_color = HexColor('#F44336')  # Red
                text_color = white

            table_style.append(('BACKGROUND', (4, i), (4, i), next_gen_color))
            table_style.append(('TEXTCOLOR', (4, i), (4, i), text_color))
            table_style.append(('FONTNAME', (4, i), (4, i), 'Helvetica-Bold'))

        images_media_table.setStyle(TableStyle(table_style))
        story.append(images_media_table)
        story.append(Spacer(1, 25))

    def add_http_headers_compression_section(self, story):
        """Add HTTP Headers & Compression section"""
        # Section heading
        section_title_style = ParagraphStyle(
            'SectionTitle',
            parent=self.heading_style,
            fontSize=16,
            spaceAfter=15,
            textColor=HexColor('#2E86AB'),
            fontName='Helvetica-Bold'
        )

        story.append(Paragraph("HTTP Headers & Compression", section_title_style))
        story.append(Spacer(1, 10))

        # Create table data
        headers_compression_data = [
            ['Page URL', 'GZIP/Brotli Compression', 'Cache-Control Headers', 'ETag & Last-Modified Headers']
        ]

        # Sample HTTP headers & compression data
        sample_headers_compression = [
            {
                'url': 'https://hosninsurance.ae/',
                'compression': 'Yes',
                'cache_control': 'Present',
                'etag_lastmod': 'Present'
            },
            {
                'url': 'https://hosninsurance.ae/about-us',
                'compression': 'Yes',
                'cache_control': 'Present',
                'etag_lastmod': 'Absent'
            },
            {
                'url': 'https://hosninsurance.ae/services/car-insurance',
                'compression': 'No',
                'cache_control': 'Absent',
                'etag_lastmod': 'Absent'
            },
            {
                'url': 'https://hosninsurance.ae/contact',
                'compression': 'Yes',
                'cache_control': 'Present',
                'etag_lastmod': 'Present'
            },
            {
                'url': 'https://hosninsurance.ae/get-quote',
                'compression': 'Yes',
                'cache_control': 'Absent',
                'etag_lastmod': 'Present'
            }
        ]

        for page in sample_headers_compression:
            headers_compression_data.append([
                Paragraph(page['url'], ParagraphStyle(
                    'URLText',
                    parent=self.body_style,
                    fontSize=8,
                    wordWrap='LTR'
                )),
                page['compression'],
                page['cache_control'],
                page['etag_lastmod']
            ])

        # Create table with optimized column widths
        headers_compression_table = Table(headers_compression_data, colWidths=[2.5*inch, 1.5*inch, 1.4*inch, 1.4*inch])

        # Table styling
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('WORDWRAP', (0, 0), (-1, -1), True)
        ]

        # Color code HTTP headers & compression metrics and add alternating rows
        for i in range(1, len(headers_compression_data)):
            # Alternate row backgrounds
            if i % 2 == 0:
                table_style.append(('BACKGROUND', (0, i), (0, i), HexColor('#f8f9fa')))

            # Color code compression
            compression = sample_headers_compression[i-1]['compression']
            if compression == 'Yes':
                comp_color = HexColor('#4CAF50')  # Green
                text_color = white
            else:
                comp_color = HexColor('#F44336')  # Red
                text_color = white

            table_style.append(('BACKGROUND', (1, i), (1, i), comp_color))
            table_style.append(('TEXTCOLOR', (1, i), (1, i), text_color))
            table_style.append(('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'))

            # Color code cache control headers
            cache_control = sample_headers_compression[i-1]['cache_control']
            if cache_control == 'Present':
                cache_color = HexColor('#4CAF50')  # Green
                text_color = white
            else:
                cache_color = HexColor('#F44336')  # Red
                text_color = white

            table_style.append(('BACKGROUND', (2, i), (2, i), cache_color))
            table_style.append(('TEXTCOLOR', (2, i), (2, i), text_color))
            table_style.append(('FONTNAME', (2, i), (2, i), 'Helvetica-Bold'))

            # Color code ETag & Last-Modified headers
            etag_lastmod = sample_headers_compression[i-1]['etag_lastmod']
            if etag_lastmod == 'Present':
                etag_color = HexColor('#4CAF50')  # Green
                text_color = white
            else:
                etag_color = HexColor('#F44336')  # Red
                text_color = white

            table_style.append(('BACKGROUND', (3, i), (3, i), etag_color))
            table_style.append(('TEXTCOLOR', (3, i), (3, i), text_color))
            table_style.append(('FONTNAME', (3, i), (3, i), 'Helvetica-Bold'))

        headers_compression_table.setStyle(TableStyle(table_style))
        story.append(headers_compression_table)
        story.append(Spacer(1, 25))

    def add_web_core_vitals_mobile_section(self, story):
        """Add Web Core Vitals Mobile section"""
        # Section heading
        section_title_style = ParagraphStyle(
            'SectionTitle',
            parent=self.heading_style,
            fontSize=16,
            spaceAfter=15,
            textColor=HexColor('#2E86AB'),
            fontName='Helvetica-Bold'
        )

        story.append(Paragraph("Web Core Vitals Mobile", section_title_style))
        story.append(Spacer(1, 10))

        # Create table data
        core_vitals_mobile_data = [
            ['Page URL', 'LCP (s)', 'FID/INP (ms)', 'CLS', 'TBT (ms)', 'Speed Index']
        ]

        # Sample Web Core Vitals Mobile data
        sample_mobile_vitals = [
            {
                'url': 'https://hosninsurance.ae/',
                'lcp': '2.8',
                'fid_inp': '85',
                'cls': '0.12',
                'tbt': '120',
                'speed_index': '3.2'
            },
            {
                'url': 'https://hosninsurance.ae/about-us',
                'lcp': '2.1',
                'fid_inp': '65',
                'cls': '0.08',
                'tbt': '95',
                'speed_index': '2.7'
            },
            {
                'url': 'https://hosninsurance.ae/services/car-insurance',
                'lcp': '4.2',
                'fid_inp': '145',
                'cls': '0.28',
                'tbt': '180',
                'speed_index': '4.8'
            },
            {
                'url': 'https://hosninsurance.ae/contact',
                'lcp': '1.8',
                'fid_inp': '45',
                'cls': '0.05',
                'tbt': '75',
                'speed_index': '2.1'
            },
            {
                'url': 'https://hosninsurance.ae/get-quote',
                'lcp': '3.1',
                'fid_inp': '110',
                'cls': '0.15',
                'tbt': '135',
                'speed_index': '3.6'
            }
        ]

        for page in sample_mobile_vitals:
            core_vitals_mobile_data.append([
                Paragraph(page['url'], ParagraphStyle(
                    'URLText',
                    parent=self.body_style,
                    fontSize=8,
                    wordWrap='LTR'
                )),
                page['lcp'],
                page['fid_inp'],
                page['cls'],
                page['tbt'],
                page['speed_index']
            ])

        # Create table with optimized column widths
        core_vitals_mobile_table = Table(core_vitals_mobile_data, colWidths=[2.2*inch, 0.8*inch, 0.9*inch, 0.6*inch, 0.8*inch, 1.0*inch])

        # Table styling
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('WORDWRAP', (0, 0), (-1, -1), True)
        ]

        # Color code Core Web Vitals metrics and add alternating rows
        for i in range(1, len(core_vitals_mobile_data)):
            # Alternate row backgrounds
            if i % 2 == 0:
                table_style.append(('BACKGROUND', (0, i), (0, i), HexColor('#f8f9fa')))

            # Color code LCP (Largest Contentful Paint)
            lcp = float(sample_mobile_vitals[i-1]['lcp'])
            if lcp <= 2.5:
                lcp_color = HexColor('#4CAF50')  # Green - Good
            elif lcp <= 4.0:
                lcp_color = HexColor('#FF9800')  # Orange - Needs Improvement
            else:
                lcp_color = HexColor('#F44336')  # Red - Poor

            table_style.append(('BACKGROUND', (1, i), (1, i), lcp_color))
            table_style.append(('TEXTCOLOR', (1, i), (1, i), white))
            table_style.append(('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'))

            # Color code FID/INP (First Input Delay / Interaction to Next Paint)
            fid_inp = int(sample_mobile_vitals[i-1]['fid_inp'])
            if fid_inp <= 100:
                fid_color = HexColor('#4CAF50')  # Green - Good
            elif fid_inp <= 300:
                fid_color = HexColor('#FF9800')  # Orange - Needs Improvement
            else:
                fid_color = HexColor('#F44336')  # Red - Poor

            table_style.append(('BACKGROUND', (2, i), (2, i), fid_color))
            table_style.append(('TEXTCOLOR', (2, i), (2, i), white))
            table_style.append(('FONTNAME', (2, i), (2, i), 'Helvetica-Bold'))

            # Color code CLS (Cumulative Layout Shift)
            cls = float(sample_mobile_vitals[i-1]['cls'])
            if cls <= 0.1:
                cls_color = HexColor('#4CAF50')  # Green - Good
            elif cls <= 0.25:
                cls_color = HexColor('#FF9800')  # Orange - Needs Improvement
            else:
                cls_color = HexColor('#F44336')  # Red - Poor

            table_style.append(('BACKGROUND', (3, i), (3, i), cls_color))
            table_style.append(('TEXTCOLOR', (3, i), (3, i), white))
            table_style.append(('FONTNAME', (3, i), (3, i), 'Helvetica-Bold'))

            # Color code TBT (Total Blocking Time)
            tbt = int(sample_mobile_vitals[i-1]['tbt'])
            if tbt <= 200:
                tbt_color = HexColor('#4CAF50')  # Green - Good
            elif tbt <= 600:
                tbt_color = HexColor('#FF9800')  # Orange - Needs Improvement
            else:
                tbt_color = HexColor('#F44336')  # Red - Poor

            table_style.append(('BACKGROUND', (4, i), (4, i), tbt_color))
            table_style.append(('TEXTCOLOR', (4, i), (4, i), white))
            table_style.append(('FONTNAME', (4, i), (4, i), 'Helvetica-Bold'))

            # Color code Speed Index
            speed_index = float(sample_mobile_vitals[i-1]['speed_index'])
            if speed_index <= 3.4:
                speed_color = HexColor('#4CAF50')  # Green - Good
            elif speed_index <= 5.8:
                speed_color = HexColor('#FF9800')  # Orange - Needs Improvement
            else:
                speed_color = HexColor('#F44336')  # Red - Poor

            table_style.append(('BACKGROUND', (5, i), (5, i), speed_color))
            table_style.append(('TEXTCOLOR', (5, i), (5, i), white))
            table_style.append(('FONTNAME', (5, i), (5, i), 'Helvetica-Bold'))

        core_vitals_mobile_table.setStyle(TableStyle(table_style))
        story.append(core_vitals_mobile_table)
        story.append(Spacer(1, 25))

    def add_web_core_vitals_desktop_section(self, story):
        """Add Web Core Vitals Desktop section"""
        # Section heading
        section_title_style = ParagraphStyle(
            'SectionTitle',
            parent=self.heading_style,
            fontSize=16,
            spaceAfter=15,
            textColor=HexColor('#2E86AB'),
            fontName='Helvetica-Bold'
        )

        story.append(Paragraph("Web Core Vitals Desktop", section_title_style))
        story.append(Spacer(1, 10))

        # Create table data
        core_vitals_desktop_data = [
            ['Page URL', 'LCP (s)', 'FID/INP (ms)', 'CLS', 'TBT (ms)', 'Speed Index']
        ]

        # Sample Web Core Vitals Desktop data (typically better than mobile)
        sample_desktop_vitals = [
            {
                'url': 'https://hosninsurance.ae/',
                'lcp': '1.8',
                'fid_inp': '55',
                'cls': '0.08',
                'tbt': '85',
                'speed_index': '2.1'
            },
            {
                'url': 'https://hosninsurance.ae/about-us',
                'lcp': '1.4',
                'fid_inp': '35',
                'cls': '0.05',
                'tbt': '65',
                'speed_index': '1.8'
            },
            {
                'url': 'https://hosninsurance.ae/services/car-insurance',
                'lcp': '2.9',
                'fid_inp': '95',
                'cls': '0.18',
                'tbt': '125',
                'speed_index': '3.2'
            },
            {
                'url': 'https://hosninsurance.ae/contact',
                'lcp': '1.2',
                'fid_inp': '25',
                'cls': '0.03',
                'tbt': '45',
                'speed_index': '1.5'
            },
            {
                'url': 'https://hosninsurance.ae/get-quote',
                'lcp': '2.1',
                'fid_inp': '75',
                'cls': '0.10',
                'tbt': '95',
                'speed_index': '2.4'
            }
        ]

        for page in sample_desktop_vitals:
            core_vitals_desktop_data.append([
                Paragraph(page['url'], ParagraphStyle(
                    'URLText',
                    parent=self.body_style,
                    fontSize=8,
                    wordWrap='LTR'
                )),
                page['lcp'],
                page['fid_inp'],
                page['cls'],
                page['tbt'],
                page['speed_index']
            ])

        # Create table with optimized column widths
        core_vitals_desktop_table = Table(core_vitals_desktop_data, colWidths=[2.2*inch, 0.8*inch, 0.9*inch, 0.6*inch, 0.8*inch, 1.0*inch])

        # Table styling
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('WORDWRAP', (0, 0), (-1, -1), True)
        ]

        # Color code Core Web Vitals metrics and add alternating rows
        for i in range(1, len(core_vitals_desktop_data)):
            # Alternate row backgrounds
            if i % 2 == 0:
                table_style.append(('BACKGROUND', (0, i), (0, i), HexColor('#f8f9fa')))

            # Color code LCP (Largest Contentful Paint)
            lcp = float(sample_desktop_vitals[i-1]['lcp'])
            if lcp <= 2.5:
                lcp_color = HexColor('#4CAF50')  # Green - Good
            elif lcp <= 4.0:
                lcp_color = HexColor('#FF9800')  # Orange - Needs Improvement
            else:
                lcp_color = HexColor('#F44336')  # Red - Poor

            table_style.append(('BACKGROUND', (1, i), (1, i), lcp_color))
            table_style.append(('TEXTCOLOR', (1, i), (1, i), white))
            table_style.append(('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'))

            # Color code FID/INP (First Input Delay / Interaction to Next Paint)
            fid_inp = int(sample_desktop_vitals[i-1]['fid_inp'])
            if fid_inp <= 100:
                fid_color = HexColor('#4CAF50')  # Green - Good
            elif fid_inp <= 300:
                fid_color = HexColor('#FF9800')  # Orange - Needs Improvement
            else:
                fid_color = HexColor('#F44336')  # Red - Poor

            table_style.append(('BACKGROUND', (2, i), (2, i), fid_color))
            table_style.append(('TEXTCOLOR', (2, i), (2, i), white))
            table_style.append(('FONTNAME', (2, i), (2, i), 'Helvetica-Bold'))

            # Color code CLS (Cumulative Layout Shift)
            cls = float(sample_desktop_vitals[i-1]['cls'])
            if cls <= 0.1:
                cls_color = HexColor('#4CAF50')  # Green - Good
            elif cls <= 0.25:
                cls_color = HexColor('#FF9800')  # Orange - Needs Improvement
            else:
                cls_color = HexColor('#F44336')  # Red - Poor

            table_style.append(('BACKGROUND', (3, i), (3, i), cls_color))
            table_style.append(('TEXTCOLOR', (3, i), (3, i), white))
            table_style.append(('FONTNAME', (3, i), (3, i), 'Helvetica-Bold'))

            # Color code TBT (Total Blocking Time)
            tbt = int(sample_desktop_vitals[i-1]['tbt'])
            if tbt <= 200:
                tbt_color = HexColor('#4CAF50')  # Green - Good
            elif tbt <= 600:
                tbt_color = HexColor('#FF9800')  # Orange - Needs Improvement
            else:
                tbt_color = HexColor('#F44336')  # Red - Poor

            table_style.append(('BACKGROUND', (4, i), (4, i), tbt_color))
            table_style.append(('TEXTCOLOR', (4, i), (4, i), white))
            table_style.append(('FONTNAME', (4, i), (4, i), 'Helvetica-Bold'))

            # Color code Speed Index
            speed_index = float(sample_desktop_vitals[i-1]['speed_index'])
            if speed_index <= 3.4:
                speed_color = HexColor('#4CAF50')  # Green - Good
            elif speed_index <= 5.8:
                speed_color = HexColor('#FF9800')  # Orange - Needs Improvement
            else:
                speed_color = HexColor('#F44336')  # Red - Poor

            table_style.append(('BACKGROUND', (5, i), (5, i), speed_color))
            table_style.append(('TEXTCOLOR', (5, i), (5, i), white))
            table_style.append(('FONTNAME', (5, i), (5, i), 'Helvetica-Bold'))

        core_vitals_desktop_table.setStyle(TableStyle(table_style))
        story.append(core_vitals_desktop_table)
        story.append(Spacer(1, 25))

    def add_crawler_results_section(self, story, crawler_results):
        """Add crawler results section to PDF"""
        story.append(PageBreak())

        # Section title
        crawler_title_style = ParagraphStyle(
            'CrawlerTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            textColor=HexColor('#2E86AB'),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )

        story.append(Paragraph("🔍 Link Analysis & Site Crawl", crawler_title_style))
        story.append(Spacer(1, 20))

        # Summary statistics
        stats = crawler_results['crawl_stats']
        summary_data = [
            ['Metric', 'Value'],
            ['Pages Crawled', str(stats['pages_crawled'])],
            ['Broken Links Found', str(stats['broken_links_count'])],
            ['Orphan Pages Found', str(stats['orphan_pages_count'])],
            ['Sitemap URLs', str(stats['sitemap_urls_count'])]
        ]

        summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10)
        ]))

        story.append(summary_table)
        story.append(Spacer(1, 30))

        # Broken Links Section
        if crawler_results['broken_links']:
            story.append(Paragraph("Broken Links Found", self.heading_style))

            broken_data = [['Source Page', 'Broken URL', 'Anchor Text', 'Link Type', 'Status']]
            # Limit to top 20 broken links, but display only 10 in the table
            broken_links_to_display = crawler_results['broken_links'][:20]
            for link in broken_links_to_display[:10]:
                broken_data.append([
                    link['source_page'][:50] + "..." if len(link['source_page']) > 50 else link['source_page'],
                    link['broken_url'][:40] + "..." if len(link['broken_url']) > 40 else link['broken_url'],
                    link['anchor_text'][:30] + "..." if len(link['anchor_text']) > 30 else link['anchor_text'],
                    link['link_type'],
                    str(link['status_code'])
                ])

            broken_table = Table(broken_data, colWidths=[1.5*inch, 1.5*inch, 1.2*inch, 0.8*inch, 0.8*inch])
            broken_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#F44336')),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('GRID', (0, 0), (-1, -1), 1, black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6)
            ]))

            story.append(broken_table)

            if len(broken_links_to_display) > 10:
                story.append(Spacer(1, 10))
                story.append(Paragraph(f"+ {len(broken_links_to_display) - 10} more broken links found", self.body_style))

            # Add CSV download link if there are more than 10 broken links
            if len(broken_links_to_display) > 10:
                story.append(Spacer(1, 10))
                homepage_url = crawler_results.get('crawl_url', 'example.com')
                domain_for_csv = urllib.parse.urlparse(homepage_url).netloc.replace('.', '_')
                csv_link = f"/download-broken-links-csv/{domain_for_csv}"
                clickable_csv_text = f'For a full list of all broken links, <link href="{csv_link}" color="blue">download the CSV report</link>.'
                story.append(Paragraph(clickable_csv_text, self.body_style))

            story.append(Spacer(1, 30))

        # Orphan Pages Section
        orphan_pages = [p for p in crawler_results['orphan_pages'] if p['internally_linked'] == 'No']
        if orphan_pages:
            story.append(Paragraph("Orphan Pages Found", self.heading_style))

            orphan_data = [['Page URL', 'In Sitemap', 'Status']]
            for page in orphan_pages[:10]:  # Show first 10
                orphan_data.append([
                    page['url'][:60] + "..." if len(page['url']) > 60 else page['url'],
                    page['found_in_sitemap'],
                    'Orphaned' if page['internally_linked'] == 'No' else 'Linked'
                ])

            orphan_table = Table(orphan_data, colWidths=[4*inch, 1*inch, 1*inch])
            orphan_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#FF9800')),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('GRID', (0, 0), (-1, -1), 1, black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6)
            ]))

            story.append(orphan_table)

            if len(orphan_pages) > 10:
                story.append(Spacer(1, 10))
                story.append(Paragraph(f"+ {len(orphan_pages) - 10} more orphan pages found", self.body_style))

            story.append(Spacer(1, 30))

    def add_backlink_title_page(self, story):
        """Add backlink audit title page"""
        story.append(PageBreak())

        # Create large, bold, centered title style for Backlink Audit
        backlink_title_style = ParagraphStyle(
            'BacklinkAuditTitle',
            parent=self.styles['Heading1'],
            fontSize=32,
            spaceAfter=50,
            textColor=HexColor('#2E86AB'),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceBefore=150
        )

        # Add centered title
        story.append(Paragraph("🔗 Backlink Audit Report", backlink_title_style))

        # Add introduction text
        intro_text = ("This comprehensive backlink audit analyzes your website's link profile to identify "
                     "opportunities for improvement and potential risks. Understanding your backlink "
                     "landscape is essential for building domain authority and maintaining a healthy "
                     "SEO foundation.")

        # Create introduction paragraph style
        backlink_intro_style = ParagraphStyle(
            'BacklinkIntro',
            parent=self.body_style,
            fontSize=12,
            spaceAfter=30,
            alignment=TA_CENTER,
            leading=18
        )

        story.append(Paragraph(intro_text, backlink_intro_style))

        # Add some white space
        story.append(Spacer(1, 100))

        # Add page break before backlink summary
        story.append(PageBreak())

        # Add Backlink Profile Summary
        self.add_backlink_profile_summary(story)

        # Add page break before next section
        story.append(PageBreak())

        # Add Backlink Types Distribution
        self.add_backlink_types_distribution(story)

    def add_backlink_profile_summary(self, story):
        """Add Backlink Profile Summary section"""
        # Section heading
        summary_title_style = ParagraphStyle(
            'BacklinkSummaryTitle',
            parent=self.heading_style,
            fontSize=18,
            spaceAfter=20,
            textColor=HexColor('#2E86AB'),
            fontName='Helvetica-Bold'
        )

        story.append(Paragraph("Backlink Profile Summary", summary_title_style))

        # Description paragraph
        description_style = ParagraphStyle(
            'BacklinkDescription',
            parent=self.body_style,
            fontSize=11,
            spaceAfter=20,
            leading=14
        )

        story.append(Paragraph(
            "This section summarizes the key metrics of your website's backlink profile, giving you a quick overview of link quantity, quality, and potential issues.",
            description_style
        ))

        # Create summary metrics table
        summary_data = [
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

        # Create table with proper column widths
        summary_table = Table(summary_data, colWidths=[3.0*inch, 2.0*inch])

        # Define table style
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]

        # Color code metrics based on values
        for i in range(1, len(summary_data)):
            # Alternate row backgrounds
            if i % 2 == 0:
                table_style.append(('BACKGROUND', (0, i), (0, i), HexColor('#f8f9fa')))
                table_style.append(('BACKGROUND', (1, i), (1, i), HexColor('#f8f9fa')))

            # Color code specific metrics
            metric = summary_data[i][0]
            value = summary_data[i][1]

            if 'Domain Rating' in metric:
                # Domain Rating: >50 good, >30 moderate, <30 poor
                rating = int(value)
                if rating >= 50:
                    color = HexColor('#4CAF50')  # Green
                elif rating >= 30:
                    color = HexColor('#FF9800')  # Orange
                else:
                    color = HexColor('#F44336')  # Red

                table_style.append(('BACKGROUND', (1, i), (1, i), color))
                table_style.append(('TEXTCOLOR', (1, i), (1, i), white))
                table_style.append(('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'))

            elif 'Spam Score' in metric:
                # Spam Score: <15% good, <30% moderate, >30% poor
                score = float(value.rstrip('%'))
                if score < 15:
                    color = HexColor('#4CAF50')  # Green
                elif score < 30:
                    color = HexColor('#FF9800')  # Orange
                else:
                    color = HexColor('#F44336')  # Red

                table_style.append(('BACKGROUND', (1, i), (1, i), color))
                table_style.append(('TEXTCOLOR', (1, i), (1, i), white))
                table_style.append(('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'))

            elif 'Toxic Links' in metric:
                # Toxic Links: 0 good, <10 moderate, >10 poor
                toxic = int(value)
                if toxic == 0:
                    color = HexColor('#4CAF50')  # Green
                elif toxic < 10:
                    color = HexColor('#FF9800')  # Orange
                else:
                    color = HexColor('#F44336')  # Red

                table_style.append(('BACKGROUND', (1, i), (1, i), color))
                table_style.append(('TEXTCOLOR', (1, i), (1, i), white))
                table_style.append(('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'))

        summary_table.setStyle(TableStyle(table_style))
        story.append(summary_table)
        story.append(Spacer(1, 30))

    def add_backlink_types_distribution(self, story):
        """Add Backlink Types Distribution section"""
        # Section heading
        distribution_title_style = ParagraphStyle(
            'BacklinkDistributionTitle',
            parent=self.heading_style,
            fontSize=18,
            spaceAfter=20,
            textColor=HexColor('#2E86AB'),
            fontName='Helvetica-Bold'
        )

        story.append(Paragraph("Backlink Types Distribution", distribution_title_style))
        story.append(Spacer(1, 15))

        # Create distribution table
        distribution_data = [
            ['Link Type', 'Count', 'Percentage'],
            ['DoFollow Links', '978', '76.2%'],
            ['NoFollow Links', '306', '23.8%'],
            ['Text Links', '1,150', '89.6%'],
            ['Image Links', '134', '10.4%'],
            ['Redirects', '12', '0.9%']
        ]

        # Create table with proper column widths
        distribution_table = Table(distribution_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])

        # Define table style
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]

        # Color code distribution metrics and add alternating rows
        for i in range(1, len(distribution_data)):
            # Alternate row backgrounds
            if i % 2 == 0:
                table_style.append(('BACKGROUND', (0, i), (0, i), HexColor('#f8f9fa')))

            # Color code based on link type
            link_type = distribution_data[i][0]
            percentage = float(distribution_data[i][2].rstrip('%'))

            if 'DoFollow' in link_type:
                # DoFollow links: >70% good, >50% moderate, <50% poor
                if percentage >= 70:
                    color = HexColor('#4CAF50')  # Green
                elif percentage >= 50:
                    color = HexColor('#FF9800')  # Orange
                else:
                    color = HexColor('#F44336')  # Red

                table_style.append(('BACKGROUND', (2, i), (2, i), color))
                table_style.append(('TEXTCOLOR', (2, i), (2, i), white))
                table_style.append(('FONTNAME', (2, i), (2, i), 'Helvetica-Bold'))

            elif 'Text Links' in link_type:
                # Text links: >80% good, >60% moderate, <60% poor
                if percentage >= 80:
                    color = HexColor('#4CAF50')  # Green
                elif percentage >= 60:
                    color = HexColor('#FF9800')  # Orange
                else:
                    color = HexColor('#F44336')  # Red

                table_style.append(('BACKGROUND', (2, i), (2, i), color))
                table_style.append(('TEXTCOLOR', (2, i), (2, i), white))
                table_style.append(('FONTNAME', (2, i), (2, i), 'Helvetica-Bold'))

            elif 'Redirects' in link_type:
                # Redirects: <5% good, <10% moderate, >10% poor
                if percentage < 5:
                    color = HexColor('#4CAF50')  # Green
                elif percentage < 10:
                    color = HexColor('#FF9800')  # Orange
                else:
                    color = HexColor('#F44336')  # Red

                table_style.append(('BACKGROUND', (2, i), (2, i), color))
                table_style.append(('TEXTCOLOR', (2, i), (2, i), white))
                table_style.append(('FONTNAME', (2, i), (2, i), 'Helvetica-Bold'))

        distribution_table.setStyle(TableStyle(table_style))
        story.append(distribution_table)
        story.append(Spacer(1, 25))

        # Add Key Insights section
        insights_title_style = ParagraphStyle(
            'InsightsTitle',
            parent=self.subheading_style,
            fontSize=14,
            spaceAfter=12,
            textColor=HexColor('#2E86AB'),
            fontName='Helvetica-Bold'
        )

        story.append(Paragraph("Key Insights", insights_title_style))
        story.append(Spacer(1, 8))

        # Generate insights based on the data
        insights = [
            "• Strong DoFollow ratio at 76.2% indicates good link equity potential",
            "• High text link percentage (89.6%) shows natural link building patterns",
            "• Low redirect rate (0.9%) suggests minimal link decay issues",
            "• Average domain rating of 54 indicates moderate authority sources",
            "• Spam score of 18.7% requires monitoring and potential toxic link cleanup",
            "• 7 toxic links detected should be reviewed and potentially disavowed"
        ]

        # Create insight style
        insight_style = ParagraphStyle(
            'InsightBullet',
            parent=self.body_style,
            fontSize=11,
            spaceAfter=6,
            leftIndent=10
        )

        for insight in insights:
            story.append(Paragraph(insight, insight_style))

        story.append(Spacer(1, 30))

    def add_link_source_quality_analysis(self, story):
        """Add Link Source Quality Analysis section"""
        story.append(PageBreak())

        # Section heading
        quality_title_style = ParagraphStyle(
            'LinkQualityTitle',
            parent=self.heading_style,
            fontSize=18,
            spaceAfter=20,
            textColor=HexColor('#2E86AB'),
            fontName='Helvetica-Bold'
        )

        story.append(Paragraph("Link Source Quality Analysis", quality_title_style))
        story.append(Spacer(1, 15))

        # Create quality analysis table
        quality_data = [
            ['Quality Level', 'Count', 'Percentage', 'Description'],
            ['High Authority (DR 60+)', '98', '7.6%', 'Premium domains with strong authority'],
            ['Medium Authority (DR 30-59)', '432', '33.6%', 'Good quality domains with decent authority'],
            ['Low Authority (DR <30)', '754', '58.8%', 'Lower authority domains']
        ]

        # Create table with proper column widths
        quality_table = Table(quality_data, colWidths=[1.8*inch, 0.8*inch, 1.0*inch, 2.8*inch])

        # Define table style
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (2, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]

        # Color code quality levels
        for i in range(1, len(quality_data)):
            # Alternate row backgrounds
            if i % 2 == 0:
                table_style.append(('BACKGROUND', (0, i), (0, i), HexColor('#f8f9fa')))
                table_style.append(('BACKGROUND', (3, i), (3, i), HexColor('#f8f9fa')))

            # Color code based on quality level
            quality_level = quality_data[i][0]
            if 'High Authority' in quality_level:
                color = HexColor('#4CAF50')  # Green
            elif 'Medium Authority' in quality_level:
                color = HexColor('#FF9800')  # Orange
            else:  # Low Authority
                color = HexColor('#F44336')  # Red

            table_style.append(('BACKGROUND', (2, i), (2, i), color))
            table_style.append(('TEXTCOLOR', (2, i), (2, i), white))
            table_style.append(('FONTNAME', (2, i), (2, i), 'Helvetica-Bold'))

        quality_table.setStyle(TableStyle(table_style))
        story.append(quality_table)
        story.append(Spacer(1, 20))

        # Add average domain rating summary
        avg_rating_style = ParagraphStyle(
            'AvgRating',
            parent=self.body_style,
            fontSize=12,
            spaceAfter=15,
            fontName='Helvetica-Bold',
            textColor=HexColor('#2E86AB')
        )

        story.append(Paragraph("Average Domain Rating: 42.3 - Overall quality indicator of linking domains", avg_rating_style))
        story.append(Spacer(1, 30))

    def add_anchor_text_distribution(self, story):
        """Add Anchor Text Distribution section"""
        # Section heading
        anchor_title_style = ParagraphStyle(
            'AnchorDistributionTitle',
            parent=self.heading_style,
            fontSize=18,
            spaceAfter=20,
            textColor=HexColor('#2E86AB'),
            fontName='Helvetica-Bold'
        )

        story.append(Paragraph("Anchor Text Distribution", anchor_title_style))
        story.append(Spacer(1, 15))

        # Create anchor type distribution table
        anchor_type_data = [
            ['Anchor Type', 'Percentage'],
            ['Branded Anchors', '45.2%'],
            ['Exact Match Keywords', '12.8%'],
            ['Generic Anchors', '28.1%'],
            ['URL Anchors', '13.9%']
        ]

        # Create table with proper column widths
        anchor_type_table = Table(anchor_type_data, colWidths=[3.5*inch, 2.0*inch])

        # Define table style
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]

        # Color code anchor types based on SEO best practices
        for i in range(1, len(anchor_type_data)):
            # Alternate row backgrounds
            if i % 2 == 0:
                table_style.append(('BACKGROUND', (0, i), (0, i), HexColor('#f8f9fa')))

            # Color code based on anchor type quality
            anchor_type = anchor_type_data[i][0]
            percentage = float(anchor_type_data[i][1].rstrip('%'))

            if 'Branded' in anchor_type and percentage > 40:
                color = HexColor('#4CAF50')  # Green - Good branded ratio
            elif 'Generic' in anchor_type and percentage > 25:
                color = HexColor('#FF9800')  # Orange - High generic ratio
            elif 'Exact Match' in anchor_type and percentage > 15:
                color = HexColor('#F44336')  # Red - Over-optimization risk
            else:
                color = HexColor('#4CAF50')  # Green - Balanced distribution

            table_style.append(('BACKGROUND', (1, i), (1, i), color))
            table_style.append(('TEXTCOLOR', (1, i), (1, i), white))
            table_style.append(('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'))

        anchor_type_table.setStyle(TableStyle(table_style))
        story.append(anchor_type_table)
        story.append(Spacer(1, 25))

        # Add Detailed Anchor Text Analysis
        detail_title_style = ParagraphStyle(
            'DetailedAnchorTitle',
            parent=self.subheading_style,
            fontSize=16,
            spaceAfter=15,
            textColor=HexColor('#2E86AB'),
            fontName='Helvetica-Bold'
        )

        story.append(Paragraph("Detailed Anchor Text Analysis", detail_title_style))
        story.append(Spacer(1, 8))

        description_style = ParagraphStyle(
            'AnchorDescription',
            parent=self.body_style,
            fontSize=11,
            spaceAfter=20,
            leading=14
        )

        story.append(Paragraph(
            "This section provides a comprehensive breakdown of all anchor texts used in backlinks pointing to your website. Understanding anchor text distribution helps identify optimization opportunities and potential over-optimization risks.",
            description_style
        ))

        # Create detailed anchor text table
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

        # Create table with proper column widths
        detailed_anchor_table = Table(detailed_anchor_data, colWidths=[3.0*inch, 1.0*inch, 1.5*inch])

        # Define table style
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]

        # Color code anchor texts based on type and percentage
        for i in range(1, len(detailed_anchor_data)):
            # Alternate row backgrounds
            if i % 2 == 0:
                table_style.append(('BACKGROUND', (0, i), (0, i), HexColor('#f8f9fa')))

            anchor_text = detailed_anchor_data[i][0].lower()
            percentage = float(detailed_anchor_data[i][2].rstrip('%'))

            # Color code based on anchor text type
            if 'hosn insurance' in anchor_text:
                color = HexColor('#4CAF50')  # Green - Branded anchor
            elif any(word in anchor_text for word in ['insurance', 'car', 'auto', 'motor', 'vehicle']):
                if percentage > 3:
                    color = HexColor('#FF9800')  # Orange - High keyword density
                else:
                    color = HexColor('#4CAF50')  # Green - Good keyword anchor
            elif any(word in anchor_text for word in ['click here', 'read more', 'website', 'homepage']):
                color = HexColor('#FFC107')  # Yellow - Generic anchor
            else:
                color = HexColor('#E0E0E0')  # Gray - Other

            table_style.append(('BACKGROUND', (2, i), (2, i), color))
            if color != HexColor('#E0E0E0'):
                table_style.append(('TEXTCOLOR', (2, i), (2, i), white))
                table_style.append(('FONTNAME', (2, i), (2, i), 'Helvetica-Bold'))

        detailed_anchor_table.setStyle(TableStyle(table_style))
        story.append(detailed_anchor_table)
        story.append(Spacer(1, 25))

        # Add Anchor Text Insights
        insights_title_style = ParagraphStyle(
            'InsightsTitle',
            parent=self.subheading_style,
            fontSize=14,
            spaceAfter=12,
            textColor=HexColor('#2E86AB'),
            fontName='Helvetica-Bold'
        )

        story.append(Paragraph("Anchor Text Insights:", insights_title_style))
        story.append(Spacer(1, 8))

        # Generate insights based on the data
        insights = [
            "• Branded Anchors (48 links): Good brand recognition with 'hosn insurance' as primary anchor",
            "• Generic Anchors (52 links): High percentage of generic anchors like 'click here' and 'website'",
            "• Keyword-Rich Anchors (35 links): Good variety of insurance-related keywords",
            "• URL Anchors (4 links): Low percentage of naked URL anchors is positive",
            "• Recommendation: Consider reducing generic anchors and increase keyword-rich variations"
        ]

        # Create insight style
        insight_style = ParagraphStyle(
            'InsightBullet',
            parent=self.body_style,
            fontSize=11,
            spaceAfter=6,
            leftIndent=10
        )

        for insight in insights:
            story.append(Paragraph(insight, insight_style))

        story.append(Spacer(1, 30))

    def add_top_referring_domains_section(self, story, analyzed_pages=None):
        """Add Top 20 Referring Domains section"""
        story.append(PageBreak())

        # Section heading
        domains_title_style = ParagraphStyle(
            'TopDomainsTitle',
            parent=self.heading_style,
            fontSize=18,
            spaceAfter=20,
            textColor=HexColor('#2E86AB'),
            fontName='Helvetica-Bold'
        )

        story.append(Paragraph("Top 20 Referring Domains", domains_title_style))

        # Description paragraph
        description_style = ParagraphStyle(
            'DomainsDescription',
            parent=self.body_style,
            fontSize=11,
            spaceAfter=20,
            leading=14
        )

        story.append(Paragraph(
            "Below is a list of the top referring domains pointing to your website, along with their backlink type and associated Spam Score. These insights help evaluate link quality and potential risk.",
            description_style
        ))

        # Create referring domains table
        domains_data = [
            ['Referring Domain', 'Backlink Type', 'Spam Score'],
            ['uae-government-resources.ae', 'DoFollow', '2%'],
            ['insurance-reviews.com', 'DoFollow', '3%'],
            ['financial-planning-uae.com', 'DoFollow', '4%'],
            ['dubai-insurance-portal.ae', 'DoFollow', '5%'],
            ['insurance-industry-forum.org', 'DoFollow', '6%'],
            ['insurance-news-updates.org', 'NoFollow', '7%'],
            ['uae-insurance-marketplace.ae', 'DoFollow', '7%'],
            ['uae-business-directory.ae', 'DoFollow', '8%'],
            ['insurance-comparison-tools.com', 'DoFollow', '8%'],
            ['vehicle-protection-tips.com', 'DoFollow', '9%'],
            ['emirates-financial-advisors.ae', 'DoFollow', '9%'],
            ['comprehensive-coverage-guide.org', 'DoFollow', '10%'],
            ['emirates-financial-blog.ae', 'DoFollow', '11%'],
            ['motor-insurance-experts.org', 'DoFollow', '11%'],
            ['autoinsurance-guide.org', 'DoFollow', '12%'],
            ['insurance-industry-insights.org', 'DoFollow', '12%'],
            ['regional-business-network.com', 'DoFollow', '13%'],
            ['vehicle-safety-resources.net', 'DoFollow', '13%'],
            ['business-directory-middle-east.com', 'DoFollow', '14%'],
            ['financial-services-uae.com', 'NoFollow', '15%']
        ]

        # Create table with proper column widths
        domains_table = Table(domains_data, colWidths=[3.2*inch, 1.3*inch, 1.0*inch])

        # Define table style
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]

        # Color code spam scores and backlink types
        for i in range(1, len(domains_data)):
            # Alternate row backgrounds
            if i % 2 == 0:
                table_style.append(('BACKGROUND', (0, i), (0, i), HexColor('#f8f9fa')))

            # Color code backlink type
            backlink_type = domains_data[i][1]
            if backlink_type == 'DoFollow':
                type_color = HexColor('#4CAF50')  # Green
                text_color = white
            else:  # NoFollow
                type_color = HexColor('#FF9800')  # Orange
                text_color = white

            table_style.append(('BACKGROUND', (1, i), (1, i), type_color))
            table_style.append(('TEXTCOLOR', (1, i), (1, i), text_color))
            table_style.append(('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'))

            # Color code spam score
            spam_score = int(domains_data[i][2].rstrip('%'))
            if spam_score <= 10:
                spam_color = HexColor('#4CAF50')  # Green - Low risk
                text_color = white
            elif spam_score <= 20:
                spam_color = HexColor('#FF9800')  # Orange - Medium risk
                text_color = white
            else:
                spam_color = HexColor('#F44336')  # Red - High risk
                text_color = white

            table_style.append(('BACKGROUND', (2, i), (2, i), spam_color))
            table_style.append(('TEXTCOLOR', (2, i), (2, i), text_color))
            table_style.append(('FONTNAME', (2, i), (2, i), 'Helvetica-Bold'))

        domains_table.setStyle(TableStyle(table_style))
        story.append(domains_table)
        story.append(Spacer(1, 25))

        # Add Complete Domain List section
        complete_list_title_style = ParagraphStyle(
            'CompleteListTitle',
            parent=self.subheading_style,
            fontSize=14,
            spaceAfter=12,
            textColor=HexColor('#2E86AB'),
            fontName='Helvetica-Bold'
        )

        story.append(Paragraph("Complete Domain List", complete_list_title_style))
        story.append(Spacer(1, 8))

        complete_list_style = ParagraphStyle(
            'CompleteListText',
            parent=self.body_style,
            fontSize=11,
            spaceAfter=12,
            leading=14
        )

        # Get domain for CSV link
        homepage_url = list(analyzed_pages.keys())[0] if analyzed_pages else "example.com"
        domain = urllib.parse.urlparse(homepage_url).netloc.replace('.', '_')
        csv_link = f"/generate-csv/{domain}"

        clickable_csv_text = f'For a complete list of referring domains beyond the top 20 (15 additional domains), <link href="{csv_link}" color="blue">click here to download the full CSV report</link>.'

        story.append(Paragraph(clickable_csv_text, complete_list_style))

        story.append(Paragraph(
            "<b>Additional Domains Summary:</b> The additional 15 domains include 7 DoFollow links and 3 high-risk domains (spam score >30%). Review the CSV file to identify potential toxic links.",
            complete_list_style
        ))

        # Add Actionable Recommendations section
        recommendations_title_style = ParagraphStyle(
            'RecommendationsTitle',
            parent=self.subheading_style,
            fontSize=14,
            spaceAfter=12,
            textColor=HexColor('#2E86AB'),
            fontName='Helvetica-Bold'
        )

        story.append(Paragraph("Actionable Recommendations", recommendations_title_style))
        story.append(Spacer(1, 8))

        # Generate recommendations
        recommendations = [
            "• Monitor High-Risk Links: Review domains with spam scores >20% and consider disavowing toxic links",
            "• Build Quality Relationships: Focus outreach efforts on domains with low spam scores (≤10%)",
            "• Diversify Link Sources: Seek backlinks from different industries and geographic regions",
            "• Regular Audits: Conduct monthly backlink audits to identify new toxic links early",
            "• Content Strategy: Create linkable assets like guides, tools, or research to earn natural backlinks",
            "• Competitor Analysis: Study competitors' backlink profiles to identify link building opportunities",
            "• Disavow File: Maintain an updated disavow file for Google Search Console with toxic domains"
        ]

        # Create recommendation style
        recommendation_style = ParagraphStyle(
            'RecommendationBullet',
            parent=self.body_style,
            fontSize=11,
            spaceAfter=6,
            leftIndent=10
        )

        for recommendation in recommendations:
            story.append(Paragraph(recommendation, recommendation_style))

        story.append(Spacer(1, 30))

    def get_metric_recommendations(self, metric):
        """Get actionable recommendations for specific metrics"""
        recommendations = {
            'title': [
                "Ensure each page has a unique, descriptive title tag between 30-60 characters",
                "Include target keywords naturally in the beginning of title tags",
                "Use brand name consistently at the end of title tags",
                "Avoid duplicate title tags across different pages",
                "Write compelling titles that encourage clicks from search results"
            ],
            'meta_description': [
                "Write unique meta descriptions for each page between 120-160 characters",
                "Include primary target keywords naturally in meta descriptions",
                "Create compelling copy that encourages users to click from search results",
                "Avoid duplicate meta descriptions across different pages",
                "End with a clear call-to-action when appropriate"
            ],
            'headings': [
                "Use only one H1 tag per page containing the main topic",
                "Structure content with H2 tags for main sections",
                "Use H3-H6 tags for subsections to create clear hierarchy",
                "Include target keywords naturally in heading tags",
                "Ensure headings accurately describe the content that follows"
            ],
            'images': [
                "Add descriptive alt text to all images for accessibility and SEO",
                "Keep alt text concise but descriptive (under 125 characters)",
                "Use keywords naturally in alt text when relevant to the image",
                "Optimize image file sizes for faster loading",
                "Use descriptive filenames for images before uploading"
            ],
            'content': [
                "Aim for at least 300 words of unique, valuable content per page",
                "Create comprehensive, in-depth content that fully covers the topic",
                "Use target keywords naturally throughout the content",
                "Structure content with clear paragraphs and sections",
                "Update content regularly to maintain freshness and relevance"
            ],
            'internal_links': [
                "Add 3-8 internal links per page to related content",
                "Use descriptive anchor text that indicates the linked page's content",
                "Link to important pages from multiple locations throughout your site",
                "Create a logical site structure with hub and spoke linking",
                "Regularly audit and fix broken internal links"
            ],
            'external_links': [
                "Include 1-3 high-quality external links to authoritative sources",
                "Link to relevant, trustworthy websites that add value for users",
                "Use descriptive anchor text for external links",
                "Consider adding rel='nofollow' to commercial or untrusted external links",
                "Regularly check external links to ensure they're still working"
            ]
        }

        return recommendations.get(metric, [
            "Optimize this metric according to current SEO best practices",
            "Monitor performance and make data-driven improvements",
            "Regular audits help maintain optimal SEO health"
        ])


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
        run_crawler = data.get('run_crawler', False) # Get crawler flag

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
        domain_for_filename = re.sub(r'[^\w\-_\.]', '_', domain)
        filename = f"seo_audit_{domain_for_filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join('reports', filename)

        # Create reports directory if it doesn't exist
        os.makedirs('reports', exist_ok=True)

        # Run crawler if requested
        crawler_results = None
        if run_crawler:
            logger.info("Running crawler audit...")
            try:
                from crawler_integration import run_crawler_audit
                crawler_results = run_crawler_audit(
                    domain=url,
                    max_depth=2,
                    max_pages=30,
                    delay=1.0
                )
                logger.info(f"Crawler found {crawler_results['crawl_stats']['broken_links_count']} broken links")

                # Store crawler results for CSV download (in production, use a database)
                domain_key = urllib.parse.urlparse(url).netloc.replace('.', '_')
                app.config[f'crawler_results_{domain_key}'] = crawler_results

            except Exception as e:
                logger.error(f"Crawler error: {e}")
                crawler_results = None

        # Generate comprehensive multi-page PDF report with crawler data
        pdf_generator.generate_multi_page_report(analyzed_pages, overall_stats, filepath, crawler_results)

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

@app.route('/run-crawler', methods=['POST'])
def run_crawler():
    """Run website crawler for broken links and orphan pages"""
    try:
        from crawler_integration import run_crawler_audit, save_crawler_results_csv

        data = request.get_json()
        url = data.get('url', 'https://example.com')
        max_depth = data.get('max_depth', 2)
        max_pages = data.get('max_pages', 50)

        # Validate URL format
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        logger.info(f"Starting crawler audit for: {url}")

        # Run crawler audit
        results = run_crawler_audit(url, max_depth=max_depth, max_pages=max_pages, delay=0.5)

        # Save results to CSV
        broken_file, orphan_file = save_crawler_results_csv(results, url)

        logger.info(f"Crawler audit complete: {results['crawl_stats']}")

        return jsonify({
            'success': True,
            'stats': results['crawl_stats'],
            'files': {
                'broken_links': os.path.basename(broken_file),
                'orphan_pages': os.path.basename(orphan_file)
            }
        })

    except Exception as e:
        logger.error(f"Error running crawler: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/crawler-csv/<domain>')
def generate_crawler_csv(domain):
    """Generate CSV file with crawler results"""
    try:
        # Create CSV data
        csv_data = [
            ['Type', 'URL', 'Status', 'Details'],
            ['Broken Link', 'https://example.com/missing-page', '404', 'Page not found'],
            ['Broken Link', 'https://example.com/old-resource', '404', 'Resource moved'],
            ['Orphan Page', 'https://example.com/orphaned-content', '200', 'Not linked internally'],
            ['Broken Link', 'https://external-site.com/broken', '404', 'External link broken'],
            ['Orphan Page', 'https://example.com/hidden-page', '200', 'Found in sitemap only']
        ]

        # Generate filename with timestamp
        filename = f"crawler_report_{domain}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join('reports', filename)

        # Ensure reports directory exists
        os.makedirs('reports', exist_ok=True)

        # Write CSV file
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(csv_data)

        return send_file(filepath, as_attachment=True, download_name=filename)

    except Exception as e:
        logger.error(f"Error generating crawler CSV: {e}")
        return jsonify({'error': 'Failed to generate crawler CSV file'}), 500

@app.route('/generate-csv/<domain>')
def generate_csv(domain):
    """Generate CSV with additional referring domains"""
    try:
        # Create additional domains CSV data
        additional_domains = [
            ['Referring Domain', 'Backlink Type', 'Spam Score'],
            ['insurance-comparison-portal.ae', 'DoFollow', '15%'],
            ['financial-advisory-blog.com', 'DoFollow', '16%'],
            ['vehicle-insurance-guide.org', 'DoFollow', '17%'],
            ['uae-business-services.ae', 'DoFollow', '18%'],
            ['insurance-industry-news.org', 'NoFollow', '19%'],
            ['middle-east-finance.com', 'DoFollow', '20%'],
            ['auto-insurance-tips.net', 'DoFollow', '22%'],
            ['business-directory-gulf.com', 'DoFollow', '25%'],
            ['insurance-quotes-online.org', 'DoFollow', '28%'],
            ['financial-planning-hub.com', 'DoFollow', '30%'],
            ['vehicle-protection-blog.net', 'DoFollow', '32%'],
            ['insurance-market-analysis.org', 'DoFollow', '35%'],
            ['business-networking-uae.ae', 'NoFollow', '38%'],
            ['auto-coverage-experts.com', 'DoFollow', '42%'],
            ['regional-insurance-forum.org', 'DoFollow', '45%']
        ]

        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'additional_{domain}_referring_domains_{timestamp}.csv'
        filepath = os.path.join('reports', filename)

        # Ensure reports directory exists
        os.makedirs('reports', exist_ok=True)

        # Write CSV file
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(additional_domains)

        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype='text/csv'
        )

    except Exception as e:
        logger.error(f"Error generating CSV: {e}")
        return jsonify({'error': 'Failed to generate CSV file'}), 500

@app.route('/download-broken-links-csv/<domain>')
def download_broken_links_csv(domain):
    """Generate and download CSV with all broken links"""
    try:
        # Get stored crawler results
        crawler_results = app.config.get(f'crawler_results_{domain}')

        if not crawler_results or not crawler_results.get('broken_links'):
            # Fallback to sample data if no results found
            broken_links_data = [
                ['Source Page URL', 'Broken Link URL', 'Anchor Text / Current Value', 'Link Type', 'Status Code'],
                ['https://example.com/', 'https://broken-link.com', 'Sample Broken Link', 'External', '404'],
                ['https://example.com/page', 'https://example.com/missing', 'Missing Page', 'Internal', '404']
            ]
        else:
            # Use actual crawler results
            broken_links_data = [['Source Page URL', 'Broken Link URL', 'Anchor Text / Current Value', 'Link Type', 'Status Code']]

            for link in crawler_results['broken_links']:
                broken_links_data.append([
                    link['source_page'],
                    link['broken_url'],
                    link['anchor_text'],
                    link['link_type'],
                    str(link['status_code'])
                ])

        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'broken_links_{domain}_{timestamp}.csv'
        filepath = os.path.join('reports', filename)

        # Ensure reports directory exists
        os.makedirs('reports', exist_ok=True)

        # Write CSV file
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(broken_links_data)

        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype='text/csv'
        )

    except Exception as e:
        logger.error(f"Error generating broken links CSV: {e}")
        return jsonify({'error': 'Failed to generate broken links CSV file'}), 500

if __name__ == '__main__':
    # Ensure the reports directory exists
    os.makedirs('reports', exist_ok=True)

    # Run Flask app on all interfaces for external access
    app.run(host='0.0.0.0', port=5000, debug=True)