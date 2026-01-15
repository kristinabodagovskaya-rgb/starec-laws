#!/usr/bin/env python3
"""
Синхронизация всех законов из codex.starec.ai
Загружает только те что имеют статьи (articles > 0)
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


def search_in_codex(title):
    """Поиск закона в codex по названию"""
    try:
        # Упрощаем название для поиска
        search_title = title.replace('РФ', '').replace('часть', '').strip()[:50]

        resp = requests.get(
            f"{CODEX_API}/search",
            params={"q": search_title, "limit": 3},
            timeout=15
        )
        resp.raise_for_status()
        data = resp.json()

        for r in data.get('results', []):
            if r.get('document_nd'):
                return r.get('document_nd'), r.get('document_title', '')

        return None, None
    except Exception as e:
        print(f"    Ошибка поиска: {e}")
        return None, None


def fetch_document(nd):
    """Получить документ из codex"""
    try:
        resp = requests.get(f"{CODEX_API}/documents/{nd}", timeout=60)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"    Ошибка загрузки: {e}")
        return None


def build_html(doc):
    """Собрать HTML из статей"""
    articles = doc.get('articles', [])
    if not articles:
        return None

    html_parts = []
    html_parts.append(f'<h1>{doc.get("title", "")}</h1>')

    if doc.get('number') and doc.get('sign_date'):
        html_parts.append(f'<p class="law-meta">№ {doc["number"]} от {doc["sign_date"]}</p>')

    for art in articles:
        art_num = art.get('number', '')
        art_title = art.get('title', '')
        art_content = art.get('content', '')

        html_parts.append(f'<div id="st{art_num}" class="article-section">')
        html_parts.append(f'<h3>Статья {art_num}. {art_title}</h3>')
        html_parts.append(f'<div class="article-content">{art_content}</div>')
        html_parts.append('</div>')

    return '\n'.join(html_parts)


def save_law(cursor, conn, law_id, full_text, doc):
    """Сохранить закон в БД"""
    cursor.execute("""
        UPDATE law_embeddings
        SET full_text = %s,
            law_number = COALESCE(%s, law_number),
            law_date = COALESCE(%s, law_date)
        WHERE id = %s
    """, (full_text, doc.get('number'), doc.get('sign_date'), law_id))

    # Сохраняем редакции
    editions = doc.get('editions', [])
    for ed in editions:
        cursor.execute("""
            INSERT INTO law_editions (law_id, edition_id, rdk, valid_from, change_reason, is_current)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (
            law_id,
            ed.get('id'),
            ed.get('rdk'),
            ed.get('valid_from'),
            ed.get('change_reason'),
            ed.get('rdk') == editions[0].get('rdk') if editions else False
        ))

    conn.commit()


def main():
    print("="*70)
    print("СИНХРОНИЗАЦИЯ ЗАКОНОВ ИЗ CODEX.STAREC.AI")
    print("="*70)

    conn = psycopg2.connect(**PG_CONFIG)
    cursor = conn.cursor()

    # Получаем все наши законы
    cursor.execute("""
        SELECT id, title, length(COALESCE(full_text, '')) as current_len
        FROM law_embeddings
        ORDER BY id
    """)
    laws = cursor.fetchall()

    print(f"Всего законов в нашей базе: {len(laws)}")
    print()

    loaded = 0
    skipped = 0
    not_found = 0
    errors = 0

    for law_id, title, current_len in laws:
        print(f"[{law_id}] {title[:50]}")

        # Ищем в codex
        nd, codex_title = search_in_codex(title)

        if not nd:
            print(f"    ❌ Не найден в codex")
            not_found += 1
            time.sleep(0.3)
            continue

        print(f"    Найден: nd={nd}")

        # Загружаем документ
        doc = fetch_document(nd)

        if not doc:
            errors += 1
            time.sleep(0.5)
            continue

        articles = doc.get('articles', [])

        if not articles:
            print(f"    ⚠️ Нет статей в codex (пусто)")
            skipped += 1
            time.sleep(0.3)
            continue

        # Собираем HTML
        html = build_html(doc)

        if not html:
            print(f"    ⚠️ Ошибка сборки HTML")
            errors += 1
            continue

        editions_count = len(doc.get('editions', []))

        print(f"    ✅ {len(articles)} статей, {editions_count} редакций, {len(html)} символов")

        # Сохраняем
        save_law(cursor, conn, law_id, html, doc)
        loaded += 1

        time.sleep(0.5)

    cursor.close()
    conn.close()

    print()
    print("="*70)
    print("ИТОГИ:")
    print(f"  Загружено: {loaded}")
    print(f"  Пустых в codex: {skipped}")
    print(f"  Не найдено: {not_found}")
    print(f"  Ошибок: {errors}")
    print("="*70)


if __name__ == "__main__":
    main()
