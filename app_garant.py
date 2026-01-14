from flask import Flask, render_template, render_template_string, request, send_file
import psycopg2
import psycopg2.extras
import re
from bs4 import BeautifulSoup
import openai
import os
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
import io
from functools import lru_cache

app = Flask(__name__)

PG_CONFIG = {
    'host': '127.0.0.1',
    'port': 5432,
    'database': 'starec_laws',
    'user': 'flaskapp',
    'password': 'flaskpass123'
}

# OpenAI API key (should be in environment variable)
openai.api_key = os.getenv('OPENAI_API_KEY', '')

# Simple HTML template for law list (index page)
INDEX_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>База законов Российской Федерации</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Times New Roman', serif;
            line-height: 1.6;
            color: #000;
            background: #f5f5f5;
            padding: 20px;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            padding: 40px 60px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header {
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 2px solid #000;
        }
        .header h1 {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 10px;
            text-transform: uppercase;
        }
        .law-meta {
            font-size: 14px;
            color: #666;
            margin-top: 10px;
        }
        .law-list {
            list-style: none;
        }
        .law-list li {
            padding: 10px;
            border-bottom: 1px solid #e0e0e0;
        }
        .law-list a {
            color: #1d1d1f;
            text-decoration: none;
            font-size: 16px;
        }
        .law-list a:hover {
            text-decoration: underline;
        }
        .search-box {
            margin: 30px 0;
            text-align: center;
        }
        .search-box input {
            width: 60%;
            padding: 12px 20px;
            font-size: 16px;
            border: 1px solid #ccc;
            border-radius: 4px;
        }
        .search-box button {
            padding: 12px 30px;
            font-size: 16px;
            background: #1d1d1f;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            margin-left: 10px;
        }
        .search-box button:hover {
            background: #000000;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>База законов Российской Федерации</h1>
            <div class="law-meta">Всего законов с текстом: {{ total_laws }}</div>
        </div>

        <div class="search-box">
            <form action="/search" method="get">
                <input type="text" name="q" placeholder="Поиск" required>
                <button type="submit">Найти</button>
            </form>
        </div>

        <ul class="law-list">
        {% for l in laws %}
            <li><a href="/law/{{ l.id }}">{{ l.title }}</a></li>
        {% endfor %}
        </ul>
    </div>
</body>
</html>
'''


def parse_law_structure(full_text_html):
    """
    Parse law HTML structure to extract:
    - Sections (РАЗДЕЛ)
    - Chapters (Глава)
    - Articles (Статья in <div id="stXXX">)

    Returns:
        toc: List of sections with chapters and articles
        articles: Flat list of all articles
        full_text_processed: HTML with article-section wrappers

    FIXED: Process only top-level elements to avoid duplication
    """
    if not full_text_html:
        return [], [], ""

    soup = BeautifulSoup(full_text_html, 'html.parser')

    toc = []
    articles = []
    current_section = None
    current_chapter = None

    processed_html_parts = []

    # Process only direct children of body/root to avoid nested duplication
    # Get the root element (could be body or the parsed fragment)
    root_elements = list(soup.children) if soup.name is None else [soup]

    def process_children(parent):
        """Process direct children only, no recursion into nested elements"""
        nonlocal current_section, current_chapter

        for elem in parent.children:
            # Skip text nodes
            if isinstance(elem, str):
                if elem.strip():
                    processed_html_parts.append(elem)
                continue

            if not hasattr(elem, 'name'):
                continue

            text = elem.get_text(strip=True)

            # Check for SECTION
            if elem.name == 'p' and text.startswith('РАЗДЕЛ'):
                current_section = {
                    'title': text,
                    'chapters': [],
                    'articles': []
                }
                toc.append(current_section)
                current_chapter = None
                processed_html_parts.append(str(elem))

            # Check for CHAPTER
            elif elem.name == 'p' and text.startswith('Глава'):
                if current_section:
                    current_chapter = {
                        'title': text,
                        'articles': []
                    }
                    current_section['chapters'].append(current_chapter)
                processed_html_parts.append(str(elem))

            # Check for ARTICLE (div with id="stXXX" or id="ст-XXX" or class="article")
            elif elem.name == 'div' and (elem.get('id', '').startswith('st') or elem.get('id', '').startswith('ст-') or 'article' in elem.get('class', [])):
                article_id = elem.get('id')
                article_title_elem = elem.find('h3')

                if article_title_elem:
                    article_title = article_title_elem.get_text(strip=True)

                    # Add to flat article list
                    articles.append({
                        'id': article_id,
                        'title': article_title
                    })

                    # Add to current chapter or section
                    article_entry = {
                        'id': article_id,
                        'title': article_title
                    }

                    if current_chapter:
                        current_chapter['articles'].append(article_entry)
                    elif current_section:
                        current_section['articles'].append(article_entry)

                    # Wrap article in section div for styling
                    elem['class'] = elem.get('class', []) + ['article-section']
                    processed_html_parts.append(str(elem))
                else:
                    processed_html_parts.append(str(elem))

            else:
                # For other elements, add them as-is
                processed_html_parts.append(str(elem))

    # Process all root-level elements
    for root in root_elements:
        if hasattr(root, 'children'):
            process_children(root)
        elif hasattr(root, 'name'):
            # Single element case
            processed_html_parts.append(str(root))

    # If no sections found, create a default section
    if not toc and articles:
        toc = [{
            'title': 'Статьи',
            'chapters': [],
            'articles': articles
        }]

    full_text_processed = ''.join(processed_html_parts)

    return toc, articles, full_text_processed


def get_query_embedding(query_text):
    """Generate embedding for search query using OpenAI"""
    try:
        response = openai.embeddings.create(
            model="text-embedding-3-small",
            input=query_text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None


@app.route('/')
def index():
    """Clean homepage with search and link to laws database"""
    return render_template('index_clean.html')


@app.route('/laws')
def laws_list():
    """Laws list with filters"""
    conn = psycopg2.connect(**PG_CONFIG)
    cursor = conn.cursor()

    # Get filter parameters
    law_type = request.args.get('law_type', '').strip()
    search = request.args.get('search', '').strip()

    # Build query
    query = """
        SELECT id, title, law_number, law_date, last_amendment_date
        FROM law_embeddings
        WHERE full_text IS NOT NULL AND length(full_text) > 500
    """
    params = []

    # Apply filters
    if law_type == 'Кодекс':
        query += " AND title ILIKE %s"
        params.append('%кодекс%')
    elif law_type == 'ФКЗ':
        query += " AND law_number LIKE %s"
        params.append('%-ФКЗ')
    elif law_type == 'ФЗ':
        query += " AND (law_number LIKE %s AND law_number NOT LIKE %s)"
        params.extend(['%-ФЗ', '%-ФКЗ'])

    if search:
        query += " AND title ILIKE %s"
        params.append(f'%{search}%')

    query += " ORDER BY title"

    cursor.execute(query, params)
    laws = []
    for row in cursor.fetchall():
        laws.append({
            'id': row[0],
            'title': row[1],
            'law_number': row[2],
            'law_date': row[3],
            'last_amendment_date': row[4]
        })

    cursor.close()
    conn.close()

    return render_template('laws_list.html', laws=laws, law_type=law_type, search=search)


@app.route('/search')
def search():
    """Semantic search using vector similarity"""
    query = request.args.get('q', '').strip()

    if not query:
        return render_template_string(INDEX_TEMPLATE, laws=[], total_laws=0)

    # Generate query embedding
    query_embedding = get_query_embedding(query)

    if not query_embedding:
        return "Error generating search embedding", 500

    # Search using cosine similarity
    conn = psycopg2.connect(**PG_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            title,
            1 - (embedding <=> %s::vector) AS similarity
        FROM law_embeddings
        WHERE embedding IS NOT NULL
        ORDER BY similarity DESC
        LIMIT 20
    """, (query_embedding,))

    results = cursor.fetchall()
    cursor.close()
    conn.close()

    # Format results
    laws = [{'id': row[0], 'title': f"{row[1]} (релевантность: {row[2]:.2f})"} for row in results]

    return render_template_string(INDEX_TEMPLATE, laws=laws, total_laws=len(laws))


@app.route('/law/<int:law_id>')
def show_law(law_id):
    """Show single law with Garant-style UI"""
    conn = psycopg2.connect(**PG_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, authority, eo_number, full_text,
               law_number, law_date, last_amendment_date, last_amendment_info
        FROM law_embeddings
        WHERE id = %s
    """, (law_id,))
    row = cursor.fetchone()

    if not row:
        cursor.close()
        conn.close()
        return "Закон не найден", 404

    law = {
        'id': row[0],
        'title': row[1],
        'authority': row[2],
        'eo_number': row[3],  # Fake number, won't show if law_number exists
        'full_text': row[4],
        'law_number': row[5],  # Real law number like "95-ФЗ"
        'law_date': row[6],     # Real law date
        'last_amendment_date': row[7],
        'last_amendment_info': row[8]
    }

    # Get all editions for this law from law_editions table
    cursor.execute("""
        SELECT id, edition_id, valid_from, change_reason, is_current
        FROM law_editions
        WHERE law_id = %s
        ORDER BY valid_from DESC
    """, (law_id,))

    editions = []
    for ed_row in cursor.fetchall():
        editions.append({
            'id': ed_row[0],
            'edition_id': ed_row[1],
            'date': ed_row[2],
            'description': ed_row[3],
            'is_current': ed_row[4]
        })

    cursor.close()
    conn.close()

    # Parse law structure
    toc, articles, full_text_processed = parse_law_structure(law['full_text'])

    law['full_text_processed'] = full_text_processed

    return render_template(
        'law_detail_garant.html',
        law=law,
        toc=toc,
        articles=articles,
        editions=editions
    )


@app.route('/law/<int:law_id>/edition/<int:edition_id>')
def show_law_edition(law_id, edition_id):
    """Show specific edition of a law"""
    conn = psycopg2.connect(**PG_CONFIG)
    cursor = conn.cursor()

    # Get law basic info
    cursor.execute("""
        SELECT id, title, law_number, law_date
        FROM law_embeddings
        WHERE id = %s
    """, (law_id,))
    law_row = cursor.fetchone()

    if not law_row:
        cursor.close()
        conn.close()
        return "Закон не найден", 404

    # Get specific edition
    cursor.execute("""
        SELECT id, edition_id, valid_from, change_reason, content_html, is_current
        FROM law_editions
        WHERE id = %s AND law_id = %s
    """, (edition_id, law_id))
    ed_row = cursor.fetchone()

    if not ed_row:
        cursor.close()
        conn.close()
        return "Редакция не найдена", 404

    law = {
        'id': law_row[0],
        'title': law_row[1],
        'law_number': law_row[2],
        'law_date': law_row[3],
        'full_text': ed_row[4],  # content_html from edition
        'last_amendment_date': ed_row[2],  # valid_from date
        'last_amendment_info': ed_row[3]   # change_reason
    }

    # Get all editions for navigation
    cursor.execute("""
        SELECT id, edition_id, valid_from, change_reason, is_current
        FROM law_editions
        WHERE law_id = %s
        ORDER BY valid_from DESC
    """, (law_id,))

    editions = []
    for e in cursor.fetchall():
        editions.append({
            'id': e[0],
            'edition_id': e[1],
            'date': e[2],
            'description': e[3],
            'is_current': e[4]
        })

    cursor.close()
    conn.close()

    # Parse law structure
    toc, articles, full_text_processed = parse_law_structure(law['full_text'])
    law['full_text_processed'] = full_text_processed

    return render_template(
        'law_detail_garant.html',
        law=law,
        toc=toc,
        articles=articles,
        editions=editions,
        current_edition_id=edition_id,
        is_revision_view=True
    )


@app.route('/law/<int:law_id>/download')
def download_law(law_id):
    """Download law as DOCX file"""
    conn = psycopg2.connect(**PG_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, full_text, law_number, law_date, last_amendment_date
        FROM law_embeddings
        WHERE id = %s
    """, (law_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        return "Закон не найден", 404

    law = {
        'id': row[0],
        'title': row[1],
        'full_text': row[2],
        'law_number': row[3],
        'law_date': row[4],
        'last_amendment_date': row[5]
    }

    # Create DOCX document
    doc = Document()

    # Add title
    title = doc.add_paragraph()
    title_run = title.add_run(law['title'])
    title_run.bold = True
    title_run.font.size = Pt(16)
    title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

    # Add metadata
    if law['law_number'] and law['law_date']:
        meta = doc.add_paragraph()
        meta_text = f"от {law['law_date']} N {law['law_number']}"
        if law['last_amendment_date']:
            meta_text += f" (ред. от {law['last_amendment_date']})"
        meta_run = meta.add_run(meta_text)
        meta_run.font.size = Pt(12)
        meta.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

    doc.add_paragraph()  # Empty line

    # Parse HTML and add content
    if law['full_text']:
        soup = BeautifulSoup(law['full_text'], 'html.parser')

        for elem in soup.find_all(['p', 'h3', 'div']):
            text = elem.get_text(strip=True)
            if not text:
                continue

            # Check element type
            if elem.name == 'h3':
                # Article heading
                para = doc.add_paragraph()
                run = para.add_run(text)
                run.bold = True
                run.font.size = Pt(14)
            elif text.startswith('РАЗДЕЛ'):
                # Section title
                para = doc.add_paragraph()
                run = para.add_run(text)
                run.bold = True
                run.font.size = Pt(14)
                para.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
            elif text.startswith('Глава'):
                # Chapter title
                para = doc.add_paragraph()
                run = para.add_run(text)
                run.bold = True
                run.font.size = Pt(13)
            else:
                # Regular paragraph
                para = doc.add_paragraph(text)
                para.style = 'Normal'

    # Save to BytesIO
    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)

    # Generate filename
    filename = f"{law['law_number']}_{law_id}.docx" if law['law_number'] else f"law_{law_id}.docx"

    return send_file(
        file_stream,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )


# ========== V2.0 ROUTES ==========

@app.route('/v2/')
def v2_index():
    conn = psycopg2.connect(**PG_CONFIG)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT COUNT(*) as cnt FROM legal_regimes")
    regimes_count = cur.fetchone()['cnt']

    cur.execute("SELECT COUNT(*) as cnt FROM legal_states")
    states_count = cur.fetchone()['cnt']

    cur.execute("SELECT id, name, category, description FROM legal_regimes WHERE parent_regime_id IS NULL ORDER BY id")
    regimes = cur.fetchall()

    cur.close()
    conn.close()

    stats = {
        'regimes_count': regimes_count,
        'states_count': states_count,
        'situations_count': 0,
        'active_norms_count': 0
    }

    return render_template('v2/index.html', stats=stats, regimes=regimes)


@app.route('/v2/situations/')
def v2_situations():
    return render_template('v2/situations.html', situations=[])


@app.route('/v2/regimes/')
def v2_regimes():
    conn = psycopg2.connect(**PG_CONFIG)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, name, category, description FROM legal_regimes ORDER BY name")
    regimes = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('v2/regimes.html', regimes=regimes)


@app.route('/v2/timeline/')
def v2_timeline():
    return render_template('v2/timeline.html', changes=[])


@app.route('/v2/regime/<int:regime_id>')
def v2_regime_detail(regime_id):
    conn = psycopg2.connect(**PG_CONFIG)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT id, name, category, description FROM legal_regimes WHERE id = %s", (regime_id,))
    regime = cur.fetchone()

    if not regime:
        cur.close()
        conn.close()
        return "Режим не найден", 404

    cur.execute("SELECT id, name, description FROM legal_states WHERE regime_id = %s ORDER BY name", (regime_id,))
    states = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('v2/regime_detail.html', regime=regime, states=states)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
