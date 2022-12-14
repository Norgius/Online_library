import os
import sys
import argparse
import logging
from time import sleep
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from logging.handlers import RotatingFileHandler

import requests
import requests.exceptions
from tqdm import tqdm
from bs4 import BeautifulSoup
from pathvalidate import sanitize_filename

ENCODING = 'UTF-8'
logger = logging.getLogger(__file__)


def check_for_redirect(response):
    if response.history:
        raise requests.exceptions.HTTPError(
            f'Cо страницы - {response.history[0].url}\n'
            f'произошёл редирект на страницу - {response.url}'
        )


def parse_book_page(html_book_page):
    soup = BeautifulSoup(html_book_page.text, 'lxml')
    title_and_author = soup.select_one('body h1')
    title, author = title_and_author.text.split('::')
    title = sanitize_filename(title).strip()
    author = sanitize_filename(author).strip()
    comments_blog = soup.select('.texts')
    comments = [comment.span.string for comment in comments_blog]
    book_genres = soup.select('span.d_book a')
    genres = [genre.text for genre in book_genres]
    img_src = soup.select_one('.bookimage img').get('src')
    book = {'title': title, 'author': author, 'comments': comments,
            'genres': genres, 'img_src': img_src}
    return book


def get_file_extension(url):
    parsed_url = urlsplit(url)
    filename = os.path.split(parsed_url.path)[1]
    return os.path.splitext(filename)[1]


def download_image(img_link, book_id, dest_folder='', folder='images'):
    dest_folder = os.path.join(dest_folder, folder)
    Path(dest_folder).mkdir(parents=True, exist_ok=True)
    response = requests.get(img_link, timeout=10)
    response.raise_for_status()
    if img_link.endswith('nopic.gif'):
        img_name = 'nopic.gif'
    else:
        extension = get_file_extension(img_link)
        img_name = f'{book_id}{extension}'
    file_path = os.path.join(dest_folder, img_name)
    with open(file_path, 'wb') as file:
        file.write(response.content)
    return file_path


def save_text(response, filename, dest_folder='', folder='books'):
    dest_folder = os.path.join(dest_folder, folder)
    Path(dest_folder).mkdir(parents=True, exist_ok=True)
    filename = sanitize_filename(filename).strip()
    file_path = os.path.join(dest_folder, f'{filename}.txt')
    with open(file_path, 'w', encoding=ENCODING) as file:
        file.write(response.text)
    return file_path


def get_books(start_id, end_id):
    for book_id in tqdm(range(start_id, end_id)):
        url = 'https://tululu.org/'
        params = {'id': book_id}
        try:
            response = requests.get(url=f'{url}txt.php',
                                    params=params, timeout=10)
            response.raise_for_status()
            check_for_redirect(response)
            html_book_page = requests.get(url=f'{url}b{book_id}/', timeout=10)
            html_book_page.raise_for_status()
            check_for_redirect(html_book_page)
            book = parse_book_page(html_book_page)
            book_file_path = save_text(
                response,
                f'{book_id}. {book.get("title")}'
            )
            img_link = urljoin(html_book_page.url, book.get('img_src'))
            img_file_path = download_image(img_link, book_id)
            book['book_path'] = book_file_path
            book['img_src'] = img_file_path
        except requests.exceptions.HTTPError as http_er:
            logger.info(f'Невозможно загрузить книгу по данному '
                        f'book_id = {book_id}\n{http_er}\n')
            sys.stderr.write(f'{http_er}\n\n')
            continue
        except requests.exceptions.ConnectionError as connect_er:
            logger.warning(f'Произошёл сетевой сбой на книге с данным '
                           f'book_id = {book_id}\n{connect_er}\n')
            sys.stderr.write(f'{connect_er}\n\n')
            sleep(15)
            continue
        print(f'Название: {book.get("title")}')
        print(f'Автор: {book.get("author")}\n')


def main():
    logging.basicConfig(
        filename='app.log',
        filemode='w',
        level=logging.INFO,
        format='%(name)s - %(levelname)s - %(asctime)s - %(message)s'
    )
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler('app.log', maxBytes=15000, backupCount=2)
    logger.addHandler(handler)
    parser = argparse.ArgumentParser(
        description='Скачивает книги в указанном диапазоне'
    )
    parser.add_argument('start_id', type=int,
                        help='Начало диапазона')
    parser.add_argument('end_id', type=int,
                        help='Конец диапазона')
    args = parser.parse_args()
    get_books(args.start_id, args.end_id)


if __name__ == '__main__':
    main()
