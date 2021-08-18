package baseline.model;

import java.util.List;

public class TranslationRequest {
    List<String> content;
    String sourceLanguage;
    String targetLanguage;

    public TranslationRequest(List<String> content, String sourceLanguage, String targetLanguage) {
        this.content = content;
        this.sourceLanguage = sourceLanguage;
        this.targetLanguage = targetLanguage;
    }
}
