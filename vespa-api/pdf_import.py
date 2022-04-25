from pdfminer.high_level import extract_pages
from pdfminer.layout import LTPage, LTTextBox, LTTextLine, LTChar
from pdf2image import convert_from_path
import config
import sys
import argparse
import os
from langdetect import detect, LangDetectException
import stemmer
import vespa_util
import time
import json
from shutil import copyfile
import traceback
from datetime import datetime


warnings = []


class PdfImportError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message

    def __str__(self):
        return self.code, self.message

    def __repr__(self):
        return self.code, self.message


def main():
    wait_for_vespa()

    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=str, help="the folder containing PDFs to import", default="data")
    args = parser.parse_args()
    files = find_files(args.folder)

    if not os.path.isdir(config.metadata_path):
        os.mkdir(config.metadata_path)

    for (path, name) in progressBar(files, prefix="Importing", suffix="Completed", total=len(files)):
        path_parts = path.split(os.sep)
        collection = path_parts[1] if len(path_parts) > 2 else ''
        import_file(collection=collection, name=name, path=path)


def import_file(file=None, full_name=None, collection='', name=None, path=None):
    # TODO test and rework
    if file:
        name = '.'.join(full_name.rsplit('.')[:-1])
        path = f'{config.metadata_path}/{full_name}'

    doc_dir = f'{config.metadata_path}/{name}'
    if not os.path.isfile(f'{config.metadata_path}/{name}.pdf'):
        if file:
            file.save(path)
        else:
            copyfile(path, f'{config.metadata_path}/{name}.pdf')

    if not os.path.isdir(doc_dir):
        os.mkdir(doc_dir)

    try:
        for page_no, page_layout in enumerate(extract_pages(path)):
            try:
                image_path = f'{doc_dir}/{page_no}{config.convert_suffix}'
                thumb_path = f'{doc_dir}/{page_no}_thumb{config.convert_suffix}'
                json_path = f'{doc_dir}/{page_no}.json'

                image = convert_from_path(path, first_page=page_no + 1, last_page=page_no + 1)[0]
                if not os.path.isfile(image_path):
                    image.save(image_path, config.convert_type)
                else:
                    # Page already processed - Skip!
                    continue

                thumb = image.copy()
                if not os.path.isfile(thumb_path):
                    thumb.thumbnail((max(1500, page_layout.width), max(1500, page_layout.height)))
                    thumb.save(thumb_path, config.convert_type)

                text = page_layout.groups[0].get_text() if page_layout.groups else ''
                page_id = f'{name}_{page_no}'
                boxes = {}
                extract_page_word_boxes(page_layout, boxes)
                try:
                    stems = {stem: body['terms']
                             for stem, body in stemmer.map_stems_to_words(boxes.keys(), detect(text)).items()}
                except LangDetectException:
                    stems = {}
                page_data = {
                    'boxes': boxes,
                    'stems': stems,
                    'dimensions': {
                        'scale': image.width / page_layout.width,
                        'thumbScale': thumb.width / page_layout.width,
                        'origWidth': page_layout.width,
                        'origHeight': page_layout.height
                    }
                }

                with open(json_path, 'w') as file:
                    json.dump(page_data, file)
                vespa_util.feed(page_id, name, page_no, collection, text)
            except vespa_util.FeedException as e:
                raise e
            except Exception as e:
                print(f'\033[KFailed to import file: {name} | page: {page_no} - Cleaning up file artifacts!')
                __safe_remove(thumb_path)
                __safe_remove(image_path)
                __safe_remove(json_path)
                raise PdfImportError(400, f'Failed to import file: {name} | page: {page_no} - {str(e)}')
    except PdfImportError as e:
        raise e
    except vespa_util.FeedException as e:
        raise PdfImportError(500, e)
    except Exception as e:
        print(f'\033[KFailed to import file: {name}')
        raise PdfImportError(400, f'Failed to import file: {name} - {str(e)}')


