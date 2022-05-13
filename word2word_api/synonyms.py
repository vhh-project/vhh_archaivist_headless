import csv
import configparser
import re

config = configparser.ConfigParser()
config.read('config.ini')
config = config['synonyms']
synonym_map = {}


def __remove_parenthesis(text: str):
    open = text.find('(')
    close = text.find(')')
    result = text[0:open]
    if close < len(text) - 1:
        result += text[close + 1: len(text)]
    return result.strip()


def __add_term(main_term, row):
    try:
        synonym_map[main_term] += row[1:]
    except KeyError:
        synonym_map[main_term] = row[1:]


def find_synonyms(term_list: list):
    terms = " ".join(term_list)
    result = []

    for main_term, synonyms in synonym_map.items():
        if re.search(r'\b'+main_term, terms) is not None:
            result.append({
                'mainTerm': main_term,
                'terms': synonyms
            })
    return result


if config.getboolean('enabled'):
    with open(config['input'], 'r') as f:
        reader = csv.reader(f, delimiter="\t")
        # tab separated file in this format: main-phrase <tab> synonym 1 <tab> synonym 2 <tab> synonym 3 <tab> …
        # main-term is (currently) always english, while the synonyms can be multilingual
        for row in reader:
            main_term = row[0]

            if '(' in main_term and ')' in main_term:
                main_term = __remove_parenthesis(main_term)

            for term in main_term.split('/'):
                __add_term(term, row)
