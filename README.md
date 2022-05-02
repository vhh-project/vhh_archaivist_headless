# ArchAIvist cross-lingual BM25 index

## Contents
- [Introduction](#introduction)
  - [Containers](#containers)
    - [word2word translation API](#word2word-translation-api)
    - [baseline vespa app](#baseline-vespa-app)
    - [vespa API (intermediate service)](#vespa-api-intermediate-service)
- [Prerequisites](#prerequisites)
- [Disclaimer](#disclaimer)
- [Setup](#setup)
- [Running](#running)
  - [Baseline](#baseline)
  - [Word2Word Translation](#word2word-translation)
  - [Intermediate API](#intermediate-api)
- [Usage](#usage)
  - [Baseline Application (vespa index)](#baseline-application-vespa-index)
    - [Default schema](#default-schema)
    - [Feeding (text only)](#feeding-text-only)
    - [Querying](#querying)
      - [Request](#request)
      - [Response](#response)
      - [Synonyms](#synonyms)
  - [Vespa Intermediate API](#vespa-intermediate-api)
    

## Introduction
This repository contains a multi-container docker application orchestrated with docker-compose. The purpose of this application is to offer a highly configurable search index. The query terms are translated into a range of supported target languages and ranked via BM25.

### Containers
The application is comprised of three containers. These containers can directly communicate with eachother through an internal network automacally established by docker-compose.

#### word2word translation API
A translation API running on a Python Flask server using the [word2word translation library](https://github.com/kakaobrain/word2word). 


Currently supported languages are:
- English
- German
- French
- Catalan
- Italian
- Spanish
- Russian
- Polish
- Bengali

To lower memory consumption and startup time this service does not directly translate between pairs but rather uses English as an intermediary language. However, additional languages can easily be added to [word2word_api/translate.py](word2word_api/translate.py).

#### vespa API (intermediate service)
This container hosts a Python Flask server which simplifies all interactions with the underlying vespa application (see next container). The API supports the import of OCR-annotated PDFs and creates on-the-fly relevant image snippets (including text position metadata) of the source documents for search requests.

#### baseline vespa app
This container hosts a basic vespa search application with a customized searcher plugin, that translates query terms in all languages supported by the vespa linguistics suite and the word2word service to achieve higher retrieval rates in a multilingual document corpus.

## Prerequisites
- mvn - Apache Maven (tested on v3.8.1)
- docker-compose (tested on 1.29.2)

## Disclaimer
This application was solely tested in a local network environment. Additional configuration has to be done to publicly expose its endpoints.

## Setup

- Execute ```mvn install``` in the _baseline_vespa_app_ folder.
- Add the _baseline_vespa_app_ to the execution environment through ```export VESPA_BASELINE=/path/to/vespa/app/folder``` or alternatively by hardcoding the path in the _docker-compose.yml_ file

## Running
After completing the setup steps, simply execute ```docker-compose up -d``` from the repo's root folder.

This launches the vespa API, the baseline vespa app as well as the word2word translation container. Once all container's health checks return status 'healthy' the service is ready to go.

### Baseline
The baseline launch is already configured to wait for the internal vespa config server to launch, and subsequently launch the content server running the index and APIs. The container's health check queries a status endpoint of the content server.

### Word2Word Translation
This container may take a while during first launch, since it downloads dictionaries for each supported language pair on startup. 

### Intermediate API
This container should be the quickest up, but of course requires the baseline index to be up and running for requests to properly work.

## Usage
Default port for vespa index applications: **8080**  
Default port for vespa intermediate API: **5001**  

The internal ports of the docker-compose network should remain the same but the exposed ports can be configured in [docker-compose.yml](docker-compose.yml).

### Baseline Application (vespa index)
In the following sections we will show some exemplary ways for feeding documents and sending queries to this application. For a more comprehensive introduction to all possibilities please visit the vespa documentation: 
- [Quick Start](https://docs.vespa.ai/en/vespa-quick-start.html)
- [All sections under 'Reads and Writes'](https://docs.vespa.ai/en/reads-and-writes.html)
#### Default schema
The default schema, which can be customized to your needs, is comprised of following fields: 
- **id** - Allows full text IDs
- **body** - Stores the plain text representation of the document and is the only indexed field
- **language** (Optional) - Can be provided to be able to filter queries based on document source language
- **parent_doc** (Optional) - Name of the parent document, if feeding single document pages
- **page** (Optional) - Page number, if feeding single document pages
- **collection** (Optional) - Parameter for grouping multiple parent documents in collections

The full schema can be found at [baseline_vespa_app/src/main/application/schemas/baseline.sd](baseline_vespa_app/src/main/application/schemas/baseline.sd)

#### Feeding (text only)
 As mentioned earlier there are several ways to feed documents to the vespa application. Here we will demonstrate one way to feed single documents via the [/document/v1 API](https://docs.vespa.ai/en/document-v1-api-guide.html):

 Send a POST request to 
 
 ```http://hostname:8080/document/v1/baseline/baseline/docid/<document_id>```

 with the desired *document_id* at the end of the path.
 
 The body should be in JSON format and could look like this:
 ```json
 {
     "fields": {
         "body": "Insert text content of your document here"
     }
 }
 ```
Feel free to also populate the other fields introduced above when feeding data. This example only represents the bare minimum a feed requires.

#### Querying

##### Request
Querying can be done through vespa's own [Query API](https://docs.vespa.ai/en/query-api.html). The query API allows both GET requests with according query parameters or a POST request with a JSON body containing the necessary fields. Next we will show an example request (POST for better readability) and explain the details:

```
http://hostname:8080/search
```
The JSON body:
```json
{
    "searchChain": "multilangchain",
    "yql": "select * from sources * where default contains 'this is a demo query';",
    "hits": 5,
    "offset": 0,
    "presentation.format": "query-meta-json"
}
```
- searchChain - this is required to trigger our custom multilingual searcher component
- [yql](https://docs.vespa.ai/en/query-language.html) - vespa's own query language. Queries targeting the *body* field are multilingually expanded
- hits (optional; default: 10) - amount of relevant documents to return
- offset (optional; default: 0) - offset to start from returning documents
- presentation.format: The '**query-meta-json**' format is a custom-built extension of the default result format of vespa. It adds an additional '**query-metadata**' field to the result containing information about the internal query translation

Keep in mind, that vespa and our custom searcher run language detection on the query body. Unfortunately, short queries often can not be successfully recognized and therefore default to english. Languages not supported by the stemmer and/or the translation service also default to english.

##### Response
The response with the above query setup mostly follows the [default JSON result format](https://docs.vespa.ai/en/reference/default-result-format.html) with the addition of the '**query-metadata**' field in the 'root' object. 

The output for each relevant document, i.e. which fields are displayed and in which manner, can be configured via attributes in the schema fields. For example, the body field currently has the 'summary' attribute set to 'dynamic', which returns a relevant text snippet from the document body with matching words highlighted accordingly. To return the full document body, this attribute has to be removed.

##### Synonyms
As an additional step in the translation process, we look for synonyms of specific (currently English) phrases and multilingual aliases contained in [word2word_api/wikidata-aliases.txt](word2word_api/wikidata-aliases.txt). Any found synonyms also are returned in the response and consequently used for extenting the initial query. 

File format for synonyms: main-phrase \<tab> synonym 1 \<tab> synonym 2 \<tab> synonym 3 \<tab> ...

In order to disable synonym detection or change the file path, take a look at [word2word_api/config.ini](word2word_api/config.ini).

***
### Vespa Intermediate API
See service's [README.md](vespa-api/README.md)