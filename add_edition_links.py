#!/usr/bin/env python3
"""
Добавление ссылок на редакции в блок 'Редакции документа'.
Ссылки серые, ведут на страницу редакции.
"""

import psycopg2
import re

DB_CONFIG = {
    'database': 'starec_laws',
    'user': 'flaskapp', 
    'password': 'flaskpass123',
    'host': 'localhost'
}

def generate_editions_html(law_id, editions):
    """Генерирует HTML блок редакций со ссылками"""
    if not editions:
        return ''
    
    html = []
    html.append(f'<details class="law-editions-block">')
    html.append(f'<summary>Редакции документа ({len(editions)})</summary>')
    html.append('<div class="law-editions-list">')
    
    for ed_id, rdk, valid_from, change_reason in editions:
        date_str = str(valid_from) if valid_from else ''
        reason_str = change_reason or ''
        
        # Ссылка на редакцию
        html.append(f'<div class="law-edition-item">')
        html.append(f'<a href="/law/{law_id}/edition/{ed_id}" class="edition-link">')
        html.append(f'<span class="edition-date">{date_str}</span>')
        html.append(f'<span class="edition-title">{reason_str}</span>')
        html.append('</a>')
        html.append('</div>')
    
    html.append('</div>')
    html.append('</details>')
    
    return '\n'.join(html)

def update_law_with_edition_links(cur, law_id, title, full_text, editions):
    """Обновляет закон, заменяя блок редакций на версию со ссылками"""
    
    if not full_text:
        return False
    
    # Генерируем новый блок редакций
    new_editions_html = generate_editions_html(law_id, editions)
    
    # Удаляем старый блок редакций
    # Паттерн для поиска существующего блока
    pattern = r'<details class="law-editions-block">.*?</details>'
    
    if re.search(pattern, full_text, re.DOTALL):
        # Заменяем существующий блок
        new_text = re.sub(pattern, new_editions_html, full_text, flags=re.DOTALL)
    else:
        # Вставляем после law-header
        header_end = full_text.find('</div>', full_text.find('law-header'))
        if header_end > 0:
            insert_pos = header_end + 6  # После </div>
            new_text = full_text[:insert_pos] + '\n' + new_editions_html + full_text[insert_pos:]
        else:
            new_text = full_text
    
    if new_text != full_text:
        cur.execute('UPDATE law_embeddings SET full_text = %s WHERE id = %s', (new_text, law_id))
        return True
    return False

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Получаем все законы
    cur.execute('SELECT id, title, full_text FROM law_embeddings ORDER BY id')
    laws = cur.fetchall()
    
    print(f'Законов: {len(laws)}')
    print()
    
    updated = 0
    for law_id, title, full_text in laws:
        # Получаем редакции для этого закона
        cur.execute('''
            SELECT id, rdk, valid_from, change_reason
            FROM law_editions
            WHERE law_id = %s
            ORDER BY valid_from DESC
        ''', (law_id,))
        editions = cur.fetchall()
        
        if not editions:
            continue
        
        if update_law_with_edition_links(cur, law_id, title, full_text, editions):
            updated += 1
            print(f'[{law_id}] {title[:40]}... - {len(editions)} редакций ✓')
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f'\nОбновлено законов: {updated}')

if __name__ == '__main__':
    main()
