// Copyright 2019 Oath Inc. Licensed under the terms of the Apache 2.0 license. See LICENSE in the project root.
package baseline;

import baseline.model.*;
import baseline.service.Word2WordTranslator;
import com.google.gson.Gson;
import com.google.inject.Inject;
import com.yahoo.language.Language;
import com.yahoo.language.Linguistics;
import com.yahoo.language.detect.Detection;
import com.yahoo.language.process.StemList;
import com.yahoo.language.process.StemMode;
import com.yahoo.prelude.query.*;
import com.yahoo.search.Query;
import com.yahoo.search.Result;
import com.yahoo.search.Searcher;
import com.yahoo.search.query.QueryTree;
import com.yahoo.search.searchchain.Execution;
import com.yahoo.yolean.chain.After;

import java.util.*;
import java.util.stream.Collectors;
import java.util.stream.StreamSupport;

/**
 * Searcher which translates query terms into different languages
 * and extends the query with the translated terms and synonyms
 */
@After("MinimalQueryInserter")
public class MultilangSearcher extends Searcher {

    private Linguistics linguistics;
    private Word2WordTranslator translator;

    @Inject
    public MultilangSearcher(Linguistics linguistics, Word2WordTranslator translator) {
        this.linguistics = linguistics;
        this.translator = translator;
    }

    public MultilangSearcher() {

    }

    /**
     * Search method takes the query and an execution context.  This method can
     * manipulate both the Query object and the Result object before passing it
     * further in the chain.
     * 
     * @see https://docs.vespa.ai/documentation/searcher-development.html
     */
    @Override
    public Result search(Query query, Execution execution) {
        QueryTree tree = query.getModel().getQueryTree();
        Item root = tree.getRoot();
        Map<Language, List<String>> detections = new HashMap<>();
        List<MultiTranslation> multiTranslationList = new ArrayList<>();
        List<Item> queryItems = new ArrayList<>();
        Gson gson = new Gson();
        String filterLanguage = "";

        if (root instanceof AndItem) {
            for (ListIterator<Item> it = ((AndItem) root).getItemIterator(); it.hasNext();) {
                queryItems.add(it.next());
            }
            // assuming multi-part query with subqueries and/or language filter

            filterLanguage = getFilterLanguage((CompositeItem) root);
            filterLanguage = filterLanguage != null ? filterLanguage : "";
        } else {
            queryItems.add(root);
        }

        for (int i = 0; i<queryItems.size(); i++) {
            Item queryItem = queryItems.get(i);
            String queryBody = "";
            String indexName = "";
            // assuming basic query with single contains clause for "body" field
            if (queryItem instanceof IndexedSegmentItem) {
                IndexedSegmentItem item = (IndexedSegmentItem) queryItem;
                queryBody = item.stringValue();
                indexName = item.getIndexName();
            } else if (queryItem instanceof TermItem) {
                TermItem item = (TermItem) queryItem;
                queryBody = item.stringValue();
                indexName = item.getIndexName();
            }

            if (indexName.equals("body") || indexName.equals("default")) {
                query.trace("String value of query: '" + queryBody + "'", true, 2);

                Detection detection = linguistics.getDetector().detect(queryBody, null);
                Language detectedLanguage = detection.getLanguage();
                query.trace(String.format("Detected language: '%s'", detectedLanguage.languageCode()), 2);

                // Stream that splits up the query body into individual string tokens
                List<String> words = StreamSupport
                        .stream(linguistics.getTokenizer()
                                .tokenize(queryBody, detectedLanguage, StemMode.NONE, false)
                                .spliterator(), false)
                        .filter(token -> token.isIndexable())
                        .map(token -> token.getOrig())
                        .collect(Collectors.toList());

                try {
                    // Launch translation request to the word2word translation container
                    MultiTranslation multiTranslation = translator.multiTranslate(words, detectedLanguage.languageCode());
                    multiTranslationList.add(multiTranslation);
                    query.trace("Translator result: " + gson.toJson(multiTranslation), true, 2);

                    // Normalize and stem all translated terms with the language-specific stemmer
                    Map<String, List<StemList>> stems = new HashMap<>();
                    for (MultiTranslationPart translationPart : multiTranslation.getTranslations()) {
                        List<StemList> stemListList = new ArrayList<>();
                        for (String word : translationPart.getContent()) {
                            word = linguistics.getNormalizer().normalize(word);
                            if (word.equals("")) {
                                stemListList.add(new StemList(word));
                            } else {
                                stemListList.addAll(linguistics.getStemmer()
                                        .stem(word, StemMode.DEFAULT, Language.fromLanguageTag(translationPart.getLanguageCode()))
                                );
                            }
                        }
                        stems.put(translationPart.getLanguageCode(), stemListList);
                    }
                    query.trace("Stemmed translations: " + gson.toJson(stems), false, 2);

                    WeakAndItem weakAndItem = new WeakAndItem();
                    OrItem languageOrItem = new OrItem();
                    //Extend query with clauses, which equally rank translated terms to their original counterparts

                    String finalFilterLanguage = filterLanguage;
                    stems.forEach((language, stemLists) -> {
                        if (finalFilterLanguage.equals("") || finalFilterLanguage.equals(language)) {
                            AndItem languageAndItem = new AndItem();
                            WeakAndItem langWeakAndItem = new WeakAndItem();
                            stemLists.forEach(wordStems -> {
                                if (wordStems.size() > 1) {
                                    PhraseItem compositeStemsItem = new PhraseItem();
                                    for (String stem : wordStems) {
                                        compositeStemsItem.addItem(new WordItem(stem));
                                    }
                                    langWeakAndItem.addItem(compositeStemsItem);
                                } else {
                                    if (!wordStems.get(0).isBlank()) {
                                        TermItem stemItem = new WordItem(wordStems.get(0));
                                        langWeakAndItem.addItem(stemItem);
                                    }
                                }
                            });
                            languageAndItem.addItem(langWeakAndItem);
                            languageAndItem.addItem(new RegExpItem(Constants.LANGUAGE_FIELD, true, language));
                            languageOrItem.addItem(languageAndItem);
                        }
                    });

                    if (filterLanguage.equals("")) {
                        // no filter so we can add language filters appropriately
                        languageOrItem.addItem(getLanguageElse(multiTranslation, words));
                    }
                    weakAndItem.addItem(languageOrItem);

                    if (shouldUseSynonyms(query)) {
                        addSynonymClauses(detections, multiTranslation, weakAndItem);
                    } else {
                        multiTranslation.getSynonyms().clear();
                    }

                    if (root instanceof AndItem) {
                        // assuming multi-part query with subqueries and/or language filter
                        ((AndItem) root).setItem(i, weakAndItem);
                    } else {
                        // query with single node
                        root = weakAndItem;
                    }
                    query.trace(String.format("\n\nSynonym language detections: " + detections), false, 2);
                    query.trace(String.format("\n\nQuery modification %d/(potentially) %d done", i+1, queryItems.size()), false, 2);
                } catch (Word2WordTranslator.TranslateExecption translateExecption) {
                    query.trace("Translator failed: " + translateExecption.getMessage(), 2);
                }
            }
        }
        // Store translation metadata in query context. This property can then be retrieved from custom result renderer.
        query.getContext(true).setProperty(Constants.TRANSLATIONS, gson.toJson(multiTranslationList));
        query.getModel().getQueryTree().setRoot(root);
        query.trace("MultilangSearcher was called in chain", true, 2);
        return execution.search(query);
    }

