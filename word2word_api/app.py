from flask import Flask, request, abort

app = Flask(__name__)
import translate as translate_util
import synonyms as synonyms_util


@app.route('/')
def hello_world():
    return 'Hello, World!'


@app.route('/multilang-translate', methods=['POST'])
def multi_translate():
    if request.is_json:
        body = request.json
        try:
            translations = translate_util.multilang_text_translate(
                body['sourceLanguage'],
                body['content']
            )

            if body['sourceLanguage'] == 'en':
                terms = body['content']
            else:
                terms = translate_util.get_translated_terms(translations, 'en')

            return {
                "sourceLanguage": body['sourceLanguage'],
                "languages": translate_util.get_supported_languages(),
                "translations": translations,
                "synonyms": synonyms_util.find_synonyms(terms)
            }
        except KeyError:
            pass
    # bad request if content type not JSON or missing/wrong JSON fields
    abort(400)


@app.route('/translate', methods=['POST'])
def translate():
    if request.is_json:
        body = request.json
        try:
            return {
                'translation': translate_util.text_translate(
                    body['sourceLanguage'],
                    body['targetLanguage'],
                    body['content'])
            }
        except KeyError:
            pass
    # bad request if content type not JSON or missing/wrong JSON fields
    abort(400)


@app.route('/supported-languages')
def supported_languages():
    return {
        'languages': translate_util.supported_languages
    }
