package baseline.service;

import baseline.model.MultiTranslation;
import baseline.model.Translation;
import baseline.model.TranslationRequest;
import baseline.service.retrofit.ServiceBuilder;
import baseline.service.retrofit.Word2wordService;
import retrofit2.Call;
import retrofit2.Response;

import java.io.IOException;
import java.util.List;

public class Word2WordTranslator {

    Word2wordService word2wordService;

    public Word2WordTranslator() {
        word2wordService = ServiceBuilder.buildService(Word2wordService.class);
    }

    /**
     * Translates the passed tokenized passage from the source language to the target language
     * @param tokens A list of tokenized strings
     * @param sourceLanguageCode ISO 639‑1 two-letter language code (e.g. 'en') for source language
     * @param targetLanguageCode ISO 639‑1 two-letter language code (e.g. 'en') for target language
     * @return A list of dictionary translated tokens
     * @throws TranslateExecption If something went wrong during translation
     */
    public List<String> translate(List<String> tokens, String sourceLanguageCode, String targetLanguageCode)
            throws TranslateExecption{
        Call<Translation> translationCall = word2wordService.translate(
                new TranslationRequest(tokens, sourceLanguageCode, targetLanguageCode));
        try {
            Response<Translation> translationResponse = translationCall.execute();
            if (translationResponse.isSuccessful() && translationResponse.body() != null) {
                return translationResponse.body().getTranslation();
            } else {
                throw new TranslateExecption(translationResponse.message());
            }
        } catch (IOException e) {
            throw new TranslateExecption(e.getMessage());
        }
    }

    /**
     * Translates the passed tokenized passage from the source language to all supported languages
     * @param tokens A list of tokenized strings
     * @param sourceLanguageCode ISO 639‑1 two-letter language code (e.g. 'en') for source language
     * @return An object containing all supported languages and according translations
     * @throws TranslateExecption If something went wrong during translation
     */
    public MultiTranslation multiTranslate(List<String> tokens, String sourceLanguageCode)
            throws TranslateExecption{
        Call<MultiTranslation> translationCall = word2wordService.multiTranslate(
                new TranslationRequest(tokens, sourceLanguageCode, null));
        try {
            Response<MultiTranslation> translationResponse = translationCall.execute();
            if (translationResponse.isSuccessful() && translationResponse.body() != null) {
                return translationResponse.body();
            } else {
                throw new TranslateExecption(translationResponse.message());
            }
        } catch (IOException e) {
            throw new TranslateExecption(e.getMessage());
        }
    }

    /**
     * Gets thrown upon translation failure
     */
    public class TranslateExecption extends Exception {
        public TranslateExecption(String message) {
            super(message);
        }
    }
}
