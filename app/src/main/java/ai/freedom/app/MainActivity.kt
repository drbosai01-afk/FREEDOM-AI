package ai.freedom.app

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.speech.RecognizerIntent
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import ai.freedom.core.ActionRequest
import ai.freedom.core.Capability
import ai.freedom.core.PermissionBroker

/**
 * FREEDOM v0.1 offline shell. No remote AI or background recording.
 * The user intentionally launches Android's speech recognition or document picker.
 */
class MainActivity : Activity() {
    private lateinit var transcript: TextView
    private lateinit var input: EditText
    private val speechRequest = 1001
    private val fileRequest = 1002

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(20, 28, 20, 16)
            setBackgroundColor(Color.rgb(247, 249, 252))
        }

        val heading = TextView(this).apply {
            text = "FREEDOM  •  0.1"
            textSize = 25f
            setTextColor(Color.rgb(18, 32, 52))
            gravity = Gravity.CENTER_HORIZONTAL
        }
        root.addView(heading)

        val status = TextView(this).apply {
            text = "Локальный прототип • ИИ пока не подключён"
            gravity = Gravity.CENTER_HORIZONTAL
        }
        root.addView(status)

        val scroll = ScrollView(this)
        transcript = TextView(this).apply {
            text = "FREEDOM: Привет! Я первая версия ассистента. Могу принять текст, голос через системный ввод и выбранный тобой файл. Ничего не отправляю в интернет.\n"
            textSize = 17f
            setTextColor(Color.rgb(20, 31, 44))
            setPadding(4, 20, 4, 20)
        }
        scroll.addView(transcript)
        root.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))

        input = EditText(this).apply {
            hint = "Напиши сообщение"
            setSingleLine(false)
            minLines = 1
            maxLines = 3
        }
        root.addView(input)

        val actions = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        val send = Button(this).apply { text = "Отправить" }
        val voice = Button(this).apply { text = "Голос" }
        val file = Button(this).apply { text = "Файл" }
        actions.addView(send, LinearLayout.LayoutParams(0, -2, 1f))
        actions.addView(voice, LinearLayout.LayoutParams(0, -2, 1f))
        actions.addView(file, LinearLayout.LayoutParams(0, -2, 1f))
        root.addView(actions)
        setContentView(root)

        send.setOnClickListener {
            val message = input.text.toString().trim()
            if (message.isNotEmpty()) {
                append("Ты: $message")
                append("FREEDOM: Сообщение получено локально. Подключение ИИ — следующий этап.")
                input.setText("")
            }
        }
        voice.setOnClickListener { launchSpeech() }
        file.setOnClickListener { chooseFile() }
    }

    private fun append(message: String) {
        transcript.append("\n$message\n")
    }

    private fun launchSpeech() {
        try {
            val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ru-RU")
            }
            startActivityForResult(intent, speechRequest)
        } catch (_: Exception) {
            Toast.makeText(this, "На устройстве нет доступного распознавания речи", Toast.LENGTH_LONG).show()
        }
    }

    private fun chooseFile() {
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "*/*"
        }
        startActivityForResult(intent, fileRequest)
    }

    @Deprecated("Android activity result callback for prototype")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (resultCode != RESULT_OK) return
        when (requestCode) {
            speechRequest -> {
                val spoken = data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                    ?.firstOrNull().orEmpty()
                if (spoken.isNotBlank()) input.setText(spoken)
            }
            fileRequest -> {
                val uri = data?.data ?: return
                // A picker grant is scoped to this user-selected document only.
                // Do not read or upload the document until the user requests a concrete operation.
                val broker = PermissionBroker(setOf(Capability.READ_SELECTED_FILES))
                val request = ActionRequest(Capability.READ_SELECTED_FILES, "Show selected document reference")
                if (broker.isAllowed(request, userConfirmedThisAction = true)) {
                    append("FREEDOM: Выбран документ: ${uri.lastPathSegment ?: "файл"}. Содержимое не считывалось.")
                }
            }
        }
    }
}
