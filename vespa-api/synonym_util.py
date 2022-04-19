

def remove_parenthesis(text: str):
    """
    Removes text enclosed in parentheses
    :param text:
    :return:
    """
    if '(' in text and ')' in text:
        open = text.find('(')
        close = text.find(')')
        result = text[0:open]
        if close < len(text) - 1:
            result += text[close + 1: len(text)]
        return result.strip()
    else:
        return text


def contains_synonym(synonym: str, words: []):
    """
    Check if list of words contains a synonym string
    :param synonym: str
    :param words: []
    :return:
    """
    synonym_words = synonym.split(' ')
    try:
        index = words.index(synonym_words[0])
        if synonym_words == words[index: index + len(synonym_words)]:
            # full consecutive match in words
            return True
        else:
            # check rest of text for synonym match
            return contains_synonym(synonym, words[index+1])

    except (IndexError, ValueError):
        pass
    return False


def locate_synonym(synonym: str, words: [], locations=None, prevIndex=0):
    """
    Return positions of parts of a fully matched synonym in a list of words

    :param locations: recursively processed list of found synonym locations
    :param synonym: synonym string to look for
    :param words: list of words to search
    """
    if locations is None:
        locations = set()

    synonym_words = synonym.split(' ')
    try:
        index = words.index(synonym_words[0])
        if synonym_words == words[index: index + len(synonym_words)]:
            # full consecutive match in document
            for i in range(index, index + len(synonym_words)):
                locations.add(i + prevIndex)
            locate_synonym(synonym, words[index + len(synonym_words):], locations, index + len(synonym_words) + prevIndex)
        else:
            # check rest of text for synonym match
            locate_synonym(synonym, words[index+1], locations)
    except (IndexError, ValueError):
        return list(locations)
    return list(locations)


def process_synonyms(synonyms):
    """
    Flatten structure and remove and/or split up synonyms into chunks that can be better compared with stemmed data
    :param synonyms:
    :return:
    """
    processed_synonyms = []
    for synonym_list in synonyms:
        for synonym in synonym_list:
            # we ignore flavour text contained in parentheses
            synonym = remove_parenthesis(synonym)

            for term in synonym.split('/'):
                # split synonyms containing slashes into separate terms
                processed_synonyms.append(term)
    return processed_synonyms
