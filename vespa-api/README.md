# Contents
- Endpoints
    - [POST /document](#post-document)
    - [GET /search](#get-search)
    - [GET /document/\<name\>/page/\<number\>](#get-documentnamepagenumber)
    - [GET /document/\<name\>/download](#get-documentnamedownload)
    - [GET /document/\<name\>/page/\<number\>/image](#get-documentnamepagenumberimage)
    - [DELETE /document/\<name\>](#delete-documentname)
    - [GET /snippet/\<id\>](#get-snippetid)
    - [GET /status](#get-status)
- [Configuration & Extras](#configuration--extras)
    - [Snippet Creation & Cleanup](#snippet-creation--cleanup)   
    - [Batch PDF Import](#batch-pdf-import)

# POST /document
Upload & process OCR-annoted PDF  

This request processes each PDF page individually:
- Render PDF page in PDF library 
    - Extract text including positions on page
    - Convert page to image
    - Store positional information (bounding boxes) and image in server file system
    - Feed text and other schema attributes (see [schema](../baseline_vespa_app/src/main/application/schemas/baseline.sd)) to vespa index

## Disclaimer 
This request overwrites pre-existing documents with a duplicate names. Also, this request can take a while for longer documents. PDF rendering and PDF-to-image conversion can cause a lot of momentary memory usage peaks. In order to keep memory usage as light as possible, each PDF page is processed sequentially. Hence, we decided to increase the default worker timeout in gunicorn from 30 seconds to 120 seconds. The GUNICORN_TIMEOUT parameter can be tweaked via the [Dockerfile](Dockerfile) if needed.

## Request
Content Type: `multipart/form-data`  
Example request:  
```
curl -F "file=@/path/to/ocr/document.pdf" -F "collection=Example Collection Name" http://hostname:5001/document
```

## Response
### Success
`200 OK`

The response provides the uploaded document name (i.e. original name of the uploaded file), a download endpoint for the source PDF, the amount of pages and the vespa-generated _ids_ and _pathIds_ for each page in order to be able to directly retrieve the page documents from the index.
```jsonc
{
    "document_name": "Chief-Signal-Officer_Annual-Report_1945_026-074_Chapter-2_Without-Images.pdf_OCR",
    "download_path": "/document/Chief-Signal-Officer_Annual-Report_1945_026-074_Chapter-2_Without-Images.pdf_OCR/download",
    "page_count": 49,
    "page_paths": [
        {
            "id": "id:baseline:baseline::Chief-Signal-Officer_Annual-Report_1945_026-074_Chapter-2_Without-Images.pdf_OCR_0",
            "pathId": "/document/v1/baseline/baseline/docid/Chief-Signal-Officer_Annual-Report_1945_026-074_Chapter-2_Without-Images.pdf_OCR_0"
        },
        {
            "id": "id:baseline:baseline::Chief-Signal-Officer_Annual-Report_1945_026-074_Chapter-2_Without-Images.pdf_OCR_1",
            "pathId": "/document/v1/baseline/baseline/docid/Chief-Signal-Officer_Annual-Report_1945_026-074_Chapter-2_Without-Images.pdf_OCR_1"
        },

        .
        .
        .

        {
            "id": "id:baseline:baseline::Chief-Signal-Officer_Annual-Report_1945_026-074_Chapter-2_Without-Images.pdf_OCR_48",
            "pathId": "/document/v1/baseline/baseline/docid/Chief-Signal-Officer_Annual-Report_1945_026-074_Chapter-2_Without-Images.pdf_OCR_48"
        }
    ]
}

```

### Failure
`400 Bad Request` 
- No file provided
- Non-PDF file provided
- PDF library failed to render file

`413 Request Entity Too Large`
- File exceeds 20MB size 
    - `MAX_CONTENT_LENGTH` can be configured at the top of [app.py](app.py)

`503 Service Unavailable`
- Baseline vespa application is not in a healthy state because ..
    - .. something broke during runtime in the baseline container ([restart](../README.md#troubleshooting) could do the trick)
    - .. the request was sent before all containers were up and running (docker container status: healthy)

`504 Timeout`  
Could potentially happen, if the batch delete for reimporting files times out, but is highly unlikely

`507 Insufficient Storage`  
- Vespa index is blocking feed operation due to high disk load (see [services.xml](../baseline_vespa_app/src/main/application/services.xml) to configure max disk limits)
 
When in doubt, run `docker-compose logs vespa-api` inside the repository folder for a more comprehensive log output
# GET /search
Start multi-stage search process:
- Construct and forward YQL query from request parameters to baseline vespa app
- For each page hit
    - Fetch positional data and original page image from file system
    - Based on positions of relevant terms on page, create image snippets
## Request Parameters

- `query` Required
    -  string (e.g. `'war zone'`) - applies a logical OR operator on all terms in query
    - array of strings (e.g. `['war', 'zone]`) - applies logical AND to each array item additionally to logical OR inside each string 
- `page` Default: 0 - Page offset in result list
- `hits` Default: 5 - Number of items per result list page
- `language` - Optional
    - Filter results based on document language (detected during import)
    - two-letter ISO 639-1 or three-letter ISO 639-3 codes (e.g. 'en' or 'eng' for English)
- `document` Optional
    - Filter resulting pages on a single parent document
- `order_by` Default: ''  | 'alpha'  
    - Sort results either by rank from best to worst (Default '') or alphabetically ('alpha')
- `direction` Default: 'desc' | 'asc'
    - Determine sort direction when sorting alphabetically (**desc**ending or **asc**ending)

## Response

### Success
`200 OK`  

Example response: [search.json](examples/search.json)

The response is served in JSON format. The top level has the vespa hits (`hits`), translation results in `query_metadata` and the `total` number of relevant items. 

#### hits <a id="query_hits"/>
Hits contains an array of relevant items from the vespa index fashioned after the [default JSON result format](https://docs.vespa.ai/en/reference/default-result-format.html). More specifially it contains data close to the **root.children** array in the default format (see [example JSON](https://docs.vespa.ai/en/query-api.html#result-examples) also). Additionally to the default data from the index, we extend each hit with the `snippets` array data structure. One snippet item inside `snippets` could look as follows:
```jsonc
{
    "boxes": [
        {
            "box": [119, 175.99, 150.59, 167.59], // x1, x2, y1, y2 coordinates
            "relevant": true, // boolean - is term relevant to query?
            "word": "characteristics"
        },
        .
        .
        .
    ],
    "height": 204,
    "width": 1256,
    "image_path": "/snippet/tmpu3nbuhb7", // API path for image source
    "image_scale": 2.7778662420382165 // ratio between source PDF and scaled-down image
}
```
The boxes contain all term bounding boxes of the original document, that are inside the snippet's confines and the relevant flag indicates wether or not the boxes should be highlighted as relevant to the query.

### Failure
`504 Timeout`  
Indicates that the vespa index timed out during the forwarded request.
Can happen for complex queries (hint: tweak the `timeout` variable in [vespa_util.py](vespa_util.py)) or when the vespa index (i.e. baseline application) is unreachable.

# GET /document/\<name\>/page/\<number\>
Launch search at baseline vespa index (Filter single page).
This endpoint represents a way to retrieve the full page metadata with relevant term bounding boxes marked. 

## Request
Example: `curl hostname:5001/document/SEHEN-UND-HOEREN_1969-02_H40.pdf_OCR/page/18?query=war%20dogs`
### Path parameters
- `<name>` (string) - The document name ('parent_doc' in baseline index schema)
- `<page>` (int) - The specific document page
### Query parameters
`query` Required
-  string (e.g. `'war zone'`) - applies a logical OR operator on all terms in query
- array of strings (e.g. `['war', 'zone]`) - applies logical AND to each array item additionally to logical OR inside each string 

## Response
### Success
Example response: [document_search.json](examples/document_search.json)

```jsonc
{
    "bounding_data": {
        "boxes": [
            {
                "box": [119, 175.99, 150.59, 167.59], // x1, x2, y1, y2 coordinates
                "relevant": true, // boolean - is term relevant to query?
                "word": "characteristicts"
            },
            .
            .
            .
        ],
        "height": 1333,
        "width": 1900,
        "image_path": "/document/SEHEN-UND-HOEREN_1969-02_H40.pdf_OCR/page/18/image", // API path for image source
        "image_scale": 	2.7778947368421054, // ratio between source PDF and scaled-down image
    },
    "download_path": "/document/SEHEN-UND-HOEREN_1969-02_H40.pdf_OCR/download", // API path for PDF source
    "hit": {...}, // default vespa hit information
    "query_metadata": {...} // word2word translation metadata
}
```

### Failure
`404 Not Found`  
Document as a whole or specific page number not found in vespa index or bounding box file structure

# GET /document/\<name\>/download
Download source PDF with `<name>` ('parent_doc' in vespa baseline index schema)

## Response
### Success 
```HTTP
200 OK
Content-Disposition: attachment; 
Content-Type: application/pdf
```
### Failure 
`404 Not Found`  
Document not found in file system

# GET /document/\<name\>/page/\<number\>/image
Fetch full page image with `<name>` ('parent_doc' in index schema) and `<number>` ('page' in index schema)

## Response
### Success 
```HTTP
200 OK
Content-Disposition: inline
Content-Type: image/jpeg
```
### Failure 
`404 Not Found`  
Document as a whole or specific page number not found in file system

# DELETE /document/\<name\>
Delete all pages and metadata associated with a specific document `<name>`

## Response
### Success 
Example response: [document_delete.json](examples/document_delete.json)  
The response contains separate results for the vespa index deletion (`vespa_result`) and the metadata deletion 
(`file_result`) and the number of deleted pages in `total_pages`. Errors during metadata deletion are passed silently in
the success result, since even leftover metadata is never accessed, as long as the index entries were successfully 
deleted. 

```jsonc
{
  "file_result": {
    "errors": [],
    "paths": [
      "/output/document_delete_test",
      "/output/document_delete_test.pdf"
    ],
    "status_code": 200 | 404 | 500
  },
  "total_pages": 5,
  "vespa_result": [
    {
      "json": {
        "id": "id:baseline:baseline::document_delete_test_0",
        "pathId": "/document/v1/baseline/baseline/docid/document_delete_test_0"
      },
      "operation_type": "delete",
      "status_code": 200,
      "url": "http://localhost:8080/document/v1/baseline/baseline/docid/document_delete_test_0"
    },
    {
      "json": {
        "id": "id:baseline:baseline::document_delete_test_1",
        "pathId": "/document/v1/baseline/baseline/docid/document_delete_test_1"
      },
      "operation_type": "delete",
      "status_code": 200,
      "url": "http://localhost:8080/document/v1/baseline/baseline/docid/document_delete_test_1"
    },
    .
    .
    .
  ]
}
```
### Failure 
`404 Not Found`  
No associated document pages found in search index

`503 Service Unavailable`  
- Baseline vespa application is not in a healthy state because ..
  - .. something broke during runtime in the baseline container ([restart](../README.md#troubleshooting) could do the trick)
  - .. the request was sent before all containers were up and running (docker container status: healthy)

`504 Timeout`
Indicates that the vespa index timed out during fetching the indexed document batches or during the batch deletion. 
Could possibly only happen for very large document (i.e. pages in the high hundreds or thousands - 
hint: tweak the `timeout` variable in [vespa_util.py](vespa_util.py)) or in some cases when the vespa index 
(i.e. baseline application) is unreachable.


# GET /snippet/\<id\>
Fetch snippet image via `<id>`. Request path most likely retrieved ready to use from `image_path` field in each [query response JSON](#query_hits) hit.
## Response
### Success 
```HTTP
200 OK
Content-Disposition: inline
Content-Type: image/jpeg
```
### Failure 
`404 Not Found`  
Snippet id invalid or outdated

# GET /status
General status check for API

***

# Configuration & Extras
## Snippet Creation & Cleanup
This container creates query-time image snippets and stores them in a tmp-folder on the container drive. This folder is scheduled to be cleaned up once a day. For higher search request loads, it might be advisable to increase the cleanup frequency or devise an 'expiration time' for files and clean up the folder more frequently based on that metric.  
See [cron_container.txt](vespa-api/cron_container.txt) for the schedule and [snippet_cleanup.py](vespa-api/snippet_cleanup.py) for the cleanup logic.

## Batch PDF Import
Aside from the [PDF upload endpoint](#post-document) we offer an additional **(experimental)** method of batch importing PDF files directly inside the vespa-api container:

```bash
# 1. import files to running vespa-api container
# from inside repository folders run
docker-compose cp import-folder/ vespa-api:/data

# 2. prepare folder structure
# top level folder inside source folder gets imported as collection name
# e.g. /data/collection-name/...
# leave a flat hierarchy in order to not assign a collection

# 3. start batch import and pass input folder
cd /code # move to execution folder
pipenv run python pdf_import.py /data # starts import with console output
```

### Usage
```
usage: pdf_import.py [-h] [-s] folder

positional arguments:
  folder      the folder containing PDFs to import

options:
  -h, --help  show this help message and exit
  -s, --skip  skip already imported document pages
```

#### Overwrite & Skip
Currently, the default behaviour (i.e. without _-s_ or _--skip_ flag set) is to remove and reimport existing document 
pages and the associated metadata.

