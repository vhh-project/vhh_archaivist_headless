import file_processing
import vespa_util


def delete_document(document):
    document_name = file_processing.get_file_name(document)
    vespa_delete_result = vespa_util.delete_document_pages(document_name)
    file_delete_result = file_processing.remove_document_metadata(document_name)
    if not vespa_delete_result:
        raise FileNotFoundError
    return {
        'vespa_result': [result.__dict__ for result in vespa_delete_result],
        'file_result': file_delete_result.__dict__
    }
