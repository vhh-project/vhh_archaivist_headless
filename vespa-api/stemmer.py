import nltk
from nltk.stem.snowball import SnowballStemmer

languages = {
    'de': 'german',
    'en': 'english',
    'fr': 'french',
    'ca': 'english',  # No catalan stemmer available
    'it': 'italian',
    'es': 'spanish',
    'ru': 'russian',
    'pl': 'english',  # No polish stemmer available
    'bn': 'english',  # No bengal stemmer available
    'da': 'danish',
    'un': 'english'  # default english, if vespa didn't manage to detect a query language
}


def map_stems_to_words(words, language_code):
    if language_code not in languages:
        language_code = 'un'
    stemmer = SnowballStemmer(language=languages[language_code])
    unique_stems = {}
    for word in words:
        stemmed_word = stemmer.stem(word)
        try:
            unique_stems[stemmed_word].add(word)
        except KeyError:
            unique_stems[stemmed_word] = set()
            unique_stems[stemmed_word].add(word)

    stems = {}
    for stem, word_set in unique_stems.items():
        stems[stem] = {'terms': list(word_set), 'languages': [language_code]}
    return stems


def map_words_to_stems(words, language_code):
    if language_code not in languages:
        language_code = 'un'
    stemmer = SnowballStemmer(language=languages[language_code])
    stem_map = {}
    for word in words:
        stem_map[word] = stemmer.stem(word)
    return stem_map


if __name__ == '__main__':
    pass