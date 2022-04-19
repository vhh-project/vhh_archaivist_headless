from PIL import Image, ImageDraw
import config
import json
from tempfile import NamedTemporaryFile
import os
from pathlib import Path

# Prevent warning for large images
Image.MAX_IMAGE_PIXELS = 160000000


def store_snippets(snippets: list[Image]):
    if not os.path.isdir(config.snippet_dir):
        os.mkdir(config.snippet_dir)

    snippet_names = []
    for snippet in snippets:
        temp_file = NamedTemporaryFile(mode="w+b", suffix=config.convert_suffix, delete=False, dir=config.snippet_dir)
        snippet.save(temp_file, config.convert_type)
        snippet_names.append(Path(temp_file.name).stem)
        snippet.close()
        temp_file.close()
    return snippet_names


def build_snippets(document_name, page, query):
    doc_dir = f'{config.metadata_path}/{document_name}'
    metadata = __load_meta(doc_dir, page)
    page_image = __open_page_image(document_name, page)
    snippet_boxes = []
    for term in query:
        try:
            snippet_boxes.extend(__build_term_snippet_boxes(page_image, metadata, term))
        except KeyError:
            pass
    snippet_boxes = __filter_boxes(snippet_boxes)
    snippet_names = []
    for box in snippet_boxes:
        snippet = page_image.crop(box)
        snippet_names.extend(store_snippets([snippet]))
    snippet_boxes = [__box_pil2pdf(box, metadata['dimensions']['thumbScale'], metadata['dimensions']['origHeight'])
                      for box in snippet_boxes]
    page_image.close()
    return snippet_names, snippet_boxes, metadata


def __filter_boxes(boxes):
    # x1, y1, x2, y2
    filtered_boxes = []
    boxes.sort(key=__sort_boxes)
    for box in boxes:
        colliding_index = __find_first_colliding_index(box, filtered_boxes)
        if colliding_index > -1:
            joined_box = [box[0], min(box[1], filtered_boxes[colliding_index][1]),
                          box[2], max(box[3], filtered_boxes[colliding_index][3])]
            filtered_boxes.pop(colliding_index)
            filtered_boxes.append(joined_box)
        else:
            filtered_boxes.append(box)
    return filtered_boxes


def __sort_boxes(b):
    return b[1]


def __find_first_colliding_index(box, filtered_boxes):
    new_y_start = box[1]
    new_y_end = box[3]
    for i, filtered_box in enumerate(filtered_boxes):
        filter_y_start = filtered_box[1]
        filter_y_end = filtered_box[3]
        if (filter_y_start == new_y_start or filter_y_end == new_y_end) or (
                new_y_start <= filter_y_start <= new_y_end) or (
                filter_y_start <= new_y_start <= filter_y_end):
            return i
    return -1


def __build_term_snippet_boxes(marked_page: Image, metadata: dict, term: str):
    scale = metadata['dimensions']['thumbScale']
    term_boxes = metadata['boxes'][term]
    term_snippet_boxes = []
    for term_box in term_boxes:
        box = __box_pdf2pil(term_box, scale, marked_page.height)
        box = __add_margins(box, marked_page.width, marked_page.height)
        term_snippet_boxes.append(box)
    return term_snippet_boxes


def __open_page_image(document_name, page, thumb=True):
    doc_dir = f'{config.metadata_path}/{document_name}'
    return Image.open(f'{doc_dir}/{page}{"_thumb" if thumb else ""}{config.convert_suffix}')


def __highlight_page(document_name, page, query, metadata=None):
    doc_dir = f'{config.metadata_path}/{document_name}'
    image = Image.open(f'{doc_dir}/{page}{config.convert_suffix}').convert("RGBA")
    if not metadata:
        metadata = __load_meta(doc_dir, page)
    overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
    for term in query:
        __highlight_term(overlay, metadata, term)
    return Image.alpha_composite(image, overlay)


def __highlight_term(overlay: Image, metadata: dict, term: str):
    scale = metadata['dimensions']['scale']
    try:
        term_boxes = metadata['boxes'][term]
        highlight = ImageDraw.Draw(overlay)
        for term_box in term_boxes:
            box = __box_pdf2pil(term_box, scale, overlay.height)
            highlight.rectangle(box, config.snippet_highlight_color)
    except KeyError:
        pass


def __box_pdf2pil(box, scale, height):
    # from: x1, x2, y2, y1 (y-coord 0 starting from bottom)
    # to:   x1, y1, x2, y2 (y-coord 0 starting from top)
    box = [dimension * scale for dimension in box]
    box = [box[0], height - box[3], box[1], height - box[2]]
    return box


def __box_pil2pdf(box, scale, height):
    # from: x1, y1, x2, y2 (y-coord 0 starting from top)
    # to:   x1, x2, y2, y1 (y-coord 0 starting from bottom)
    box = [dimension / scale for dimension in box]
    box = [box[0], box[2], height - box[3], height - box[1]]
    return box


def __add_margins(box, width, height):
    margin = round(config.snippet_margin * height)
    box = [0, max(0, box[1] - margin), width, min(height, box[3] + margin)]
    return box


def __load_meta(doc_dir, page):
    with open(f'{doc_dir}/{page}.json', 'r') as file:
        metadata = json.load(file)
        return metadata


def main():
    snippets, _ = build_snippets('multipage_test', 1, ['adc', 'signal', 'corps'])
    [snippet.show() for snippet in snippets]
    # file_paths = store_snippets(snippets)
    # for path in file_paths:
    #     print(path)


if __name__ == '__main__':
    main()
