import os
import shutil
import config
from enum import IntEnum


class ResultCode(IntEnum):
    SUCCESS = 200
    FAILURE = 500
    NOT_FOUND = 404


class FileCommandResult:
    def __init__(self, paths, errors=()):
        self.errors = errors
        self.paths = paths
        if not self.errors:
            self.status_code = ResultCode.SUCCESS
        elif self.contains_not_found_error():
            self.status_code = ResultCode.NOT_FOUND
        else:
            self.status_code = ResultCode.FAILURE

        self.errors = [str(error) for error in errors]

    def contains_not_found_error(self):
        return any(isinstance(error, FileNotFoundError) for error in self.errors)


def remove_document_metadata(document):
    """
    Safely remove the metadata folder and the copied pdf created in the file system during import
    """
    document_name = get_file_name(document)
    path = os.path.join(config.metadata_path, document_name)
    errors = []

    try:
        shutil.rmtree(path)
    except (shutil.Error, OSError) as e:
        errors.append(e)

    pdf_path = path + '.pdf'
    try:
        os.remove(pdf_path)
    except OSError as e:
        errors.append(e)

    return FileCommandResult([path, pdf_path], errors)


def get_file_name(path):
    """
    Strip path and file ending
    """
    full_name = os.path.split(path)[1]
    if '.' in full_name:
        return '.'.join(full_name.rsplit('.')[:-1])
    else:
        return full_name
