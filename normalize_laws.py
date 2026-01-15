#!/usr/bin/env python3
"""
Скрипт для приведения законов к единому стилю
Конвертирует HTML из разных источников в унифицированный формат
"""

import re
import html
from bs4 import BeautifulSoup, NavigableString
import psycopg2
from psycopg2.extras import RealDictCursor


# Подключение к БД
DB_CONFIG = {
    'host': '127.0.0.1',
    'dbname': 'starec_laws',
    'user': 'flaskapp',
    'password': 'flaskpass123'
}


class LawNormalizer:
    """Нормализатор текста законов"""

    def __init__(self):
        # Паттерны для распознавания структуры
        self.patterns = {
            # Части закона
            'part': re.compile(
                r'^(ЧАСТЬ|Часть)\s+([IVXLCDM]+|[А-Яа-я]+|\d+)\.?\s*(.*)$',
                re.IGNORECASE | re.MULTILINE
            ),
            # Разделы
            'section': re.compile(
                r'^(РАЗДЕЛ|Раздел)\s+([IVXLCDM]+|\d+)\.?\s*(.*)$',
                re.IGNORECASE | re.MULTILINE
            ),
            # Главы
            'chapter': re.compile(
                r'^(ГЛАВА|Глава)\s+([IVXLCDM]+|\d+)\.?\s*(.*)$',
                re.IGNORECASE | re.MULTILINE
            ),
            # Параграфы
            'paragraph_section': re.compile(
                r'^§\s*(\d+)\.?\s*(.*)$',
                re.MULTILINE
            ),
            # Статьи
            'article': re.compile(
                r'^(Статья|СТАТЬЯ)\s+(\d+(?:\.\d+)?)\.?\s*(.*)$',
                re.IGNORECASE | re.MULTILINE
            ),
            # Нумерованные пункты
            'numbered_item': re.compile(
                r'^(\d+)\.\s+(.+)$',
                re.MULTILINE
            ),
            # Буквенные подпункты
            'letter_item': re.compile(
                r'^([а-яё])\)\s+(.+)$',
                re.MULTILINE
            ),
            # Ссылки на законы
            'law_reference': re.compile(
                r'(Федеральн\w+\s+закон\w*|закон\w*)\s+от\s+(\d{1,2}[.\s]\w+[.\s]\d{4}\s*(?:г\.?)?)\s*[№N]\s*(\d+[-\w]*)',
                re.IGNORECASE
            ),
            # Ссылки на статьи
            'article_reference': re.compile(
                r'(стать[яией]+|ст\.)\s*(\d+(?:\.\d+)?)',
                re.IGNORECASE
            ),
        }

    def clean_html(self, html_content):
        """Очистка HTML от лишних тегов и атрибутов"""
        if not html_content:
            return ''

        soup = BeautifulSoup(html_content, 'html.parser')

        # Удаляем скрипты и стили
        for tag in soup.find_all(['script', 'style', 'meta', 'link']):
            tag.decompose()

        # Удаляем комментарии
        for comment in soup.find_all(string=lambda text: isinstance(text, NavigableString) and text.strip().startswith('<!--')):
            comment.extract()

        # Удаляем пустые теги
        for tag in soup.find_all():
            if tag.name not in ['br', 'hr', 'img'] and not tag.get_text(strip=True) and not tag.find_all(['img', 'br', 'hr']):
                tag.decompose()

        return str(soup)

    def extract_text_structure(self, html_content):
        """Извлечение структурированного текста из HTML"""
        soup = BeautifulSoup(html_content, 'html.parser')

        # Получаем чистый текст с сохранением структуры
        text = soup.get_text(separator='\n')

        # Убираем множественные пробелы и переносы
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()

        return text

    def parse_law_structure(self, text):
        """Парсинг структуры закона"""
        structure = {
            'header': None,
            'preamble': None,
            'parts': [],
            'chapters': [],
            'articles': [],
            'appendices': []
        }

        lines = text.split('\n')
        current_part = None
        current_chapter = None
        current_article = None
        current_content = []

        for line in lines:
            line = line.strip()
            if not line:
                if current_content:
                    current_content.append('')
                continue

            # Проверяем на часть
            part_match = self.patterns['part'].match(line)
            if part_match:
                if current_article:
                    current_article['content'] = '\n'.join(current_content)
                    structure['articles'].append(current_article)
                    current_content = []

                current_part = {
                    'number': part_match.group(2),
                    'title': part_match.group(3).strip(),
                    'type': 'part'
                }
                structure['parts'].append(current_part)
                continue

            # Проверяем на главу
            chapter_match = self.patterns['chapter'].match(line)
            if chapter_match:
                if current_article:
                    current_article['content'] = '\n'.join(current_content)
                    structure['articles'].append(current_article)
                    current_content = []

                current_chapter = {
                    'number': chapter_match.group(2),
                    'title': chapter_match.group(3).strip(),
                    'type': 'chapter'
                }
                structure['chapters'].append(current_chapter)
                continue

            # Проверяем на статью
            article_match = self.patterns['article'].match(line)
            if article_match:
                if current_article:
                    current_article['content'] = '\n'.join(current_content)
                    structure['articles'].append(current_article)
                    current_content = []

                current_article = {
                    'number': article_match.group(2),
                    'title': article_match.group(3).strip(),
                    'chapter': current_chapter['number'] if current_chapter else None,
                    'part': current_part['number'] if current_part else None,
                    'content': ''
                }
                continue

            # Добавляем контент к текущей статье
            current_content.append(line)

        # Сохраняем последнюю статью
        if current_article:
            current_article['content'] = '\n'.join(current_content)
            structure['articles'].append(current_article)

        return structure

    def format_article_content(self, content):
        """Форматирование содержимого статьи"""
        lines = content.split('\n')
        formatted_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                formatted_lines.append('')
                continue

            # Нумерованный пункт
            num_match = self.patterns['numbered_item'].match(line)
            if num_match:
                formatted_lines.append(
                    f'<p class="law-paragraph"><span class="law-paragraph-number">{num_match.group(1)}.</span> {num_match.group(2)}</p>'
                )
                continue

            # Буквенный подпункт
            letter_match = self.patterns['letter_item'].match(line)
            if letter_match:
                formatted_lines.append(
                    f'<p class="law-subparagraph"><span class="law-subparagraph-letter">{letter_match.group(1)})</span> {letter_match.group(2)}</p>'
                )
                continue

            # Обычный абзац
            formatted_lines.append(f'<p class="law-paragraph">{line}</p>')

        return '\n'.join(formatted_lines)

    def add_law_references(self, html_content):
        """Добавление ссылок на законы"""
        # Ссылки на федеральные законы
        def law_ref_replace(match):
            full_match = match.group(0)
            return f'<a href="#" class="law-link" data-law="{html.escape(full_match)}">{full_match}</a>'

        html_content = self.patterns['law_reference'].sub(law_ref_replace, html_content)

        # Ссылки на статьи
        def article_ref_replace(match):
            full_match = match.group(0)
            article_num = match.group(2)
            return f'<a href="#article-{article_num}" class="law-internal-link">{full_match}</a>'

        html_content = self.patterns['article_reference'].sub(article_ref_replace, html_content)

        return html_content

    def build_unified_html(self, law_title, structure):
        """Построение унифицированного HTML"""
        html_parts = []

        # Начало документа
        html_parts.append('<div class="law-document">')

        # Заголовок
        html_parts.append('<div class="law-header">')

        # Определяем тип документа
        law_type = "ФЕДЕРАЛЬНЫЙ ЗАКОН"
        if 'кодекс' in law_title.lower():
            law_type = "КОДЕКС РОССИЙСКОЙ ФЕДЕРАЦИИ"
        elif 'конституционный' in law_title.lower():
            law_type = "ФЕДЕРАЛЬНЫЙ КОНСТИТУЦИОННЫЙ ЗАКОН"

        html_parts.append(f'<div class="law-type">{law_type}</div>')
        html_parts.append(f'<h1 class="law-title">{html.escape(law_title)}</h1>')
        html_parts.append('</div>')

        # Главы и статьи
        current_chapter = None
        current_part = None

        for article in structure.get('articles', []):
            # Проверяем смену части
            if article.get('part') != current_part:
                current_part = article.get('part')
                part_info = next((p for p in structure.get('parts', []) if p['number'] == current_part), None)
                if part_info:
                    html_parts.append('<div class="law-part">')
                    html_parts.append(f'<div class="law-part-title">ЧАСТЬ {part_info["number"]}</div>')
                    if part_info.get('title'):
                        html_parts.append(f'<div class="law-part-name">{html.escape(part_info["title"])}</div>')
                    html_parts.append('</div>')

            # Проверяем смену главы
            if article.get('chapter') != current_chapter:
                current_chapter = article.get('chapter')
                chapter_info = next((c for c in structure.get('chapters', []) if c['number'] == current_chapter), None)
                if chapter_info:
                    html_parts.append('<div class="law-chapter">')
                    html_parts.append(f'<div class="law-chapter-title">ГЛАВА {chapter_info["number"]}</div>')
                    if chapter_info.get('title'):
                        html_parts.append(f'<div class="law-chapter-name">{html.escape(chapter_info["title"])}</div>')
                    html_parts.append('</div>')

            # Статья
            html_parts.append(f'<div class="law-article" id="article-{article["number"]}">')
            article_title = f'Статья {article["number"]}.'
            if article.get('title'):
                article_title += f' {html.escape(article["title"])}'
            html_parts.append(f'<div class="law-article-title">{article_title}</div>')
            html_parts.append('<div class="law-article-content">')
            html_parts.append(self.format_article_content(article.get('content', '')))
            html_parts.append('</div>')
            html_parts.append('</div>')

        html_parts.append('</div>')

        result = '\n'.join(html_parts)
        result = self.add_law_references(result)

        return result

    def normalize(self, html_content, law_title=''):
        """Главный метод нормализации"""
        # Очистка HTML
        cleaned = self.clean_html(html_content)

        # Извлечение текста
        text = self.extract_text_structure(cleaned)

        # Парсинг структуры
        structure = self.parse_law_structure(text)

        # Если структура не распознана, делаем простую нормализацию
        if not structure['articles']:
            return self.simple_normalize(cleaned, law_title)

        # Построение унифицированного HTML
        unified = self.build_unified_html(law_title, structure)

        return unified

    def simple_normalize(self, html_content, law_title=''):
        """Простая нормализация для документов без чёткой структуры"""
        soup = BeautifulSoup(html_content, 'html.parser')

        # Обёртываем в контейнер с классом
        wrapper = soup.new_tag('div')
        wrapper['class'] = 'law-document'

        # Добавляем заголовок если есть
        if law_title:
            header = soup.new_tag('div')
            header['class'] = 'law-header'

            title_tag = soup.new_tag('h1')
            title_tag['class'] = 'law-title'
            title_tag.string = law_title
            header.append(title_tag)

            wrapper.append(header)

        # Добавляем содержимое
        content_div = soup.new_tag('div')
        content_div['class'] = 'law-article-content'

        # Перемещаем всё содержимое
        for child in list(soup.children):
            content_div.append(child.extract() if hasattr(child, 'extract') else child)

        wrapper.append(content_div)

        # Применяем стили к параграфам
        for p in wrapper.find_all('p'):
            if 'class' not in p.attrs:
                p['class'] = ['law-paragraph']

        # Применяем стили к таблицам
        for table in wrapper.find_all('table'):
            if 'class' not in table.attrs:
                table['class'] = ['law-table']

        return str(wrapper)


