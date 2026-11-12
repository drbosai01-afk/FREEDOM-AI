package ai.freedom.app

import ai.freedom.core.AIEngine
import ai.freedom.core.AIResponse
import ai.freedom.core.ChatMessage
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * OpenAI-compatible chat-completions HTTPS adapter.
 * This is an optional remote AI provider, NOT an on-device model.
 * Credentials are held in memory only and never written to app storage or logs.
 * Must be called from a worker thread.
 */
class RemoteAIEngine(
    endpoint: String,
    private val modelId: String,
    private val apiKey: String
) : AIEngine {
    override val name = "Сетевая модель: $modelId"
    override val sendsDataOffDevice = true
    private val url: URL

    init {
        val parsed = URL(endpoint.trim())
        require(parsed.protocol.equals("https", ignoreCase = true)) { "Нужен HTTPS-адрес" }
        require(parsed.host.isNotBlank() && parsed.userInfo == null && parsed.query == null && parsed.ref == null) {
            "Некорректный адрес сервера"
        }
        require(modelId.isNotBlank() && modelId.length <= 128) { "Укажи модель" }
        require(apiKey.isNotBlank()) { "Укажи API-ключ" }
        url = parsed
    }

    override fun generate(history: List<ChatMessage>): AIResponse {
        var connection: HttpURLConnection? = null
        return try {
            val body = JSONObject().apply {
                put("model", modelId)
                put("messages", JSONArray().apply {
                    history.forEach { message ->
                        put(JSONObject().apply {
                            put("role", message.role.name.lowercase())
                            put("content", message.text)
                        })
                    }
                })
                put("max_tokens", 512)
            }.toString()

            connection = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                instanceFollowRedirects = false
                connectTimeout = 15000
                readTimeout = 45000
                doOutput = true
                setRequestProperty("Content-Type", "application/json")
                setRequestProperty("Accept", "application/json")
                setRequestProperty("Authorization", "Bearer $apiKey")
            }
            connection.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            val status = connection.responseCode
            if (status !in 200..299) {
                // Do not display raw server errors, which may contain sensitive content.
                AIResponse.Unavailable("Сервер вернул HTTP $status. Проверь адрес, модель и ключ.")
            } else {
                val response = connection.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
                val text = JSONObject(response)
                    .getJSONArray("choices")
                    .getJSONObject(0)
                    .getJSONObject("message")
                    .optString("content", "")
                    .trim()
                if (text.isEmpty()) AIResponse.Unavailable("Модель не вернула текст")
                else AIResponse.Reply(text)
            }
        } catch (_: Exception) {
            // No keys, prompts, URLs or stack traces in error messages.
            AIResponse.Unavailable("Не удалось связаться с моделью. Проверь интернет и настройки.")
        } finally {
            connection?.disconnect()
        }
    }
}
