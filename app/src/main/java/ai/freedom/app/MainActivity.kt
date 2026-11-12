package ai.freedom.app

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.speech.RecognizerIntent
import android.text.InputType
import android.view.Gravity
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import ai.freedom.core.AIEngine
import ai.freedom.core.AIEngineRouter
import ai.freedom.core.AIResponse
import ai.freedom.core.ActionRequest
import ai.freedom.core.Capability
import ai.freedom.core.ChatMessage
import ai.freedom.core.PermissionBroker

/**
 * FREEDOM 0.2: user-controlled remote AI.
 * Network conversations are OFF until user configures HTTPS, model, API key and consent.
 * Key and chat history remain in memory only; nothing is sent on startup.
 */
class MainActivity : Activity() {
    private lateinit var transcript: TextView
    private lateinit var input: EditText
    private lateinit var sendButton: Button
    private lateinit var statusLabel: TextView
    private var engine: AIEngine? = null
    private var remoteConsent = false
    private var sending = false
    private val history = mutableListOf<ChatMessage>()
    private val speechRequest = 1001
    private val fileRequest = 1002

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(20, 28, 20, 16)
            setBackgroundColor(Color.rgb(247, 249, 252))
        }
        root.addView(TextView(this).apply {
            text = "FREEDOM • 0.2"
            textSize = 25f
            setTextColor(Color.rgb(18, 32, 52))
            gravity = Gravity.CENTER_HORIZONTAL
        })
        statusLabel = TextView(this).apply {
            text = "ИИ отключён • сообщения не отправляются"
            gravity = Gravity.CENTER_HORIZONTAL
        }
        root.addView(statusLabel)
        root.addView(Button(this).apply {
            text = "Подключить ИИ / отключить"
            setOnClickListener { showAISettings() }
        })
        val scroll = ScrollView(this)
        transcript = TextView(this).apply {
            text = "FREEDOM: Привет! Чтобы получить настоящие ответы, подключи ИИ в настройках. Сетевой ИИ использует отдельный API-ключ и может тарифицироваться провайдером.\n"
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
        sendButton = Button(this).apply { text = "Отправить" }
        val voice = Button(this).apply { text = "Голос" }
        val file = Button(this).apply { text = "Файл" }
        actions.addView(sendButton, LinearLayout.LayoutParams(0, -2, 1f))
        actions.addView(voice, LinearLayout.LayoutParams(0, -2, 1f))
        actions.addView(file, LinearLayout.LayoutParams(0, -2, 1f))
        root.addView(actions)
        setContentView(root)

        sendButton.setOnClickListener { sendMessage() }
        voice.setOnClickListener { launchSpeech() }
        file.setOnClickListener { chooseFile() }
    }

    private fun showAISettings() {
        val fields = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(35, 8, 35, 8)
        }
        val endpoint = EditText(this).apply {
            hint = "HTTPS endpoint"
            setText("https://api.openai.com/v1/chat/completions")
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
        }
        val model = EditText(this).apply {
            hint = "Модель"
            setText("gpt-4o-mini")
            inputType = InputType.TYPE_CLASS_TEXT
        }
        val secret = EditText(this).apply {
            hint = "API-ключ (не сохраняется)"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
        }
        val consent = CheckBox(this).apply {
            text = "Согласен отправлять мои сообщения выбранному ИИ-провайдеру. Провайдер может хранить данные и взимать оплату."
            isChecked = false
        }
        fields.addView(endpoint)
        fields.addView(model)
        fields.addView(secret)
        fields.addView(consent)
        AlertDialog.Builder(this)
            .setTitle("Подключение ИИ")
            .setMessage("Нужен отдельный API-ключ провайдера. Подписка ChatGPT Plus не заменяет API-ключ. Убедись, что доверяешь HTTPS-адресу.")
            .setView(fields)
            .setNegativeButton("Отключить") { _, _ ->
                engine = null
                remoteConsent = false
                history.clear()
                statusLabel.text = "ИИ отключён • сообщения не отправляются"
                Toast.makeText(this, "ИИ отключён; история в памяти очищена", Toast.LENGTH_SHORT).show()
            }
            .setNeutralButton("Отмена", null)
            .setPositiveButton("Подключить") { _, _ ->
                if (!consent.isChecked) {
                    Toast.makeText(this, "Для сетевого ИИ нужно согласие", Toast.LENGTH_LONG).show()
                    return@setPositiveButton
                }
                try {
                    val next = RemoteAIEngine(
                        endpoint.text.toString(),
                        model.text.toString().trim(),
                        secret.text.toString()
                    )
                    engine = next
                    remoteConsent = true
                    history.clear()
                    statusLabel.text = "ИИ: ${next.name} • Сеть включена"
                    append("FREEDOM: Модель настроена. Теперь отправь сообщение для проверки.")
                } catch (_: Exception) {
                    Toast.makeText(this, "Проверь HTTPS-адрес, модель и API-ключ", Toast.LENGTH_LONG).show()
                } finally {
                    secret.text?.clear()
                }
            }
            .show()
    }

    private fun sendMessage() {
        val message = input.text.toString().trim()
        if (message.isBlank() || sending) return
        val selectedEngine = engine
        if (selectedEngine == null || !remoteConsent) {
            append("FREEDOM: Сначала нажми «Подключить ИИ». Ничего не отправлено.")
            return
        }
        append("Ты: $message")
        input.setText("")
        history.add(ChatMessage(ChatMessage.Role.USER, message))
        val snapshot = listOf(
            ChatMessage(ChatMessage.Role.SYSTEM,
                "Ты FREEDOM, полезный личный ИИ-ассистент. Отвечай по-русски, кратко, честно. Не заявляй о выполнении действий без инструментов.")
        ) + history.toList()
        sending = true
        sendButton.isEnabled = false
        Thread {
            val result = AIEngineRouter(
                engines = mapOf("chosen" to selectedEngine),
                enabledEngines = setOf("chosen"),
                remoteConsent = true
            ).generate("chosen", snapshot)
            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread
                if (engine !== selectedEngine || !remoteConsent) {
                    sending = false
                    sendButton.isEnabled = true
                    return@runOnUiThread
                }
                when (result) {
                    is AIResponse.Reply -> {
                        append("FREEDOM: ${result.text}")
                        history.add(ChatMessage(ChatMessage.Role.ASSISTANT, result.text))
                    }
                    is AIResponse.Unavailable -> {
                        append("FREEDOM: ${result.reason}")
                        // Failed messages are not retained in conversation history.
                        if (history.isNotEmpty()) history.removeAt(history.lastIndex)
                    }
                }
                sending = false
                sendButton.isEnabled = true
            }
        }.start()
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
            Toast.makeText(this, "Нет доступного системного распознавания речи", Toast.LENGTH_LONG).show()
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
                val broker = PermissionBroker(setOf(Capability.READ_SELECTED_FILES))
                val request = ActionRequest(Capability.READ_SELECTED_FILES, "Show selected document reference")
                if (broker.isAllowed(request, userConfirmedThisAction = true)) {
                    append("FREEDOM: Выбран документ: ${uri.lastPathSegment ?: "файл"}. Содержимое не считывалось.")
                }
            }
        }
    }
}
