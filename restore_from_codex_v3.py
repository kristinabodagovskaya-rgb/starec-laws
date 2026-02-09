#!/usr/bin/env python3
"""Восстановление данных с codex.starec.ai - v3 с правильными редакциями"""

import psycopg2
import requests
import re

DB_CONFIG = {
    'database': 'starec_laws',
    'user': 'flaskapp',
    'password': 'flaskpass123',
    'host': 'localhost'
}

TITLE_TO_ND = {
    'арбитражный процессуальный кодекс': 102079219,
    'гражданский процессуальный кодекс': 102078828,
    'гражданский кодекс рф часть 1': 102033239,
    'гражданский кодекс рф часть 2': 102039276,
    'гражданский кодекс рф часть 3': 102073578,
    'гражданский кодекс рф часть 4': 102110716,
    'семейный кодекс': 102038925,
    'трудовой кодекс': 102074279,
    'жилищный кодекс': 102090645,
    'земельный кодекс': 102073184,
    'налоговый кодекс рф часть 1': 102054722,
    'налоговый кодекс рф часть 2': 102067058,
    'бюджетный кодекс': 102054721,
    'уголовный кодекс': 102041891,
    'уголовно-процессуальный кодекс': 102073942,
    'уголовно-исполнительный кодекс': 102045146,
    'кодекс об административных правонарушениях': 102074277,
}

def find_nd_for_title(title):
    title_lower = title.lower()
    for key, nd in TITLE_TO_ND.items():
        if key in title_lower:
            return nd
    return None

def fetch_from_codex(nd):
    url = f"https://codex.starec.ai/api/documents/{nd}?include_articles=true"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.json()

def format_content_with_linebreaks(text):
    """Добавить переносы строк перед пунктами"""
    if not text:
        return ''

    # Добавляем <br> перед нумерованными пунктами: 1. 2. 3. и т.д.
    text = re.sub(r'(\s)(\d+)\.\s+', r'\1<br>\2. ', text)

    # Добавляем <br> перед пунктами со скобкой: 1) 2) 3)
    text = re.sub(r'(\s)(\d+)\)\s+', r'\1<br>\2) ', text)

    # Добавляем <br> перед буквенными пунктами: а) б) в)
    text = re.sub(r'(\s)([а-яё])\)\s+', r'\1<br>\2) ', text)

    return text

def format_document(doc, our_title):
    """Форматировать документ с правильными метаданными"""
    title = doc.get('title', our_title)
    articles = doc.get('articles', [])
    editions = doc.get('editions', [])
    sign_date = doc.get('sign_date', '')
    number = doc.get('number', '')
    
    html_parts = []
    
    # ШАПКА
    html_parts.append('<div class="law-document">')
    html_parts.append('<div class="law-header">')
    html_parts.append('<div class="law-type">КОДЕКС РОССИЙСКОЙ ФЕДЕРАЦИИ</div>')
    if sign_date or number:
        date_num = f"от {sign_date}" if sign_date else ''
        if number:
            date_num += f" № {number}" if date_num else f"№ {number}"
        html_parts.append(f'<div class="law-date-number">{date_num}</div>')
    html_parts.append(f'<h1 class="law-title">{title}</h1>')
    html_parts.append('</div>')
    
    # РЕДАКЦИИ в сворачиваемом блоке
    if editions:
        html_parts.append('<details class="law-editions-block">')
        html_parts.append(f'<summary>Редакции документа ({len(editions)})</summary>')
        html_parts.append('<div class="law-editions-list">')
        for ed in sorted(editions, key=lambda x: x.get('valid_from', '') or '', reverse=True)[:30]:
            ed_date = ed.get('valid_from', '') or ''
            ed_reason = ed.get('change_reason', '') or ''
            if ed_date or ed_reason:
                html_parts.append('<div class="law-edition-item">')
                html_parts.append(f'<span class="edition-date">{ed_date}</span>')
                html_parts.append(f'<span class="edition-title">{ed_reason}</span>')
                html_parts.append('</div>')
        html_parts.append('</div>')
        html_parts.append('</details>')
    
    # СОДЕРЖАНИЕ
    html_parts.append('<div class="law-content">')
    
    for article in articles:
        art_number = article.get('number', '')
        art_title = article.get('title', '')
        art_text = article.get('text', article.get('content', ''))
        
        html_parts.append(f'<div class="law-article" id="article-{art_number}">')
        if art_number or art_title:
            header = f'Статья {art_number}' if art_number else ''
            if art_title:
                header = f'{header}. {art_title}' if header else art_title
            html_parts.append(f'<h3 class="law-article-title">{header}</h3>')
        
        if art_text:
            formatted_text = format_content_with_linebreaks(art_text)
            html_parts.append(f'<div class="law-article-content">{formatted_text}</div>')
        html_parts.append('</div>')
    
    html_parts.append('</div>')  # law-content
    html_parts.append('</div>')  # law-document
    
    return '\n'.join(html_parts)

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, title FROM law_embeddings 
        WHERE title ILIKE '%кодекс%'
        ORDER BY id
    """)
    laws = cur.fetchall()
    
    print(f"Кодексов: {len(laws)}\n")
    
    restored = 0
    
    for law_id, title in laws:
        print(f"[{law_id}] {title}")
        
        nd = find_nd_for_title(title)
        if not nd:
            print(f"    ND не найден")
            continue
        
        print(f"    ND: {nd}")
        
        try:
            doc = fetch_from_codex(nd)
            articles = doc.get('articles', [])
            editions = doc.get('editions', [])
            
            if not articles:
                print(f"    Нет статей")
                continue
            
            print(f"    Статей: {len(articles)}, редакций: {len(editions)}")
            
            formatted = format_document(doc, title)
            
            cur.execute("UPDATE law_embeddings SET full_text = %s WHERE id = %s", (formatted, law_id))
            conn.commit()
            
            print(f"    ✓ OK ({len(formatted)} симв.)")
            restored += 1
            
        except Exception as e:
            print(f"    Ошибка: {e}")
    
    cur.close()
    conn.close()
    print(f"\nВосстановлено: {restored}")

if __name__ == '__main__':
    main()
