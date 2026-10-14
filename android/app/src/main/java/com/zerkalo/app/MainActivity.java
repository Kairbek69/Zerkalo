package com.zerkalo.app;

import android.content.Intent;
import android.os.Bundle;
import android.speech.RecognizerIntent;
import android.speech.tts.TextToSpeech;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Locale;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;
import org.json.JSONObject;

public class MainActivity extends AppCompatActivity {

    private TextView tvResponse;
    private EditText etInput;
    private TextToSpeech tts;
    private OkHttpClient client;

    private static final String API_URL = "https://zerkalo-6sla.onrender.com";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(40, 40, 40, 40);

        tvResponse = new TextView(this);
        tvResponse.setText("Зеркало ждёт...");
        tvResponse.setTextSize(18);

        etInput = new EditText(this);
        etInput.setHint("Напиши или скажи...");

        Button btnSend = new Button(this);
        btnSend.setText("Отправить");

        Button btnVoice = new Button(this);
        btnVoice.setText("Голос");

        layout.addView(tvResponse);
        layout.addView(etInput);
        layout.addView(btnSend);
        layout.addView(btnVoice);
        setContentView(layout);

        tts = new TextToSpeech(this, status -> {
            if (status == TextToSpeech.SUCCESS) {
                tts.setLanguage(new Locale("ru", "RU"));
            }
        });

        client = new OkHttpClient();

        btnSend.setOnClickListener(v -> {
            String text = etInput.getText().toString().trim();
            if (!text.isEmpty()) {
                sendToZerkalo(text);
            }
        });

        btnVoice.setOnClickListener(v -> {
            Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ru-RU");
            startActivityForResult(intent, 100);
        });
    }

    private void sendToZerkalo(String text) {
        tvResponse.setText("Зеркало думает...");

        JSONObject json = new JSONObject();
        try {
            json.put("text", text);
        } catch (Exception e) {
            e.printStackTrace();
        }

        RequestBody body = RequestBody.create(
                json.toString(),
                MediaType.parse("application/json; charset=utf-8")
        );

        Request request = new Request.Builder()
                .url(API_URL + "/voice")
                .post(body)
                .build();

        client.newCall(request).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                runOnUiThread(() -> tvResponse.setText("Ошибка сети: " + e.getMessage()));
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                String responseBody = response.body().string();
                runOnUiThread(() -> {
                    try {
                        JSONObject jsonResponse = new JSONObject(responseBody);
                        String answer = jsonResponse.optString("response", "Нет ответа");
                        tvResponse.setText(answer);
                        tts.speak(answer, TextToSpeech.QUEUE_FLUSH, null, null);
                    } catch (Exception e) {
                        tvResponse.setText(responseBody);
                    }
                });
            }
        });
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == 100 && resultCode == RESULT_OK && data != null) {
            ArrayList<String> results = data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);
            if (results != null && !results.isEmpty()) {
                String spoken = results.get(0);
                etInput.setText(spoken);
                sendToZerkalo(spoken);
            }
        }
    }
}