def __safe_remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def wait_for_vespa():
    print('PDF Import - Waiting for vespa application to be up')
    while not vespa_util.health_check():
        time.sleep(0.5)
    print('PDF Import - vespa application is running - starting data import!')


def extract_page_word_boxes(layout_elem, boxes: dict):
    """
    Recursively extract bounding boxes for all words in a document page and store them in an inverted word-based index
    :param layout_elem: Currently inspected layout element
    :param boxes: Python dict to be used for storing the index
    """
    for elem in layout_elem._objs:
        if issubclass(type(elem), LTTextBox):
            extract_page_word_boxes(elem, boxes)
        elif issubclass(type(elem), LTTextLine):
            extract_line_word_boxes(elem, boxes)


def extract_line_word_boxes(line: LTTextLine, boxes: dict):
    """
    Build words from LTChar objects in a LTTextLine and add up the bounding boxes of the individual char objects
    :param line: Current line object
    :param boxes: Python dict to be used for storing the index
    :return:
    """
    current_word = ''
    box = [sys.maxsize, -sys.maxsize, sys.maxsize, -sys.maxsize]
    for elem in line:
        if is_valid_char(elem):
            char = elem.get_text()
            current_word += char
            expand_box(box, elem)
        else:
            # store word and reset variables
            try:
                if current_word != '':
                    current_word = current_word.lower()
                    boxes[current_word].append(box)
            except KeyError:
                boxes[current_word] = [box]
            current_word = ''
            box = [sys.maxsize, -sys.maxsize, sys.maxsize, -sys.maxsize]


def is_valid_char(elem):
    """
    Determines if a potential char element can be added to the current word's bounding box
    :param elem: potential LTChar element
    """
    if isinstance(elem, LTChar):
        char = elem.get_text()
        exclude_chars = [' ']
        include_chars = ['-', '&', '/']
        excluded = char in exclude_chars
        included = char in include_chars
        return not excluded and (char.isalnum() or included)
    return False


def expand_box(box, char: LTChar):
    """
    Expand the bounding box coordinates based on a new char object
    :param box: Current bounding box [x0, x1, y0, y1]
    :param char: New char added to current word
    """
    box[0] = min(box[0], char.x0)
    box[1] = max(box[1], char.x1)
    box[2] = min(box[2], char.y0)
    box[3] = max(box[3], char.y1)


def find_files(folder, suffix=".pdf"):
    """
    Recursively walk a folder and collect occurrences of specific file type
    :param folder: Folder to recursively search
    :param suffix: File ending to filter file type
    :return: List of matching file path strings
    """
    matching_files = []
    for root, dirs, files in os.walk(folder):
        path = root.split(os.sep)
        # print((len(path) - 1) * '---', os.path.basename(root))
        for file in files:
            # print(len(path) * '---', file)
            name, type = os.path.splitext(file)
            if type == suffix:
                matching_files += [(root + '/' + file, name)]
    return matching_files


def progressBar(iterable, total, prefix = '', suffix = '', decimals = 1, length = 100, fill = '█', printEnd = "\r"):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
    """
    # Progress Bar Printing Function
    def printProgressBar (iteration):
        percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
        filledLength = int(length * iteration // total)
        bar = fill * filledLength + '-' * (length - filledLength)
        if iteration != len(iterable):
            print(f'\033[K{prefix} (Current file: {iterable[iteration][1]}) | {iteration}/{total} ({percent}%) {suffix}\r', end = printEnd)
        else:
            print(f'\033[K{prefix} DONE | {iteration}/{total} ({percent}%) {suffix}\r', end = printEnd)
    # Initial Call
    printProgressBar(0)
    # Update Progress Bar
    for i, item in enumerate(iterable):
        yield item
        printProgressBar(i + 1)
    # Print New Line on Complete
    print()


if __name__ == '__main__':
    start_time = time.time()
    main()
    print("--- %s seconds ---" % (time.time() - start_time))

