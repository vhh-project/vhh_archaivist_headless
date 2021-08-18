package baseline.model;

import lombok.Getter;

import java.util.List;

@Getter
public class MultiTranslation {
    private List<String> languages;
    private List<MultiTranslationPart> translations;
    private List<Synonyms> synonyms;
}


