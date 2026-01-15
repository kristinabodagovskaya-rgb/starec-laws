#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Принудительное применение единого стиля ко ВСЕМ законам
"""

import psycopg2
import re
from bs4 import BeautifulSoup

DB_CONFIG = {
    'dbname': 'starec_laws',
    'user': 'flaskapp',
    'password': 'flaskpass123',
    'host': 'localhost'
}

def extract_law_content(html):
    """Извлекает чистый текст закона без обёрток"""
    if not html:
        return ''
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Удаляем блок редакций если есть
    for block in soup.find_all(class_='law-editions-block'):
        block.decompose()
    for block in soup.find_all(class_='editions-dropdown'):
        block.decompose()
    
    # Удаляем заголовок если есть
    for header in soup.find_all(class_='law-header'):
        header.decompose()
    
    # Получаем содержимое
    law_doc = soup.find(class_='law-document')
    if law_doc:
        # Берём содержимое law-content если есть
        law_content = law_doc.find(class_='law-content')
        if law_content:
            return law_content.decode_contents()
        return law_doc.decode_contents()
    
    # Возвращаем как есть
    return str(soup)

def get_editions_for_law(conn, law_id):
    """Получает редакции закона из БД"""
    cur = conn.cursor()
    cur.execute('''
        SELECT id, valid_from, change_reason 
        FROM law_editions 
        WHERE law_id = %s 
        ORDER BY valid_from DESC
    ''', (law_id,))
    editions = cur.fetchall()
    cur.close()
    return editions

def generate_editions_html(law_id, editions):
    """Генерирует HTML блок редакций"""
    if not editions:
        return ''
    
    html = []
    html.append('<div class="law-editions-block">')
    html.append(f'<details class="editions-dropdown">')
    html.append(f'<summary class="editions-summary">Редакции документа ({len(editions)})</summary>')
    html.append('<div class="editions-list">')
    
    for ed_id, valid_from, change_reason in editions:
        date_str = valid_from.strftime('%d.%m.%Y') if valid_from else 'Без даты'
        reason_str = change_reason if change_reason else ''
        
        html.append('<div class="edition-item">')
        html.append(f'<a href="/law/{law_id}/edition/{ed_id}" class="edition-link">')
        html.append(f'<span class="edition-date">{date_str}</span>')
        if reason_str:
            html.append(f' - <span class="edition-title">{reason_str}</span>')
        html.append('</a>')
        html.append('</div>')
    
    html.append('</div>')
    html.append('</details>')
    html.append('</div>')
    
    return '\n'.join(html)

def create_unified_html(title, editions_html, content):
    """Создаёт HTML в едином стиле"""
    # Определяем тип документа
    title_upper = title.upper()
    if 'КОДЕКС' in title_upper:
        doc_type = 'КОДЕКС РОССИЙСКОЙ ФЕДЕРАЦИИ'
    elif 'ФЕДЕРАЛЬНЫЙ КОНСТИТУЦИОННЫЙ' in title_upper:
        doc_type = 'ФЕДЕРАЛЬНЫЙ КОНСТИТУЦИОННЫЙ ЗАКОН'
    elif 'ФЕДЕРАЛЬНЫЙ ЗАКОН' in title_upper or '-ФЗ' in title:
        doc_type = 'ФЕДЕРАЛЬНЫЙ ЗАКОН'
    else:
        doc_type = 'ДОКУМЕНТ'
    
    # Чистим title
    clean_title = title
    clean_title = re.sub(r'^Федеральный закон\s+', '', clean_title, flags=re.I)
    clean_title = re.sub(r'^Кодекс\s+', '', clean_title, flags=re.I)
    
    html = f'''<div class="law-document">
    <div class="law-header">
        <div class="law-type">{doc_type}</div>
        <h1 class="law-title">{clean_title}</h1>
    </div>
    
    {editions_html}
    
    <div class="law-content">
        {content}
    </div>
</div>'''
    
    return html

def process_all_laws():
    """Обрабатывает все законы"""
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()
    
    # Получаем все законы
    cur.execute('SELECT id, title, full_text FROM law_embeddings ORDER BY id')
    laws = cur.fetchall()
    
    print(f'Всего законов: {len(laws)}')
    
    updated = 0
    errors = 0
    for law_id, title, full_text in laws:
        try:
            # Получаем редакции
            editions = get_editions_for_law(conn, law_id)
            
            # Извлекаем контент
            content = extract_law_content(full_text)
            
            # Генерируем блок редакций
            editions_html = generate_editions_html(law_id, editions)
            
            # Создаём новый HTML
            new_html = create_unified_html(title, editions_html, content)
            
            # Обновляем в БД
            cur.execute('UPDATE law_embeddings SET full_text = %s WHERE id = %s', (new_html, law_id))
            conn.commit()
            updated += 1
            
            ed_count = len(editions) if editions else 0
            print(f'[{updated}] {title[:50]}... ({ed_count} ред.)')
            
        except Exception as e:
            conn.rollback()
            errors += 1
            print(f'Ошибка {law_id} ({title[:30]}): {e}')
    
    cur.close()
    conn.close()
    
    print(f'\n=== ГОТОВО ===')
    print(f'Обновлено законов: {updated}')
    print(f'Ошибок: {errors}')

if __name__ == '__main__':
    process_all_laws()
