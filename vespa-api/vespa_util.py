import socket
import traceback

import urllib3.exceptions
from vespa.application import Vespa
import json
from langdetect import detect, LangDetectException
import ast
import bounding_boxes
import image_processing
import stemmer
import config
import requests
import synonym_util
import itertools

url = config.vespa_url
schema = "baseline"
port = config.vespa_port
app = Vespa(url, port)
searchChain = "multilangchain"
traceLevel = 0
timeout = "5s"
renderer = "query-meta-json"

order_fields = ['alpha']
order_directions = ['desc', 'asc']


class VespaTimeoutException(Exception):
    pass


def query(query, hits=5, page=0, language='', document=None, order_by='', direction='desc', stem_filter=''):
    """
    Launch a query at the vespa search index

    :param query: The JSON string query list or single query string (mandatory)
    :param hits: amount of entries to retrieve (default 5)
    :param page: page offset for the result list (default 0)
    :param language: filter results by language (ISO 639-1 codes)
    :param document: filter by a specific source document
    :param order_by: sort results alphabetically (alpha) or by ranking (default)
    :param direction: sort direction: asc | desc (default)
    :param stem_filter: JSON string of data structure describing language specific stems to be filtered
    :return:
    """
    try:
        query_list = json.loads(query)
    except json.JSONDecodeError:
        query_list = [query]

    phrases = ''

    for i, phrase in enumerate(query_list):
        phrases += f'default contains "{phrase}"'
        if i < len(query_list) - 1:
            phrases += ' and '

    language_and = ''
    if language:
        language_and = f'and language matches "{language}"'

    document_and = ''
    if document and document != '':
        document_and = f'and parent_doc matches "{document}"'

    order_clause = ''
    if order_by in order_fields and direction in order_directions:
        if order_by == 'alpha':
            order_clause = f'order by parent_doc {direction}, page {direction}'

    yql = f'select * from sources * where {phrases} {language_and} {document_and} {order_clause};'

    try:
        result = app.query(body={
            "traceLevel": traceLevel,
            "searchChain": searchChain,
            "hits": hits,
            "offset": page * hits,
            "timeout": timeout,
            "yql": yql,
            "presentation.format": renderer,
            "stemFilter": stem_filter  # custom non-vespa searchChain-specific param
        })
    except requests.exceptions.RetryError as e:
        print(''.join(traceback.format_exception(None, e, e.__traceback__)))
        raise VespaTimeoutException(e)

    query_metadata = result.json['root']['query-metadata']
    for i, phrase_translations in enumerate(query_metadata['translations']):
        multilang_terms = __collect_multilang_query_terms(phrase_translations)
        multilang_stems = __collect_multilang_query_stems(phrase_translations)
        multilang_stem_map = __collect_multilang_query_stem_map(phrase_translations)
        query_metadata['translations'][i]['stems'] = multilang_stems
        query_metadata['translations'][i]['stemMap'] = multilang_stem_map
        query_metadata['translations'][i]['flatTerms'] = multilang_terms
    try:
        return result.hits, result.json['root']['query-metadata'], \
               get_bounding_box_data(result.hits), result.number_documents_retrieved
    except KeyError as e:
        print(''.join(traceback.format_exception(None, e, e.__traceback__)))
        raise VespaTimeoutException(e)


def get_bounding_box_data(hits):
    bounding_boxes = {}
    for hit in hits:
        doc = hit['fields']['parent_doc']
        page = hit['fields']['page']
        box_data = __load_meta(doc, page)
        try:
            bounding_boxes[doc][page] = box_data
        except KeyError:
            bounding_boxes[doc] = {}
            bounding_boxes[doc][page] = box_data
    return bounding_boxes


def query_doc_page(doc, page):
    try:
        meta = __load_meta(doc, page)
        yql = f'select * from sources * where parent_doc matches \"{doc}\" and page matches \"{page}\";'

        result = app.query(body={
            "traceLevel": traceLevel,
            "searchChain": searchChain,
            "timeout": timeout,
            "yql": yql,
            "presentation.format": renderer
        })

        return result.hits[0], meta
    except (FileNotFoundError, IndexError):
        raise FileNotFoundError


def build_query_snippets(hit, stems, synonyms):
    """
    Build query snippets of a specific document page containing search query items or any matching synonyms

    :param hit: vespa hit data of the document page
    :param stems: stemmed query terms
    :param synonyms: data structure with synonyms matching the query
    :return: dict containing file paths to snippet images and bounding box data
    """
    snippet_data = {}
    doc = hit['fields']['parent_doc']
    page = hit['fields']['page']
    relevant_stem_terms = __get_relevant_stem_terms(doc, page, stems)
    relevant_synonym_terms = __get_relevant_synonym_terms(doc, page, synonyms)
    relevant_terms = relevant_stem_terms + relevant_synonym_terms
    hit_snippets_names, hit_snippets_boxes, box_data = image_processing.build_snippets(doc, page, relevant_terms)
    try:
        snippet_data[doc][page] = {'names': hit_snippets_names, 'boxes': hit_snippets_boxes}
    except KeyError:
        snippet_data[doc] = {}
        snippet_data[doc][page] = {'names': hit_snippets_names, 'boxes': hit_snippets_boxes}
    return snippet_data


def __collect_multilang_query_terms(translations):
    terms = set()
    for translation in translations['translations']:
        for term in translation['content']:
            terms.add(term.lower())
    return list(terms)