def normalize_law_in_db(law_id, normalizer):
    """Нормализация одного закона в БД"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Получаем закон
        cur.execute("SELECT id, title, full_text FROM law_embeddings WHERE id = %s", (law_id,))
        law = cur.fetchone()

        if not law or not law['full_text']:
            print(f"Закон {law_id} не найден или пустой")
            return False

        print(f"Нормализую: {law['title']}")

        # Нормализуем
        normalized = normalizer.normalize(law['full_text'], law['title'])

        # Сохраняем
        cur.execute(
            "UPDATE law_embeddings SET full_text = %s WHERE id = %s",
            (normalized, law_id)
        )
        conn.commit()

        print(f"  Готово: {len(normalized)} символов")
        return True

    except Exception as e:
        print(f"  Ошибка: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def normalize_all_laws():
    """Нормализация всех законов"""
    normalizer = LawNormalizer()

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("""
            SELECT id, title, length(full_text) as len
            FROM law_embeddings
            WHERE full_text IS NOT NULL AND length(full_text) > 100
            ORDER BY id
        """)
        laws = cur.fetchall()

        print(f"Найдено {len(laws)} законов для нормализации\n")

        success = 0
        errors = 0

        for law in laws:
            if normalize_law_in_db(law['id'], normalizer):
                success += 1
            else:
                errors += 1

        print(f"\n{'='*50}")
        print(f"Итого: {success} успешно, {errors} ошибок")

    finally:
        cur.close()
        conn.close()


def preview_normalization(law_id):
    """Превью нормализации без сохранения"""
    normalizer = LawNormalizer()

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("SELECT id, title, full_text FROM law_embeddings WHERE id = %s", (law_id,))
        law = cur.fetchone()

        if not law:
            print("Закон не найден")
            return None

        print(f"Закон: {law['title']}")
        print(f"Исходный размер: {len(law['full_text'] or '')} символов\n")

        normalized = normalizer.normalize(law['full_text'], law['title'])

        print(f"Нормализованный размер: {len(normalized)} символов\n")
        print("="*50)
        print("ПРЕВЬЮ (первые 3000 символов):")
        print("="*50)
        print(normalized[:3000])

        return normalized

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == '--all':
            normalize_all_laws()
        elif sys.argv[1] == '--preview':
            law_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            preview_normalization(law_id)
        else:
            law_id = int(sys.argv[1])
            normalizer = LawNormalizer()
            normalize_law_in_db(law_id, normalizer)
    else:
        print("Использование:")
        print("  python normalize_laws.py --all        # нормализовать все законы")
        print("  python normalize_laws.py --preview N  # превью закона N")
        print("  python normalize_laws.py N            # нормализовать закон N")
