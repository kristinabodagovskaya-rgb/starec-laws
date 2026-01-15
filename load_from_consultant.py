#!/usr/bin/env python3
"""
Загрузка законов с Консультант.ру
"""

import requests
from bs4 import BeautifulSoup
import psycopg2
import re
import time

PG_CONFIG = {
    'host': '127.0.0.1',
    'port': 5432,
    'database': 'starec_laws',
    'user': 'flaskapp',
    'password': 'flaskpass123'
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}

# Маппинг: law_id -> consultant_law_id
CONSULTANT_LAWS = {
    44: "178893",   # Об обязательном страховании ответственности перевозчика
    52: "66375",    # О минимальном размере оплаты труда
    55: "170672",   # О специальной оценке условий труда
    71: "115928",   # О развитии малого и среднего предпринимательства
    78: "46697",    # ФКЗ О судебной системе
    84: "17327",    # Основы законодательства о нотариате
    95: "44519",    # О беженцах
    113: "95188",   # Об уполномоченном по правам ребёнка
    120: "1511",    # О средствах массовой информации
}


def fetch_from_consultant(consultant_id):
    """Загрузить закон с Консультант.ру"""
    url = f"https://www.consultant.ru/document/cons_doc_LAW_{consultant_id}/"
    print(f"  Загружаю: {url}")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        print(f"  Ошибка: {e}")
        return None, None

    soup = BeautifulSoup(resp.text, 'html.parser')

    # Удаляем лишнее
    for tag in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside']):
        tag.decompose()

    # Ищем заголовок
    title = ""
    title_elem = soup.find('h1') or soup.find(class_='document-page__title')
    if title_elem:
        title = title_elem.get_text(strip=True)

    # Ищем контент
    content = soup.find('div', class_='document-page__content')
    if not content:
        content = soup.find('div', class_='doc-body')
    if not content:
        content = soup.find('article')
    if not content:
        # Пробуем найти любой контент
        content = soup.find('div', id='document')

    if not content:
        print(f"  Контент не найден!")
        return title, None

    html = str(content)
    print(f"  Получено: {len(html)} символов")

    return title, html


def wrap_articles(html):
    """Обернуть статьи в div с id"""
    # Ищем статьи по паттерну "Статья N."
    pattern = r'(<[^>]*>)*\s*(Статья\s+(\d+[\d\.]*)[\.:])'

    matches = list(re.finditer(pattern, html, re.IGNORECASE))

    if not matches:
        return html

    new_html = ""
    last_end = 0

    for i, match in enumerate(matches):
        start = match.start()
        art_num = match.group(3).replace('.', '_')

        # Добавить предыдущий контент
        if i > 0:
            new_html += html[last_end:start]
            new_html += '</div>\n\n'

        # Начать новую статью
        new_html += f'\n<div id="st{art_num}" class="article-section">\n'
        last_end = start

    # Добавить последнюю статью
    new_html += html[last_end:]
    new_html += '</div>\n'

    return new_html


def save_to_db(law_id, html):
    """Сохранить в базу"""
    conn = psycopg2.connect(**PG_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE law_embeddings SET full_text = %s WHERE id = %s
    """, (html, law_id))

    conn.commit()
    cursor.close()
    conn.close()


def main():
    print("="*60)
    print("ЗАГРУЗКА С КОНСУЛЬТАНТ.РУ")
    print("="*60)

    loaded = 0
    failed = 0

    for law_id, consultant_id in CONSULTANT_LAWS.items():
        print(f"\n[{law_id}] consultant_id={consultant_id}")

        title, html = fetch_from_consultant(consultant_id)

        if not html:
            print(f"  ❌ Не загружено!")
            failed += 1
            continue

        # Оборачиваем статьи
        html = wrap_articles(html)

        # Сохраняем
        save_to_db(law_id, html)
        print(f"  ✅ Сохранено!")
        loaded += 1

        time.sleep(2)  # Rate limit

    print(f"\n{'='*60}")
    print(f"Загружено: {loaded}, Ошибок: {failed}")


if __name__ == "__main__":
    main()
