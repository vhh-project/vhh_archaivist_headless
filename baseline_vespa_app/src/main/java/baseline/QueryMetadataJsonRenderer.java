package baseline;

import com.fasterxml.jackson.core.JsonGenerator;
import com.yahoo.search.Result;
import com.yahoo.search.rendering.JsonRenderer;

import java.io.IOException;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;

/**
 * An extension of the default vespa JsonRenderer,
 * that also renders metadata which is extracted (in JSON String format) from the query context
 */
public class QueryMetadataJsonRenderer extends JsonRenderer {

    private JsonGenerator generator;

    @Override
    protected void renderCoverage() throws IOException {
        // render translations right below root level
        renderMetadata();
        super.renderCoverage();
    }

    protected void renderMetadata() throws IOException {
        try {
            getGenerator();
            generator.writeObjectFieldStart(Constants.QUERY_METADATA);
            for (String key: Constants.METADATA_KEYS) {
                renderMetaDataPoint(key);
            }
            generator.writeEndObject();
        } catch (NoSuchFieldException | IllegalAccessException e) {
            e.printStackTrace();
        }
    }

    protected void renderMetaDataPoint(String key) throws IOException {
        String metadataJson = null;
        try {
            getGenerator();
            metadataJson = (String) getResult().getQuery()
                    .getContext(true).getProperty(key);
            if (metadataJson != null) {
                generator.writeFieldName(key);
                generator.writeRawValue(metadataJson);
            }
        } catch (IllegalAccessException | NoSuchMethodException | InvocationTargetException | NoSuchFieldException e) {
            e.printStackTrace();
        }

    }

    /**
     * Reflected access of member in JsonRenderer superclass for compatibility
     * @return
     * @throws NoSuchFieldException
     * @throws IllegalAccessException
     */
    protected JsonGenerator getGenerator() throws NoSuchFieldException, IllegalAccessException {
        if (generator == null) {
            Field generatorField = getClass().getSuperclass().getDeclaredField("generator");
            generatorField.setAccessible(true);
            generator = (JsonGenerator) generatorField.get(this);
        }

        return generator;
    }

    /**
     * Reflected call of method in JsonRenderer superclass for compatibility
     * @return
     * @throws NoSuchMethodException
     * @throws InvocationTargetException
     * @throws IllegalAccessException
     */
    protected Result getResult() throws NoSuchMethodException, InvocationTargetException, IllegalAccessException {
        Method resultMethod = getClass().getSuperclass().getDeclaredMethod("getResult");
        resultMethod.setAccessible(true);
        return (Result) resultMethod.invoke(this);
    }
}