def __collect_multilang_query_stems(translations):
    stems = {}
    for translation in translations['translations']:
        for stem, values in stemmer.map_stems_to_words(translation['content'], translation['languageCode']).items():
            if stem in stems:
                stems[stem]['terms'] = list(set(values['terms'] + stems[stem]['terms']))
                stems[stem]['languages'] = list(set(values['languages'] + stems[stem]['languages']))
            else:
                stems[stem] = values
    return stems


def __collect_multilang_query_stem_map(translations):
    stems = {}
    for translation in translations['translations']:
        stems.update(stemmer.map_words_to_stems(translation['content'], translation['languageCode']))
    return stems


def __get_relevant_stem_terms(doc, page, stems):
    metadata = __load_meta(doc, page)
    return list(get_relevant_terms(stems, metadata['stems']).keys())


def get_relevant_terms(query_stems, page_stems):
    page_stems = __extend_multipart_stems(page_stems)
    relevant_terms_map = {}
    for stem in query_stems:
        if stem in page_stems:
            for term in page_stems[stem]:
                relevant_terms_map[term] = stem
    return relevant_terms_map


def __extend_multipart_stems(stems: dict):
    extended_stems = stems.copy()
    for stem, terms in stems.items():
        if '-' in stem:
            parts = stem.split('-')
            for part in parts:
                extended_stems[part] = terms
    return extended_stems


def __get_relevant_synonym_terms(doc, page, synonyms):
    metadata = __load_meta(doc, page)
    return find_relevant_synonym_terms(metadata['boxes'], metadata['stems'], synonyms)


def find_relevant_synonym_terms(boxes, page_stems, synonyms):
    """
    Sorts words contained in provided box data and finds full synonym matches in sorted text and stem mappings

    :param boxes: dict of bounding boxes with text data
    :param page_stems: stemmed terms of boxed words
    :param synonyms: dict of synonyms (mainTerm => [terms])
    :return: list of relevant synonym terms
    """
    page_words = [box['word'] for box in bounding_boxes.flatten_bounding_boxes(boxes)]
    synonyms = [item['terms'] + [item['mainTerm']] for item in synonyms if item['mainTerm'] != '']
    processed_synonyms = []
    relevant_synonyms = []

    for synonym_list in synonyms:
        for synonym in synonym_list:
            # we ignore flavour text contained in parentheses
            synonym = synonym_util.remove_parenthesis(synonym)

            for term in synonym.split('/'):
                # split synonyms containing slashes into separate terms
                processed_synonyms.append(term)
            # check for occasional stem synonym overlap and match
            if synonym in page_stems:
                relevant_synonyms.extend(page_stems[synonym])

    for synonym in processed_synonyms:
        if synonym_util.contains_synonym(synonym, page_words):
            relevant_synonyms.append(synonym)
    return relevant_synonyms


def find_relevant_synonym_positions(words, synonyms, stems):
    """
        Sorts words contained in provided box data and finds index positions of full synonym matches in sorted text

        :param words: list of words
        :param synonyms: dict of synonyms (mainTerm => [terms])
        :param stems: dict of stems mapping to words
        :return: list of indices containing relevant synonym words
    """
    synonyms = [item['terms'] + [item['mainTerm']] for item in synonyms if item['mainTerm'] != '']
    processed_synonyms = synonym_util.process_synonyms(synonyms)
    position_map = {}

    for synonym in processed_synonyms:
        for position in synonym_util.locate_synonym(synonym, words):
            __add_or_create_dict_list(position_map, position, synonym)
        try:
            # try to find synonym in stems
            inverse_stems = __combine_inverse_synonym_stems(stems, synonym)
            for stem_combo in inverse_stems:
                for position in synonym_util.locate_synonym(' '.join(stem_combo), words):
                    __add_or_create_dict_list(position_map, position, synonym)
        except (KeyError, ValueError):
            pass
    return position_map


def __add_or_create_dict_list(dictionary, key, item):
    try:
        if item not in dictionary[key]:
            dictionary[key].append(item)
    except KeyError:
        dictionary[key] = [item]


def __combine_inverse_synonym_stems(stems, synonym):
    stems_synonym = [stems[part] for part in synonym.split(' ')]
    return list(itertools.product(*stems_synonym))


def __load_meta(doc, page):
    doc_dir = f'{config.metadata_path}/{doc}'
    with open(f'{doc_dir}/{page}.json', 'r') as file:
        metadata = json.load(file)
        return metadata


def feed(id: str, parent_doc: str, page: str, collection: str, content: str):
    """
    Feed content into the vespa search engine

    :param id: desired id
    :param parent_doc: name of parent document (for single page processing)
    :param page: page number (for single page processing)
    :param collection: name of collection this document is part of
    :param content: string content intended for indexing
    """
    try:
        language = detect(content)
    except LangDetectException:
        language = ''
    response = app.feed_data_point(
        schema="baseline",
        data_id=str(id),
        fields={
            "language": language,
            "parent_doc": parent_doc,
            "page": page,
            "collection": collection,
            "body": content
        }
    )

    if response.status_code >= 400:
        print(response.status_code, response.json, end="\n")


def health_check():
    """
    Checks if vespa search engine application is up and running
    """
    try:
        return requests.get(f'{url}:{port}/ApplicationStatus').status_code == 200
    except Exception:
        return False


if __name__ == '__main__':
    results = query('signal corps')
    print(json.dumps(results, indent=4, sort_keys=True))
