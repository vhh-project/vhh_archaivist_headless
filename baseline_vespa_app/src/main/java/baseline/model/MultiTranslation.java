package baseline.model;

import lombok.Getter;

import java.util.List;

@Getter
public class MultiTranslation {
    private String sourceLanguage;
    private List<String> languages;
    private List<MultiTranslationPart> translations;
    private List<Synonyms> synonyms;

    public int getTranslationTermCount() {
        if (translations.isEmpty()) {
            return -1;
        }

        for (int i = 0; i < translations.size(); i++) {
            MultiTranslationPart translation = translations.get(i);
            if (!translation.languageCode.equals("un")) {
                return translation.getContent().size();
            }
        }

        return translations.get(0).content.size();
    }
}


