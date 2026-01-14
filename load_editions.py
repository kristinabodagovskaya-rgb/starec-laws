#!/usr/bin/env python3
"""
Script to load law editions from Consultant.ru
Loads historical versions of laws into law_editions table

Usage:
    python load_editions.py --law-id 123 --doc-id LAW123456
    python load_editions.py --gk   # Load all editions of Civil Code
    python load_editions.py --ozpp # Load all editions of Consumer Protection Law
"""

import psycopg2
import requests
from bs4 import BeautifulSoup
import time
import re
import argparse
from datetime import datetime
import json

# Database config - same as app_garant.py
PG_CONFIG = {
    'host': '127.0.0.1',
    'port': 5432,
    'database': 'starec_laws',
    'user': 'flaskapp',
    'password': 'flaskpass123'
}

# Headers for requests
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
}

# Known laws with their Consultant.ru document IDs
KNOWN_LAWS = {
    'gk1': {
        'name': 'Гражданский кодекс Российской Федерации (часть первая)',
        'doc_id': 'LAW5142',
        'law_id': None  # Will be determined from database
    },
    'gk2': {
        'name': 'Гражданский кодекс Российской Федерации (часть вторая)',
        'doc_id': 'LAW9027',
        'law_id': None
    },
    'gk3': {
        'name': 'Гражданский кодекс Российской Федерации (часть третья)',
        'doc_id': 'LAW34154',
        'law_id': None
    },
    'gk4': {
        'name': 'Гражданский кодекс Российской Федерации (часть четвертая)',
        'doc_id': 'LAW64629',
        'law_id': None
    },
    'ozpp': {
        'name': 'О защите прав потребителей',
        'doc_id': 'LAW305',
        'law_id': None
    }
}


def find_law_id_by_title(cursor, title_pattern):
    """Find law ID in database by title pattern"""
    cursor.execute("""
        SELECT id, title FROM law_embeddings
        WHERE title ILIKE %s
        LIMIT 1
    """, (f'%{title_pattern}%',))
    row = cursor.fetchone()
    if row:
        return row[0]
    return None


def get_edition_list(doc_id):
    """
    Get list of available editions from Consultant.ru
    Returns list of dicts with date and URL
    """
    url = f"https://www.consultant.ru/document/{doc_id}/"

    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching edition list: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    editions = []

    # Look for edition links - they're usually in a dropdown or list
    # Pattern 1: Look for links with "ed=" parameter
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        if 'ed=' in href or '/ed/' in href:
            text = link.get_text(strip=True)
            # Extract date from text
            date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', text)
            if date_match:
                editions.append({
                    'date': date_match.group(1),
                    'url': href if href.startswith('http') else f"https://www.consultant.ru{href}",
                    'description': text
                })

    # Pattern 2: Look for edition selector
    edition_selector = soup.find('select', {'name': 'edition'}) or soup.find('div', class_='doc-versions')
    if edition_selector:
        for option in edition_selector.find_all(['option', 'a']):
            text = option.get_text(strip=True)
            value = option.get('value') or option.get('href', '')
            date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', text)
            if date_match and value:
                editions.append({
                    'date': date_match.group(1),
                    'url': value if value.startswith('http') else f"https://www.consultant.ru{value}",
                    'description': text
                })

    # Pattern 3: Look for "Все редакции" link
    all_editions_link = soup.find('a', string=re.compile('редакц', re.I))
    if all_editions_link:
        href = all_editions_link.get('href', '')
        if href:
            editions_url = href if href.startswith('http') else f"https://www.consultant.ru{href}"
            print(f"Found editions page: {editions_url}")
            editions.extend(get_editions_from_page(editions_url))

    return editions


def get_editions_from_page(url):
    """Get editions from dedicated editions page"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching editions page: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    editions = []

    # Look for edition links
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        text = link.get_text(strip=True)
        date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', text)
        if date_match:
            editions.append({
                'date': date_match.group(1),
                'url': href if href.startswith('http') else f"https://www.consultant.ru{href}",
                'description': text
            })

    return editions


def fetch_edition_text(url):
    """Fetch full text of a specific edition"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=60)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching edition text: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    # Find main content - Consultant.ru specific selectors
    content = soup.find('div', class_='document-page__content')
    if not content:
        content = soup.find('div', class_='text')
    if not content:
        content = soup.find('article')
    if not content:
        # Fallback to body
        content = soup.find('body')

    if content:
        # Clean up navigation and other non-content elements
        for elem in content.find_all(['nav', 'script', 'style', 'header', 'footer']):
            elem.decompose()
        return str(content)

    return None


