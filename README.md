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
See specific [README.md](baseline_vespa_app/README.md) for usage
### Vespa Intermediate API
See specific [README.md](vespa-api/README.md) for usage