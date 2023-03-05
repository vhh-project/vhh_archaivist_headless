package baseline.model;

import lombok.Getter;
import lombok.Setter;

import java.util.List;

@Getter
@Setter
public class StemFilter {
    private String language;
    private List<String> stems;

    public StemFilter(){}

    public StemFilter(String language, String... stems) {
        this.language = language;
        this.stems = List.of(stems);
    }

    @Override
    public String toString() {
        return String.format("language: %s | stems: %s", language, stems);
    }
}