    private void addSynonymClauses(Map<Language, List<String>> detections, MultiTranslation multiTranslation, WeakAndItem weakAndItem) {
        // Extend weakAnd clause with phrases found in query text and their respective synonyms
        for (Synonyms synonyms : multiTranslation.getSynonyms()) {
            var mainTermStems = getBestStems(detections, synonyms.getMainTerm(), Language.ENGLISH);
            EquivItem equivalentSynonyms;
            if (mainTermStems.length > 1) {
                equivalentSynonyms = new EquivItem(new PhraseItem(mainTermStems));
            } else {
                equivalentSynonyms = new EquivItem(new WordItem(mainTermStems[0]));
            }

            for (String term : synonyms.getTerms()) {
                var termList = getBestStems(detections, term, null);
                if (termList.length == 0) {
                    equivalentSynonyms.addItem(new WordItem(term));
                } else if (termList.length > 1) {
                    equivalentSynonyms.addItem(new PhraseItem(termList));
                } else {
                    equivalentSynonyms.addItem(new WordItem(termList[0]));
                }
            }
            weakAndItem.addItem(equivalentSynonyms);
        }
    }

    private Item getLanguageElse(MultiTranslation multiTranslation, List<String> words) {
        NotItem notItem = new NotItem();
        String regExp = multiTranslation.getLanguages()
                .stream()
                .collect(Collectors.joining("|", "(", ")"));
        RegExpItem regExpItem = new RegExpItem(Constants.LANGUAGE_FIELD, true, regExp);
        notItem.addNegativeItem(regExpItem);
        AndItem elseAndItem = new AndItem();
        elseAndItem.addItem(notItem);
        WeakAndItem fallBackWords = new WeakAndItem();
        words.forEach(word -> {
            fallBackWords.addItem(new WordItem(word));
        });
        elseAndItem.addItem(fallBackWords);
        return elseAndItem;
    }

    /**
     * Normalize and stem input string based on provided language or detect input language
     * and return first stem option
     * @param input The input text to be stemmed
     * @param language Hint for using optimal stemmer
     * @return Stemmed terms in an array
     */
    private String [] getBestStems(Map<Language, List<String>> detections, String input, Language language) {
        var normalizedInput = linguistics.getNormalizer().normalize(input);

        if (language == null) {
            language = linguistics.getDetector().detect(normalizedInput, null).getLanguage();

            var languageDetections = detections.getOrDefault(language, new ArrayList<>());
            languageDetections.add(input);
            detections.put(language, languageDetections);
        }
        return linguistics.getStemmer()
                .stem(normalizedInput, StemMode.DEFAULT, language)
                .stream()
                .map(stem -> stem.get(0))
                .collect(Collectors.toList())
                .toArray(String[]::new);
    }

    private String getFilterLanguage(CompositeItem andItem) {
        return andItem.items()
                .stream()
                .filter(item -> item instanceof RegExpItem && ((RegExpItem) item).getIndexName().equals(Constants.LANGUAGE_FIELD))
                .map(item -> ((RegExpItem) item).getRegexp().toString())
                .findFirst()
                .orElse(null);
    }

    private boolean shouldUseSynonyms(Query query) {
        return Integer.parseInt((String) query.properties().get(Constants.USE_SYNONYMS_PROP)) == 1;
    }
}
