import os

from flask import Flask, request, abort, send_from_directory, render_template, flash, redirect
from flask_cors import CORS
from werkzeug.utils import secure_filename

import config
import pdf_import
import vespa_util

app = Flask(__name__)
CORS(app)
ALLOWED_EXTENSIONS = ['pdf']


@app.route('/')
def hello_world():
    return 'Hello World!'


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/document', methods=['POST'])
def upload_file():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            collection = request.form['collection'] if 'collection' in request.form else ''
            try:
                name, pages = pdf_import.import_file(file=file, full_name=filename, collection=collection)
                return {
                    "document_name": name,
                    "download_path": f'/document/{name}/download',
                    "page_count": len(pages),
                    "page_paths": pages
                }
            except pdf_import.PdfImportError as e:
                abort(e.code, e.message)
            return ''
        else:
            abort(400, 'Please provide a valid PDF file')


@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query', default='', type=str)
    page = request.args.get('page', 0, type=int)
    hit_count = request.args.get('hits', 5, type=int)
    language = request.args.get('language', default='', type=str)
    document = request.args.get('document', default=None)
    order_by = request.args.get('order_by', default='')
    direction = request.args.get('direction', default='desc')
    stem_filter = request.args.get('stem_filter', default='')
    try:
        hits, query_metadata, bounding_boxes, total = \
            vespa_util.query(
                query,
                hits=hit_count,
                page=page,
                language=language,
                document=document,
                order_by=order_by,
                direction=direction,
                stem_filter=stem_filter)
    except vespa_util.VespaTimeoutException:
        abort(504)

    return {
        "hits": hits,
        "query_metadata": query_metadata,
        "total": total
    }


@app.route('/snippet/<snippet_id>')
def show_snippet(snippet_id):
    return send_from_directory(config.snippet_dir, snippet_id + config.convert_suffix)


@app.route('/status')
def status():
    return 'Up and running!'


@app.route('/document/<doc_name>/page/<page_number>')
def search_page(doc_name, page_number):
    query = request.args.get('query', default='', type=str)
    try:
        result, query_metadata, bounding_data = vespa_util.query_doc_page(doc_name, page_number, query)
        return {
            'hit': result,
            'query_metadata': query_metadata,
        } | bounding_data
    except FileNotFoundError:
        return '', 204


@app.route('/document/<doc_name>/page/<page_number>/image')
def show_document_page_image(doc_name, page_number):
    return send_from_directory(config.metadata_path, doc_name + '/' + page_number + config.convert_suffix)


@app.route('/document/<doc_name>/download')
def download_document_file(doc_name):
    return send_from_directory(config.metadata_path, doc_name + '.pdf', as_attachment=True)


if __name__ == '__main__':
    app.run()
