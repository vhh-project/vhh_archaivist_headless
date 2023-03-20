package baseline;

import baseline.model.StemFilter;
import com.google.gson.Gson;
import com.yahoo.prelude.query.*;
import com.yahoo.search.Query;
import com.yahoo.search.Result;
import com.yahoo.search.Searcher;
import com.yahoo.search.query.QueryTree;
import com.yahoo.search.searchchain.Execution;
import com.yahoo.yolean.chain.After;

import java.util.Arrays;
import java.util.Collection;
import java.util.List;
import java.util.stream.Collectors;

@After("MultilangSearcher")
public class StemFilterSearcher extends Searcher {
    @Override
    public Result search(Query query, Execution execution) {
            QueryTree tree = query.getModel().getQueryTree();
        Item root = tree.getRoot();
        Gson gson = new Gson();

        var stemFilters =
                gson.fromJson((String) query.properties().get(Constants.STEM_FILTER_PROP), StemFilter[].class);

        if (stemFilters == null || stemFilters.length == 0) {
            // Nothing to filter
            return execution.search(query);
        }

        CompositeItem rootItem = null;
        if (root instanceof AndItem) {
            if (((AndItem) root).getItem(0) instanceof WeakAndItem) {
                rootItem = (CompositeItem) root;
            } else {
                // Not in the supported format
                return execution.search(query);
            }

            var filterLanguage = getFilterLanguage((AndItem) root);
            var stemFilter = getMatchingStemFilter(stemFilters, filterLanguage);
            if (stemFilter != null) {
                filterStems(rootItem, stemFilter);
                query.trace(String.format("Filtering done: %s", Arrays.toString(stemFilters)), true, 2);
                return execution.search(query);
            } else if(filterLanguage != null) {
                // Query has language filtered, but there are no stems for filtered language
                return execution.search(query);
            }
        } else if (root instanceof WeakAndItem) {
            rootItem = (CompositeItem) root;
        } else {
            // Wrong format
            return execution.search(query);
        }

        OrItem orItem = new OrItem();
        AndItem baseItem = new AndItem();
        baseItem.addItem(rootItem);
        baseItem.addItem(buildLanguageExclude(stemFilters));
        orItem.addItem(baseItem);

        for (StemFilter filter: stemFilters) {
            filterStems(rootItem, filter);
        }
        query.trace(String.format("Filtering done: %s", Arrays.toString(stemFilters)), true, 2);
        return execution.search(query);
    }

    private NotItem buildLanguageExclude(StemFilter[] stemFilters) {
        NotItem notItem = new NotItem();
        String regExp = Arrays
                .stream(stemFilters)
                .map(stemFilter -> stemFilter.getLanguage())
                .collect(Collectors.joining("|", "(", ")"));
        RegExpItem regExpItem = new RegExpItem(Constants.LANGUAGE_FIELD, true, regExp);
        notItem.addNegativeItem(regExpItem);
        return notItem;
    }

    private NotItem buildLanguageExclude(StemFilter stemFilter) {
        NotItem notItem = new NotItem();
        RegExpItem regExpItem = new RegExpItem(Constants.LANGUAGE_FIELD, true, stemFilter.getLanguage());
        notItem.addNegativeItem(regExpItem);
        return notItem;
    }

    private OrItem buildSynonymFilters(EquivItem synonymItem, StemFilter stemFilter) {
        int unfilteredItemCount = synonymItem.getItemCount();

        EquivItem filteredSynonyms = (EquivItem) synonymItem.clone();
        filterStems(filteredSynonyms, stemFilter);
        int filteredItemCount = filteredSynonyms.getItemCount();

        if (filteredItemCount == unfilteredItemCount)
            return null;

        //normal version
        NotItem filterLangExclude = buildLanguageExclude(stemFilter);
        AndItem unfilteredSynonymsAnd = new AndItem();
        unfilteredSynonymsAnd.addItem(filterLangExclude);
        unfilteredSynonymsAnd.addItem(synonymItem);

        //filtered version
        AndItem filteredSynonymsAnd = new AndItem();
        RegExpItem regExpItem = new RegExpItem(Constants.LANGUAGE_FIELD, true, stemFilter.getLanguage());
        filteredSynonymsAnd.addItem(filteredSynonyms);
        filteredSynonymsAnd.addItem(regExpItem);

        OrItem synonymOr = new OrItem();
        synonymOr.addItem(unfilteredSynonymsAnd);
        synonymOr.addItem(filteredSynonymsAnd);

        return synonymOr;
    }

