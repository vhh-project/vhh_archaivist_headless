# POST /document
Upload & process OCR-annoted PDF  

This request processes each PDF page individually:
- Render PDF page in PDF library 
    - Extract text including positions on page
    - Convert page to image
    - Store positional information (bounding boxes) and image in server file system
    - Feed text and other schema attributes (see schema **TODO**) to vespa index

## Request
Content Type: `multipart/form-data`  
Example request: `curl -F file=@/path/to/ocr/document.pdf http://hostname:5001/upload`

## Response
### Success
`200 OK`

The response provides the uploaded document name (i.e. original name of the uploaded file), a download path for the source PDF, the amount of pages and the vespa-generated _ids_ and _pathIds_ for each page in order to be able to directly retrieve the page documents from the index.
```json
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

`500 Internal Server Error`  
- Vespa index is blocking feed operation due to disk limits
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
- `page` Default: 0  
- `hits` Default: 5
- `language` - Optional
    - Filter results based on document language (detected during import)
    - two-letter ISO 639-1 codes (e.g. 'en' for English)
- `document` Optional
    - Filter resulting pages on a single parent document
- `order_by` Default: ''  | 'alpha'  
    - Sort results either by rank from best to worst (Default '') or alphabetically ('alpha')
- `direction` Default: 'desc' | 'asc'
    - Determine sort direction when sorting alphabetically

## Response
### Success
`200 OK`
The response is served in JSON format. The top level looks like this:
```json
{
    'hits': ...,  // enhanced relevant page hits from vespa index 
    'query_metadata': ...,  // contains query-specific translation metadata
    'total': ...  // total number of relevant document pages
}
```
TODO

### Failure
`504 Timeout`  
Indicates that the vespa index timed out during the forwarded request.
Can happen for complex queries (hint: tweak the `timeout` variable in [test](vespa_util.py)) or when the vespa index (i.e. baseline application) is unreachable.

# GET /document/\<name\>/page/\<number\>
Launch search at baseline vespa index (Filter single page)  
TODO

# GET /document/\<name\>/download
Download source PDF  
TODO

# GET /document/\<name\>/page/\<number\>/image
Fetch full page image  
TODO

# GET /snippet/\<id\>
Fetch snippet image  
TODO

# GET /status
General status check for API  
TODO