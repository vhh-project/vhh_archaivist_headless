package baseline.model;

import lombok.Getter;

import java.util.List;

@Getter
public class MultiTranslationPart {
    String languageCode;
    List<String> content;
}
