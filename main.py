
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
    
    def analyze_seo_data(self, audit_data):
        """Analyze audit data and generate insights"""
        if not audit_data:
            return None
            
        page_data = audit_data[0] if audit_data else {}
        
        analysis = {
            'url': page_data.get('url', ''),
            'title': page_data.get('meta', {}).get('title', ''),
            'meta_description': page_data.get('meta', {}).get('description', ''),
            'h1_tags': [],
            'h2_tags': [],
            'images_without_alt': 0,
            'total_images': 0,
            'internal_links': 0,
            'external_links': 0,
            'page_size': page_data.get('page_timing', {}).get('time_to_interactive', 0),
            'load_time': page_data.get('page_timing', {}).get('dom_complete', 0),
            'word_count': 0,
            'schema_markup': [],
            'issues': [],
            'scores': {}
        }
        
        # Extract heading tags
        content = page_data.get('content', {})
        if content:
            analysis['h1_tags'] = [h.get('text', '') for h in content.get('h1', [])]
            analysis['h2_tags'] = [h.get('text', '') for h in content.get('h2', [])]
        
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
            title_score = 60
        scores['title'] = title_score
        
        # Meta description score
        meta_desc = analysis['meta_description']
        meta_score = 100
        if not meta_desc:
            meta_score = 0
        elif len(meta_desc) < 120 or len(meta_desc) > 160:
            meta_score = 70
        scores['meta_description'] = meta_score
        
        # Headings score
        h1_count = len(analysis['h1_tags'])
        headings_score = 100
        if h1_count == 0:
            headings_score = 20
        elif h1_count > 1:
            headings_score = 60
        scores['headings'] = headings_score
        
        # Images score
        if analysis['total_images'] > 0:
            alt_ratio = (analysis['total_images'] - analysis['images_without_alt']) / analysis['total_images']
            images_score = int(alt_ratio * 100)
        else:
            images_score = 100
        scores['images'] = images_score
        
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
        if h1_count == 0:
            issues.append("Add an H1 tag to your page")
        elif h1_count > 1:
            issues.append("Use only one H1 tag per page")
        
        # Image issues
        if analysis['images_without_alt'] > 0:
            issues.append(f"Add alt text to {analysis['images_without_alt']} images")
        
        # Link issues
        if analysis['internal_links'] < 3:
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
    
    def generate_report(self, analysis, filename):
        """Generate PDF report"""
        doc = SimpleDocTemplate(filename, pagesize=A4)
        story = []
        
        # Title page
        story.append(Paragraph("SEO Audit Report", self.title_style))
        story.append(Spacer(1, 20))
        
        # URL and date
        story.append(Paragraph(f"<b>Website:</b> {analysis['url']}", self.body_style))
        story.append(Paragraph(f"<b>Report Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}", self.body_style))
        story.append(Spacer(1, 30))
        
        # Overall score
        overall_score = analysis['scores']['overall']
        score_color = self.get_score_color(overall_score)
        story.append(Paragraph("Overall SEO Score", self.heading_style))
        story.append(Paragraph(f"<font color='{score_color}'><b>{overall_score}/100</b></font>", 
                              ParagraphStyle('ScoreStyle', fontSize=36, alignment=TA_CENTER)))
        story.append(Spacer(1, 20))
        
        # Scores table
        story.append(Paragraph("Detailed Scores", self.heading_style))
        
        score_data = [['Metric', 'Score', 'Status']]
        for metric, score in analysis['scores'].items():
            if metric != 'overall':
                status = 'Good' if score >= 80 else 'Needs Improvement' if score >= 60 else 'Critical'
                score_data.append([metric.replace('_', ' ').title(), f"{score}/100", status])
        
        score_table = Table(score_data, colWidths=[2*inch, 1*inch, 1.5*inch])
        score_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), HexColor('#F5F5F5')),
            ('GRID', (0, 0), (-1, -1), 1, black)
        ]))
        
        story.append(score_table)
        story.append(Spacer(1, 20))
        
        # Issues and recommendations
        story.append(Paragraph("Issues & Recommendations", self.heading_style))
        
        if analysis['issues']:
            for i, issue in enumerate(analysis['issues'], 1):
                story.append(Paragraph(f"{i}. {issue}", self.body_style))
        else:
            story.append(Paragraph("No critical issues found!", self.body_style))
        
        story.append(Spacer(1, 20))
        
        # Technical details
        story.append(Paragraph("Technical Details", self.heading_style))
        
        details_data = [
            ['Title Tag', analysis['title'] or 'Not found'],
            ['Meta Description', analysis['meta_description'] or 'Not found'],
            ['H1 Tags', str(len(analysis['h1_tags']))],
            ['H2 Tags', str(len(analysis['h2_tags']))],
            ['Total Images', str(analysis['total_images'])],
            ['Images without Alt', str(analysis['images_without_alt'])],
            ['Internal Links', str(analysis['internal_links'])],
            ['External Links', str(analysis['external_links'])]
        ]
        
        details_table = Table(details_data, colWidths=[2*inch, 4*inch])
        details_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), HexColor('#E3F2FD')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP')
        ]))
        
        story.append(details_table)
        story.append(Spacer(1, 30))
        
        # Notes section
        story.append(Paragraph("Notes & Custom Annotations", self.heading_style))
        story.append(Paragraph("_" * 80, self.body_style))
        story.append(Spacer(1, 20))
        story.append(Paragraph("_" * 80, self.body_style))
        story.append(Spacer(1, 20))
        story.append(Paragraph("_" * 80, self.body_style))
        
        doc.build(story)

# Initialize the auditor
auditor = SEOAuditor()
pdf_generator = PDFReportGenerator()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/audit', methods=['POST'])
def start_audit():
    data = request.get_json()
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    # Validate URL format
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    try:
        # Start audit
        task_id = auditor.start_audit(url)
        if not task_id:
            return jsonify({'error': 'Failed to start audit'}), 500
        
        return jsonify({'task_id': task_id, 'status': 'started'})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/results/<task_id>')
def get_results(task_id):
    try:
        # Get audit results
        audit_data = auditor.get_audit_results(task_id)
        if not audit_data:
            return jsonify({'error': 'Results not ready or task failed'}), 404
        
        # Analyze data
        analysis = auditor.analyze_seo_data(audit_data)
        if not analysis:
            return jsonify({'error': 'Failed to analyze data'}), 500
        
        return jsonify(analysis)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generate-report', methods=['POST'])
def generate_report():
    try:
        data = request.get_json()
        analysis = data.get('analysis')
        
        if not analysis:
            return jsonify({'error': 'Analysis data is required'}), 400
        
        # Generate filename
        domain = urllib.parse.urlparse(analysis['url']).netloc
        domain = re.sub(r'[^\w\-_\.]', '_', domain)
        filename = f"audit_report_{domain}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join('reports', filename)
        
        # Create reports directory if it doesn't exist
        os.makedirs('reports', exist_ok=True)
        
        # Generate PDF
        pdf_generator.generate_report(analysis, filepath)
        
        return send_file(filepath, as_attachment=True, download_name=filename)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