    private void filterStems(CompositeItem compositeItem, StemFilter stemFilter) {
        for (int i = 0; i < compositeItem.items().size(); i++) {
            Item item = compositeItem.getItem(i);
            if (item instanceof EquivItem) {
                OrItem newItem = buildSynonymFilters((EquivItem) item, stemFilter);
                if (newItem == null)
                    continue;
                compositeItem.removeItem(i);
                compositeItem.addItem(i, newItem);
            } else if (item instanceof AndItem) {
                if (modifyIfLanguageMatch(stemFilter, item) && isSingleLangRegex((AndItem) item)) {
                    compositeItem.removeItem(i);
                    i--;
                } else {
                    updateIfSynonymExclusion(stemFilter, compositeItem, (AndItem) item);
                }
            } else if (item instanceof  CompositeItem) {
                filterStems((CompositeItem) item, stemFilter);
                if (((CompositeItem) item).getItemCount() == 0) {
                    compositeItem.removeItem(i);
                    i --;
                }
            } else if (isWordItemMatch(item, stemFilter)) {
                compositeItem.removeItem(i);
                i--;
            }
        }
    }

    private boolean isSingleLangRegex(AndItem item) {
        if (item.getItemCount() == 1) {
            Item subItem = item.getItem(0);
            return subItem instanceof RegExpItem && ((RegExpItem) subItem).getIndexName().equals(Constants.LANGUAGE_FIELD);
        }
        return false;
    }

    private void updateIfSynonymExclusion(StemFilter stemFilter, CompositeItem parent, AndItem item) {
        if (updateNotFilterLanguages(item, stemFilter)) {
            EquivItem synonymItem = (EquivItem) item.items()
                    .stream()
                    .filter(child -> child instanceof EquivItem)
                    .findFirst()
                    .orElse(null);
            if (synonymItem == null) {
                // should not happen if we managed to update the NotItem before - do nothing else
                return;
            }
            EquivItem filteredSynonyms = (EquivItem) synonymItem.clone();
            filterStems(filteredSynonyms, stemFilter);
            AndItem filteredSynonymsAnd = new AndItem();
            RegExpItem regExpItem = new RegExpItem(Constants.LANGUAGE_FIELD, true, stemFilter.getLanguage());
            filteredSynonymsAnd.addItem(filteredSynonyms);
            filteredSynonymsAnd.addItem(regExpItem);

            parent.addItem(filteredSynonymsAnd);
        }
    }

    private boolean modifyIfLanguageMatch(StemFilter stemFilter, Item item) {
        String language = getFilterLanguage((AndItem) item);
        if (language != null && language.equals(stemFilter.getLanguage())) {
            filterStems((CompositeItem) item, stemFilter);
            return true;
        }
        return false;
    }

    private boolean isWordItemMatch(Item item, StemFilter stemFilter) {
        if (item instanceof WordItem) {
            return stemFilter.getStems().contains(((WordItem) item).getWord());
        }
        return false;
    }

    private StemFilter getMatchingStemFilter(StemFilter[] stemFilters, String language) {
        if (language == null) return null;
        return Arrays
                .stream(stemFilters)
                .filter(stemFilter -> stemFilter.getLanguage().equals(language))
                .findFirst()
                .orElse(null);
    }

    private String getFilterLanguage(CompositeItem compositeItem) {
        return compositeItem.items()
                .stream()
                .filter(item -> item instanceof RegExpItem && ((RegExpItem) item).getIndexName().equals(Constants.LANGUAGE_FIELD))
                .map(item -> ((RegExpItem) item).getRegexp().toString())
                .findFirst()
                .orElse(null);
    }

    private boolean updateNotFilterLanguages(AndItem andItem, StemFilter stemFilter) {
        final int MAX_LANG_COUNT = 11;

        RegExpItem regExpItem = (RegExpItem) andItem.items()
                .stream()
                .filter(item -> item instanceof NotItem)
                .map(item -> ((NotItem) item).items())
                .flatMap(Collection::stream)
                .filter(item -> item instanceof RegExpItem && ((RegExpItem) item).getIndexName().equals(Constants.LANGUAGE_FIELD))
                .findFirst()
                .orElse(null);

        if (regExpItem == null)
            return false;


        List<String> languages = new java.util.ArrayList<>(List.of(regExpItem.getRegexp().pattern().split("\\(|\\)|\\|")));
        if (languages.size() == MAX_LANG_COUNT)
            return false;

        languages.add(stemFilter.getLanguage());
        String newRegex = languages
                .stream()
                .filter(language -> language != "")
                .collect(Collectors.joining("|", "(", ")"));
        regExpItem.setValue(newRegex);

        return true;
    }
}
