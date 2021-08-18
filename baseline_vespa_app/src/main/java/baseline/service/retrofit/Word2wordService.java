package baseline.service.retrofit;

import baseline.model.MultiTranslation;
import baseline.model.Translation;
import baseline.model.TranslationRequest;
import retrofit2.Call;
import retrofit2.http.Body;
import retrofit2.http.POST;

public interface Word2wordService {

    @POST("translate")
    Call<Translation> translate(@Body TranslationRequest request);

    @POST("multilang-translate")
    Call<MultiTranslation> multiTranslate(@Body TranslationRequest request);
}
