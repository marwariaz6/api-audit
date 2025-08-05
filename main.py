
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

# Load environment variables
load_dotenv()

app = Flask(__name__)

class SEOAuditor:
    def __init__(self):
        self.login = os.getenv('DATAFORSEO_LOGIN')
        self.password = os.getenv('DATAFORSEO_PASSWORD')
        self.base_url = "https://api.dataforseo.com/v3"
        
    def make_request(self, endpoint, data=None, method='GET'):
        """Make authenticated request to DataForSEO API"""
        url = f"{self.base_url}{endpoint}"
        auth = (self.login, self.password)
        
        # Check credentials
        if not self.login or not self.password:
            print("DataForSEO credentials not configured. Please set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD in environment variables.")
            return None
        
        try:
            print(f"Making {method} request to: {url}")
            if method == 'POST':
                response = requests.post(url, json=data, auth=auth, timeout=30)
            else:
                response = requests.get(url, auth=auth, timeout=30)
            
            print(f"Response status: {response.status_code}")
            response.raise_for_status()
            result = response.json()
            print(f"API Response: {result}")
            return result
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text}")
            return None
    
    def start_audit(self, url):
        """Start on-page audit task"""
        # If no credentials, return placeholder task ID
        if not self.login or not self.password:
            return "placeholder_task_123"
            
        endpoint = "/on_page/task_post"
        
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
            return result['tasks'][0]['id']
        return None
    
    def get_audit_results(self, task_id):
        """Get audit results by task ID"""
        # If placeholder task, return sample data
        if task_id == "placeholder_task_123":
            return self.get_placeholder_data()
            
        endpoint = f"/on_page/task_get/{task_id}"
        
        # Poll for results with retry logic
        max_retries = 10
        for attempt in range(max_retries):
            result = self.make_request(endpoint)
            if result and result.get('status_code') == 20000:
                tasks = result.get('tasks', [])
                if tasks and tasks[0].get('status_message') == 'Ok':
                    return tasks[0].get('result', [])
            
            # Wait before retrying
            time.sleep(5)
        
        return None
    
    def get_placeholder_data(self):
        """Return placeholder audit data for testing"""
        return [{
            'url': 'https://example.com',
            'meta': {
                'title': 'Example Website - Your Business Online Solutions',
                'description': 'This is an example website showing how our comprehensive SEO audit tool works. Perfect length meta description for testing all features.',
                'keywords': 'seo, audit, website, optimization, testing',
                'author': 'Example Company',
                'robots': 'index, follow'
            },
            'content': {
                'h1': [{'text': 'Welcome to Example Website - Professional SEO Services'}],
                'h2': [
                    {'text': 'Our Comprehensive SEO Services'},
                    {'text': 'About Our Expert Team'},
                    {'text': 'Contact Information and Support'},
                    {'text': 'Client Success Stories'},
                    {'text': 'Free SEO Resources and Tools'}
                ],
                'h3': [
                    {'text': 'On-Page Optimization'},
                    {'text': 'Technical SEO Audits'},
                    {'text': 'Keyword Research'},
                    {'text': 'Content Strategy'},
                    {'text': 'Link Building Services'}
                ],
                'text_content': 'This is example content for the SEO audit. The page contains valuable information about search engine optimization services, best practices, and comprehensive analysis tools. Our team provides expert guidance for improving website visibility and search rankings through proven strategies and data-driven insights.',
                'word_count': 450
            },
            'resource': {
                'images': [
                    {'alt': 'Company logo - Professional SEO Services', 'src': 'logo.jpg'},
                    {'alt': 'Team photo - SEO experts working together', 'src': 'team.jpg'},
                    {'alt': '', 'src': 'banner1.jpg'},  # Missing alt text
                    {'alt': 'Product image - SEO audit dashboard', 'src': 'product.jpg'},
                    {'alt': '', 'src': 'banner2.jpg'},   # Missing alt text
                    {'alt': 'Client testimonial photo', 'src': 'testimonial.jpg'},
                    {'alt': 'SEO performance graph showing improvements', 'src': 'graph.jpg'},
                    {'alt': '', 'src': 'hero-bg.jpg'}   # Missing alt text
                ]
            },
            'links': [
                {'domain_from': 'example.com', 'domain_to': 'example.com', 'type': 'internal'},  # Internal
                {'domain_from': 'example.com', 'domain_to': 'example.com', 'type': 'internal'},  # Internal
                {'domain_from': 'example.com', 'domain_to': 'example.com', 'type': 'internal'},  # Internal
                {'domain_from': 'example.com', 'domain_to': 'example.com', 'type': 'internal'},  # Internal
                {'domain_from': 'example.com', 'domain_to': 'example.com', 'type': 'internal'},  # Internal
                {'domain_from': 'example.com', 'domain_to': 'google.com', 'type': 'external'},   # External
                {'domain_from': 'example.com', 'domain_to': 'facebook.com', 'type': 'external'}, # External
                {'domain_from': 'example.com', 'domain_to': 'twitter.com', 'type': 'external'},  # External
            ],
            'page_timing': {
                'time_to_interactive': 2500,
                'dom_complete': 1800,
                'first_contentful_paint': 1200,
                'largest_contentful_paint': 2100,
                'cumulative_layout_shift': 0.15
            },
            'schema_markup': [
                {'type': 'Organization', 'found': True},
                {'type': 'WebSite', 'found': True},
                {'type': 'BreadcrumbList', 'found': False}
            ],
            'technical': {
                'ssl_certificate': True,
                'mobile_friendly': True,
                'page_size_kb': 2400,
                'text_html_ratio': 0.15,
                'gzip_compression': True,
                'minified_css': False,
                'minified_js': True
            },
            'social_meta': {
                'og_title': 'Example Website - Professional SEO Services',
                'og_description': 'Get comprehensive SEO audit and optimization services',
                'og_image': 'https://example.com/og-image.jpg',
                'twitter_card': 'summary_large_image',
                'twitter_title': 'Example Website SEO Services',
                'twitter_description': 'Professional SEO audit and optimization'
            }
        }]
    
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
            'page_size': page_data.get('technical', {}).get('page_size_kb', page_data.get('page_timing', {}).get('time_to_interactive', 0)),
            'load_time': page_data.get('page_timing', {}).get('dom_complete', 0),
            'word_count': page_data.get('content', {}).get('word_count', 0),
            'schema_markup': page_data.get('schema_markup', []),
            'technical': page_data.get('technical', {}),
            'social_meta': page_data.get('social_meta', {}),
            'issues': [],
            'scores': {}
        }
        
        # Extract heading tags
        content = page_data.get('content', {})
        if content:
            analysis['h1_tags'] = [h.get('text', '') for h in content.get('h1', [])]
            analysis['h2_tags'] = [h.get('text', '') for h in content.get('h2', [])]
            analysis['h3_tags'] = [h.get('text', '') for h in content.get('h3', [])]
            
            # Extract word count if available
            if content.get('word_count'):
                analysis['word_count'] = content['word_count']
        
        # Analyze images
        images = page_data.get('resource', {}).get('images', [])
        analysis['total_images'] = len(images)
        analysis['images_without_alt'] = sum(1 for img in images if not img.get('alt'))
        
        # Analyze links
        links = page_data.get('links', [])
        for link in links:
            if link.get('domain_to') == link.get('domain_from'):
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
        schema_score = min(100, schema_count * 35)  # Up to 100 for 3+ schemas
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
    
    def generate_color_coded_report(self, analysis, filename):
        """Generate enhanced PDF report with color-coded tables"""
        doc = SimpleDocTemplate(filename, pagesize=A4)
        story = []
        
        # Title page
        story.append(Paragraph("SEO Audit Report", self.title_style))
        story.append(Spacer(1, 20))
        
        # URL and date
        story.append(Paragraph(f"<b>Website:</b> {analysis['url']}", self.body_style))
        story.append(Paragraph(f"<b>Report Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}", self.body_style))
        story.append(Spacer(1, 30))
        
        # Overall score with color-coded background
        overall_score = analysis['scores']['overall']
        score_color = self.get_score_color(overall_score)
        story.append(Paragraph("Overall SEO Score", self.heading_style))
        
        # Create overall score table with color background
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
        
        # Color-coded scores table
        story.append(Paragraph("Detailed SEO Metrics", self.heading_style))
        
        score_data = [['SEO Metric', 'Score', 'Performance Level', 'Priority']]
        
        # Define priority levels
        priority_map = {
            'title': 'High',
            'meta_description': 'High', 
            'headings': 'Medium',
            'images': 'Medium',
            'content': 'High',
            'technical': 'High',
            'social_media': 'Low',
            'schema_markup': 'Medium'
        }
        
        for metric, score in analysis['scores'].items():
            if metric != 'overall':
                if score >= 80:
                    status = 'Excellent'
                elif score >= 60:
                    status = 'Good'
                elif score >= 40:
                    status = 'Needs Work'
                else:
                    status = 'Critical'
                
                priority = priority_map.get(metric, 'Medium')
                score_data.append([
                    metric.replace('_', ' ').title(), 
                    f"{score}/100", 
                    status,
                    priority
                ])
        
        score_table = Table(score_data, colWidths=[2.2*inch, 1*inch, 1.3*inch, 1*inch])
        
        # Create table style with color-coded rows
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#1a237e')),  # Header - dark blue
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]
        
        # Add color coding for each row based on score
        for i, row in enumerate(score_data[1:], 1):
            score_text = row[1]
            score_value = int(score_text.split('/')[0])
            row_color = self.get_score_color(score_value)
            
            # Light version of the color for better readability
            if score_value >= 80:
                bg_color = HexColor('#E8F5E8')  # Light green
            elif score_value >= 60:
                bg_color = HexColor('#FFF3E0')  # Light orange
            else:
                bg_color = HexColor('#FFEBEE')  # Light red
            
            table_style.append(('BACKGROUND', (0, i), (-1, i), bg_color))
            
            # Color the score column with the actual score color
            table_style.append(('BACKGROUND', (1, i), (1, i), row_color))
            table_style.append(('TEXTCOLOR', (1, i), (1, i), white))
            table_style.append(('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'))
        
        score_table.setStyle(TableStyle(table_style))
        story.append(score_table)
        story.append(Spacer(1, 30))
        
        # Issues summary with color-coded priority
        story.append(Paragraph("Action Items & Recommendations", self.heading_style))
        
        if analysis['issues']:
            issues_data = [['Priority', 'Issue', 'Recommendation']]
            
            for issue in analysis['issues']:
                if 'title' in issue.lower() or 'meta description' in issue.lower():
                    priority = 'HIGH'
                    priority_color = HexColor('#F44336')  # Red
                elif 'image' in issue.lower() or 'heading' in issue.lower():
                    priority = 'MEDIUM'
                    priority_color = HexColor('#FF9800')  # Orange
                else:
                    priority = 'LOW'
                    priority_color = HexColor('#4CAF50')  # Green
                
                # Generate specific recommendation
                if 'title' in issue.lower():
                    recommendation = 'Optimize title tag for 30-60 characters'
                elif 'meta description' in issue.lower():
                    recommendation = 'Write compelling meta description 120-160 chars'
                elif 'alt text' in issue.lower():
                    recommendation = 'Add descriptive alt text to all images'
                elif 'H1' in issue:
                    recommendation = 'Add exactly one H1 tag per page'
                elif 'content' in issue.lower():
                    recommendation = 'Add more quality, relevant content'
                else:
                    recommendation = 'Address this SEO issue for better rankings'
                
                issues_data.append([priority, issue, recommendation])
            
            issues_table = Table(issues_data, colWidths=[1*inch, 2.5*inch, 2.5*inch])
            
            # Style the issues table
            issues_style = [
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#1a237e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP')
            ]
            
            # Color-code priority column
            for i, row in enumerate(issues_data[1:], 1):
                priority = row[0]
                if priority == 'HIGH':
                    issues_style.append(('BACKGROUND', (0, i), (0, i), HexColor('#FFCDD2')))
                    issues_style.append(('TEXTCOLOR', (0, i), (0, i), HexColor('#D32F2F')))
                elif priority == 'MEDIUM':
                    issues_style.append(('BACKGROUND', (0, i), (0, i), HexColor('#FFE0B2')))
                    issues_style.append(('TEXTCOLOR', (0, i), (0, i), HexColor('#F57C00')))
                else:
                    issues_style.append(('BACKGROUND', (0, i), (0, i), HexColor('#C8E6C9')))
                    issues_style.append(('TEXTCOLOR', (0, i), (0, i), HexColor('#388E3C')))
                
                issues_style.append(('FONTNAME', (0, i), (0, i), 'Helvetica-Bold'))
            
            issues_table.setStyle(TableStyle(issues_style))
            story.append(issues_table)
        else:
            story.append(Paragraph("🎉 No critical issues found! Your website is well-optimized.", self.body_style))
        
        story.append(Spacer(1, 30))
        
        # Technical summary table
        story.append(Paragraph("Technical Details", self.heading_style))
        
        tech_data = [
            ['Metric', 'Value', 'Status'],
            ['Title Length', f"{len(analysis['title'])} characters", 'Good' if 30 <= len(analysis['title']) <= 60 else 'Needs Work'],
            ['Meta Description Length', f"{len(analysis['meta_description'])} characters", 'Good' if 120 <= len(analysis['meta_description']) <= 160 else 'Needs Work'],
            ['H1 Tags Count', str(len(analysis['h1_tags'])), 'Good' if len(analysis['h1_tags']) == 1 else 'Needs Work'],
            ['H2 Tags Count', str(len(analysis['h2_tags'])), 'Good' if len(analysis['h2_tags']) > 0 else 'Needs Work'],
            ['Images Total', str(analysis['total_images']), 'Info'],
            ['Images Missing Alt', str(analysis['images_without_alt']), 'Good' if analysis['images_without_alt'] == 0 else 'Needs Work'],
            ['Internal Links', str(analysis['internal_links']), 'Good' if analysis['internal_links'] >= 3 else 'Needs Work'],
            ['External Links', str(analysis['external_links']), 'Good' if analysis['external_links'] > 0 else 'OK'],
            ['Content Words', str(analysis['word_count']), 'Good' if analysis['word_count'] >= 300 else 'Needs Work']
        ]
        
        tech_table = Table(tech_data, colWidths=[2.5*inch, 2*inch, 1.5*inch])
        
        # Style technical table with alternating colors
        tech_style = [
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
        
        # Color-code status column and alternate row colors
        for i, row in enumerate(tech_data[1:], 1):
            # Alternate row colors
            if i % 2 == 0:
                tech_style.append(('BACKGROUND', (0, i), (-1, i), HexColor('#F8F9FA')))
            
            # Color-code status
            status = row[2]
            if status == 'Good':
                tech_style.append(('BACKGROUND', (2, i), (2, i), HexColor('#4CAF50')))
                tech_style.append(('TEXTCOLOR', (2, i), (2, i), white))
            elif status == 'Needs Work':
                tech_style.append(('BACKGROUND', (2, i), (2, i), HexColor('#F44336')))
                tech_style.append(('TEXTCOLOR', (2, i), (2, i), white))
            elif status == 'OK':
                tech_style.append(('BACKGROUND', (2, i), (2, i), HexColor('#FF9800')))
                tech_style.append(('TEXTCOLOR', (2, i), (2, i), white))
            else:  # Info
                tech_style.append(('BACKGROUND', (2, i), (2, i), HexColor('#2196F3')))
                tech_style.append(('TEXTCOLOR', (2, i), (2, i), white))
            
            tech_style.append(('FONTNAME', (2, i), (2, i), 'Helvetica-Bold'))
        
        tech_table.setStyle(TableStyle(tech_style))
        story.append(tech_table)
        
        doc.build(story)
    
    def generate_report(self, analysis, filename):
        """Generate standard PDF report (kept for compatibility)"""
        return self.generate_color_coded_report(analysis, filename)

# Initialize the auditor
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
        
        # Validate URL format
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Get placeholder data and analyze it
        audit_data = auditor.get_placeholder_data()
        
        # Update URL in placeholder data
        if audit_data:
            audit_data[0]['url'] = url
        
        analysis = auditor.analyze_seo_data(audit_data)
        if not analysis:
            return jsonify({'error': 'Failed to analyze data'}), 500
        
        # Generate filename
        domain = urllib.parse.urlparse(url).netloc
        domain = re.sub(r'[^\w\-_\.]', '_', domain)
        filename = f"seo_audit_report_{domain}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join('reports', filename)
        
        # Create reports directory if it doesn't exist
        os.makedirs('reports', exist_ok=True)
        
        # Generate PDF with color-coded table
        pdf_generator.generate_color_coded_report(analysis, filepath)
        
        return send_file(filepath, as_attachment=True, download_name=filename)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
