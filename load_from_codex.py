#!/usr/bin/env python3
"""
Скрипт загрузки законов с codex.starec.ai
Загружает тексты и редакции в нашу базу
"""

import requests
import psycopg2
import time
import re

CODEX_API = "https://codex.starec.ai/api"

PG_CONFIG = {
    'host': '127.0.0.1',
    'port': 5432,
    'database': 'starec_laws',
    'user': 'flaskapp',
    'password': 'flaskpass123'
}

# Маппинг наших законов на nd в codex
# Формат: our_id: (nd, title_pattern)
LAWS_MAPPING = {
    # Пустые законы (13 штук)
    44: (None, "обязательном страховании ответственности перевозчика"),
    50: (None, "садоводстве и огородничестве"),
    52: (102066375, "О минимальном размере оплаты труда"),
    53: (None, "профессиональных союзах"),
    55: (None, "специальной оценке условий труда"),
    71: (None, "развитии малого и среднего предпринимательства"),
    78: (None, "судебной системе"),
    84: (None, "нотариате"),
    86: (None, "Федеральной службе безопасности"),
    95: (None, "беженцах"),
    111: (None, "уполномоченном по правам человека"),
    113: (None, "уполномоченном по правам ребёнка"),
    120: (None, "средствах массовой информации"),
    # Основные законы
    123: (102014512, "О защите прав потребителей"),
}


def search_law_nd(title_pattern):
    """Поиск nd закона по названию"""
    try:
        resp = requests.get(
            f"{CODEX_API}/search",
            params={"q": title_pattern, "limit": 5},
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()

        for r in data.get('results', []):
            doc_title = r.get('document_title', '')
            if doc_title and title_pattern.lower() in doc_title.lower():
                return r.get('document_nd')

        # Если не нашли точное совпадение, берём первый результат
        if data.get('results'):
            return data['results'][0].get('document_nd')

    except Exception as e:
        print(f"  Ошибка поиска: {e}")
    return None


def fetch_document(nd):
    """Получить документ с codex.starec.ai"""
    try:
        resp = requests.get(f"{CODEX_API}/documents/{nd}", timeout=60)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  Ошибка загрузки документа {nd}: {e}")
        return None


def build_html_from_articles(doc):
    """Собрать HTML из статей документа"""
    articles = doc.get('articles', [])
    if not articles:
        return None

    html_parts = []

    # Заголовок
    html_parts.append(f'<h1>{doc.get("title", "")}</h1>')

    # Метаданные
    if doc.get('number'):
        html_parts.append(f'<p class="law-meta">№ {doc["number"]} от {doc.get("sign_date", "")}</p>')

    # Статьи
    for art in articles:
        art_num = art.get('number', '')
        art_title = art.get('title', '')
        art_content = art.get('content', '')

        # Обёртка для статьи
        html_parts.append(f'<div id="st{art_num}" class="article-section">')
        html_parts.append(f'<h3>Статья {art_num}. {art_title}</h3>')
        html_parts.append(f'<div class="article-content">{art_content}</div>')
        html_parts.append('</div>')

    return '\n'.join(html_parts)


def save_law_to_db(cursor, law_id, full_text, doc_data):
    """Сохранить закон в базу"""
    cursor.execute("""
        UPDATE law_embeddings
        SET full_text = %s,
            law_number = COALESCE(law_number, %s),
            law_date = COALESCE(law_date, %s)
        WHERE id = %s
    """, (
        full_text,
        doc_data.get('number'),
        doc_data.get('sign_date'),
        law_id
    ))


def save_editions_to_db(cursor, law_id, editions):
    """Сохранить редакции в базу"""
    for ed in editions:
        cursor.execute("""
            INSERT INTO law_editions (law_id, edition_id, rdk, valid_from, change_reason, is_current)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (law_id, edition_id) DO UPDATE
            SET rdk = EXCLUDED.rdk,
                valid_from = EXCLUDED.valid_from,
                change_reason = EXCLUDED.change_reason
        """, (
            law_id,
            ed.get('id'),
            ed.get('rdk'),
            ed.get('valid_from'),
            ed.get('change_reason'),
            ed.get('rdk') == editions[0].get('rdk')  # Первая = текущая
        ))


def load_law(cursor, conn, law_id, nd=None, title_pattern=None):
    """Загрузить один закон"""
    print(f"\n{'='*60}")
    print(f"Загрузка закона ID={law_id}")

    # Если nd не указан, ищем по названию
    if not nd and title_pattern:
        print(f"  Поиск по: {title_pattern}")
        nd = search_law_nd(title_pattern)
        if nd:
            print(f"  Найден nd={nd}")
        else:
            print(f"  ❌ Не найден!")
            return False

    if not nd:
        print(f"  ❌ Нет nd!")
        return False

    # Загружаем документ
    print(f"  Загружаю документ nd={nd}...")
    doc = fetch_document(nd)

    if not doc:
        print(f"  ❌ Ошибка загрузки!")
        return False

    print(f"  Название: {doc.get('title')}")
    print(f"  Статей: {len(doc.get('articles', []))}")
    print(f"  Редакций: {len(doc.get('editions', []))}")

    # Собираем HTML
    full_text = build_html_from_articles(doc)
    if not full_text:
        print(f"  ❌ Нет статей!")
        return False

    print(f"  HTML: {len(full_text)} символов")

    # Сохраняем закон
    save_law_to_db(cursor, law_id, full_text, doc)

    # Сохраняем редакции
    editions = doc.get('editions', [])
    if editions:
        save_editions_to_db(cursor, law_id, editions)
        print(f"  ✅ Сохранено {len(editions)} редакций")

    conn.commit()
    print(f"  ✅ Закон сохранён!")
    return True


def main():
    print("="*60)
    print("ЗАГРУЗКА ЗАКОНОВ С CODEX.STAREC.AI")
    print("="*60)

    conn = psycopg2.connect(**PG_CONFIG)
    cursor = conn.cursor()

    # Получаем список пустых законов
    cursor.execute("""
        SELECT id, title FROM law_embeddings
        WHERE full_text IS NULL OR length(full_text) = 0
        ORDER BY id
    """)
    empty_laws = cursor.fetchall()
    print(f"\nПустых законов: {len(empty_laws)}")

    loaded = 0
    failed = 0

    for law_id, title in empty_laws:
        print(f"\n[{law_id}] {title}")

        # Ищем маппинг
        mapping = LAWS_MAPPING.get(law_id)
        if mapping:
            nd, pattern = mapping
        else:
            nd = None
            # Извлекаем ключевые слова из названия
            pattern = re.sub(r'^(О|Об)\s+', '', title)
            pattern = pattern[:50]

        success = load_law(cursor, conn, law_id, nd, pattern)

        if success:
            loaded += 1
        else:
            failed += 1

        time.sleep(1)  # Rate limiting

    cursor.close()
    conn.close()

    print("\n" + "="*60)
    print("ИТОГИ")
    print("="*60)
    print(f"Загружено: {loaded}")
    print(f"Ошибок: {failed}")


if __name__ == "__main__":
    main()
