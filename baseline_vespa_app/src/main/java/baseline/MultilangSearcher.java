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

    private Map<Language, List<String>> detections = new HashMap<>();

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
        Item queryItem;
        String queryBody = "";
        String indexName = "";

        if (root instanceof AndItem) {
            // assuming two-part query with language filter
            queryItem = ((AndItem) root).getItem(0);
        } else {
            queryItem = root;
        }

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
                Gson gson = new Gson();
                // Launch translation request to the word2word translation container
                MultiTranslation multiTranslation = translator.multiTranslate(words, detectedLanguage.languageCode());
                // Store translation metadata in query context. This property can then be retrieved from custom result renderer.
                query.getContext(true).setProperty(Constants.TRANSLATIONS, gson.toJson(multiTranslation));
                query.trace("Translator result: " + gson.toJson(multiTranslation),true, 2);

                // Normalize and stem all translated terms with the language-specific stemmer
                Map<String, List<StemList>> stems = new HashMap<>();
                for (MultiTranslationPart translationPart: multiTranslation.getTranslations()) {
                    String text = String.join(" ", translationPart.getContent());
                    text = linguistics.getNormalizer().normalize(text);
                    List<StemList> stemListList = linguistics.getStemmer()
                            .stem(text, StemMode.DEFAULT, Language.fromLanguageTag(translationPart.getLanguageCode()));

                    stems.put(translationPart.getLanguageCode(), stemListList);
                }
                query.trace("Stemmed translations: " + gson.toJson(stems), false, 2);

                RankItem rankItem = new RankItem();
                WeakAndItem weakAndItem = new WeakAndItem();

                //Extend query with clauses, which equally rank translated terms to their original counterparts
                for (int i = 0; i < words.size(); i++) {
                    EquivItem equivalentStems = new EquivItem();
                    for (String languageCode: multiTranslation.getLanguages()) {
                        StemList wordStems = stems.get(languageCode).get(i);
                        if (wordStems.size() > 1) {
                            PhraseItem compositeStemsItem = new PhraseItem();
                            for (String stem: wordStems) {
                                compositeStemsItem.addItem(new WordItem(stem));
                            }
                            equivalentStems.addItem(compositeStemsItem);
                        } else {
                            TermItem stemItem = new WordItem(wordStems.get(0));
                            equivalentStems.addItem(stemItem);
                        }
                    }

                    weakAndItem.addItem(equivalentStems);
                }

                // Extend weakAnd clause with phrases found in query text and their respective synonyms
                for (Synonyms synonyms: multiTranslation.getSynonyms()) {
                    var mainTermStems = getBestStems(synonyms.getMainTerm(), Language.ENGLISH);
                    EquivItem equivalentSynonyms;
                    if (mainTermStems.length > 1) {
                        equivalentSynonyms = new EquivItem(new PhraseItem(mainTermStems));
                    } else {
                        equivalentSynonyms = new EquivItem(new WordItem(mainTermStems[0]));
                    }

                    for (String term: synonyms.getTerms()) {
                        var termList = getBestStems(term, null);
                        if (termList.length > 1) {
                            equivalentSynonyms.addItem(new PhraseItem(termList));
                        } else {
                            equivalentSynonyms.addItem(new WordItem(termList[0]));
                        }
                    }
                    weakAndItem.addItem(equivalentSynonyms);
                }

                rankItem.addItem(weakAndItem);
                for (String word: words) {
                    rankItem.addItem(new WordItem(word));
                }

                if (root instanceof AndItem) {
                    // assuming two-part query with language filter
                    ((AndItem) root).setItem(0, rankItem);
                } else {
                    root = rankItem;
                }
                query.getModel().getQueryTree().setRoot(root);
                query.trace(String.format("\n\nSynonym language detections: " + detections), false, 2);
                query.trace("\n\nQuery modification done", false, 2);
            } catch (Word2WordTranslator.TranslateExecption translateExecption) {
                query.trace("Translator failed: " + translateExecption.getMessage(), 2);
            }
        }
        query.trace("MultilangSearcher was called in chain", true, 2);
        return execution.search(query);
    }

    /**
     * Normalize and stem input string based on provided language or detect input language 
     * and return first stem option
     * @param input The input text to be stemmed
     * @param language Hint for using optimal stemmer
     * @return Stemmed terms in an array
     */
    private String [] getBestStems(String input, Language language) {
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
}
