package baseline.service.retrofit;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonDeserializationContext;
import com.google.gson.JsonDeserializer;
import com.google.gson.JsonElement;
import com.google.gson.JsonParseException;

import java.lang.reflect.Type;
import java.util.Date;

import retrofit2.Retrofit;
import retrofit2.converter.gson.GsonConverterFactory;

public class ServiceBuilder {

    public static <T> T buildService(Class<T> type){

        Gson gson = new GsonBuilder().registerTypeAdapter(Date.class, new JsonDeserializer<Date>() {
            @Override
            public Date deserialize(JsonElement json, Type typeOfT, JsonDeserializationContext context) throws JsonParseException {
                long epoch = json.getAsLong();
                return new Date(epoch);
            }
        }).create();

        Retrofit retrofit = new Retrofit.Builder()
                .baseUrl("http://word2word:5000/")
                .addConverterFactory(GsonConverterFactory.create(gson))
                .build();

        return retrofit.create(type);
    }
}