def save_edition(cursor, law_id, revision_date, description, full_text):
    """Save edition to database"""
    # Check if edition already exists
    cursor.execute("""
        SELECT id FROM law_editions
        WHERE law_id = %s AND revision_date = %s
    """, (law_id, revision_date))

    existing = cursor.fetchone()

    if existing:
        # Update existing
        cursor.execute("""
            UPDATE law_editions
            SET revision_description = %s, full_text = %s
            WHERE id = %s
        """, (description, full_text, existing[0]))
        return 'updated', existing[0]
    else:
        # Insert new
        cursor.execute("""
            INSERT INTO law_editions (law_id, revision_date, revision_description, full_text)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (law_id, revision_date, description, full_text))
        new_id = cursor.fetchone()[0]
        return 'inserted', new_id


def ensure_editions_table(cursor):
    """Create law_editions table if not exists"""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS law_editions (
            id SERIAL PRIMARY KEY,
            law_id INTEGER NOT NULL REFERENCES law_embeddings(id),
            revision_date DATE NOT NULL,
            revision_description TEXT,
            full_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(law_id, revision_date)
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_law_editions_law_id ON law_editions(law_id)
    """)


def load_law_editions(law_key, conn, cursor):
    """Load all editions for a specific law"""
    law_info = KNOWN_LAWS.get(law_key)
    if not law_info:
        print(f"Unknown law key: {law_key}")
        return

    # Find law ID in database
    law_id = find_law_id_by_title(cursor, law_info['name'].split('(')[0].strip())
    if not law_id:
        print(f"Law not found in database: {law_info['name']}")
        return

    print(f"\nLoading editions for: {law_info['name']}")
    print(f"Database law_id: {law_id}")
    print(f"Consultant.ru doc_id: {law_info['doc_id']}")

    # Get list of editions
    editions = get_edition_list(law_info['doc_id'])
    print(f"Found {len(editions)} editions")

    if not editions:
        print("No editions found. Manual scraping may be needed.")
        return

    # Ensure table exists
    ensure_editions_table(cursor)
    conn.commit()

    # Load each edition
    loaded = 0
    for i, edition in enumerate(editions):
        print(f"\n[{i+1}/{len(editions)}] {edition['date']}: {edition['description']}")

        # Parse date
        try:
            date_parts = edition['date'].split('.')
            revision_date = f"{date_parts[2]}-{date_parts[1]}-{date_parts[0]}"  # YYYY-MM-DD
        except Exception as e:
            print(f"  Error parsing date: {e}")
            continue

        # Fetch full text
        full_text = fetch_edition_text(edition['url'])
        if not full_text:
            print("  Failed to fetch text")
            continue

        # Save to database
        try:
            action, edition_id = save_edition(
                cursor, law_id, revision_date,
                edition['description'], full_text
            )
            conn.commit()
            print(f"  {action.upper()} (id={edition_id})")
            loaded += 1
        except Exception as e:
            print(f"  Error saving: {e}")
            conn.rollback()

        # Rate limiting
        time.sleep(1)

    print(f"\nDone! Loaded {loaded}/{len(editions)} editions")


def main():
    parser = argparse.ArgumentParser(description='Load law editions from Consultant.ru')
    parser.add_argument('--law-id', type=int, help='Database law ID')
    parser.add_argument('--doc-id', help='Consultant.ru document ID (e.g., LAW5142)')
    parser.add_argument('--gk', action='store_true', help='Load Civil Code (all parts)')
    parser.add_argument('--gk1', action='store_true', help='Load Civil Code Part 1')
    parser.add_argument('--gk2', action='store_true', help='Load Civil Code Part 2')
    parser.add_argument('--gk3', action='store_true', help='Load Civil Code Part 3')
    parser.add_argument('--gk4', action='store_true', help='Load Civil Code Part 4')
    parser.add_argument('--ozpp', action='store_true', help='Load Consumer Protection Law')
    parser.add_argument('--list', action='store_true', help='List available laws in database')

    args = parser.parse_args()

    conn = psycopg2.connect(**PG_CONFIG)
    cursor = conn.cursor()

    try:
        if args.list:
            cursor.execute("""
                SELECT id, title FROM law_embeddings
                WHERE full_text IS NOT NULL
                ORDER BY title LIMIT 30
            """)
            print("Laws in database:")
            for row in cursor.fetchall():
                print(f"  [{row[0]}] {row[1][:80]}...")
            return

        if args.gk:
            for key in ['gk1', 'gk2', 'gk3', 'gk4']:
                load_law_editions(key, conn, cursor)
        elif args.gk1:
            load_law_editions('gk1', conn, cursor)
        elif args.gk2:
            load_law_editions('gk2', conn, cursor)
        elif args.gk3:
            load_law_editions('gk3', conn, cursor)
        elif args.gk4:
            load_law_editions('gk4', conn, cursor)
        elif args.ozpp:
            load_law_editions('ozpp', conn, cursor)
        else:
            print("Usage: python load_editions.py --gk or --ozpp")
            print("Run with --help for more options")

    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    main()
