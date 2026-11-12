package ai.freedom.app

import ai.freedom.core.AIEngine
import ai.freedom.core.AIResponse
import ai.freedom.core.ChatMessage
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * Optional remote inference. Credential only lives in RAM and is not logged.
 * Network access is triggered solely by a confirmed user message.
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
        require(parsed.port == -1 || parsed.port == 443) { "Только стандартный HTTPS-порт 443" }
        require(modelId.isNotBlank() && modelId.length <= 128) { "Укажи модель" }
        require(apiKey.isNotBlank()) { "Укажи API-ключ" }
        url = parsed
    }

    override fun generate(history: List<ChatMessage>): AIResponse {
        var connection: HttpURLConnection? = null
        return try {
            require(history.size <= 100) { "Слишком длинный диалог" }
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
            if (body.toByteArray(Charsets.UTF_8).size > 65536) {
                return AIResponse.Unavailable("Слишком длинный диалог. Перезапусти приложение для очистки истории.")
            }

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
                AIResponse.Unavailable("Сервер вернул HTTP $status. Проверь адрес, модель и ключ.")
            } else {
                // Never buffer an unbounded upstream response into device memory.
                val response = connection.inputStream.use { stream ->
                    val bytes = stream.readNBytes(262145)
                    if (bytes.size > 262144) {
                        return AIResponse.Unavailable("Слишком большой ответ сервера")
                    }
                    bytes.toString(Charsets.UTF_8)
                }
                val reply = JSONObject(response)
                    .getJSONArray("choices")
                    .getJSONObject(0)
                    .getJSONObject("message")
                    .optString("content", "")
                    .trim()
                if (reply.isEmpty()) AIResponse.Unavailable("Модель не вернула текст")
                else AIResponse.Reply(reply)
            }
        } catch (_: Exception) {
            AIResponse.Unavailable("Не удалось выполнить запрос. Проверь интернет, настройки и длину диалога.")
        } finally {
            connection?.disconnect()
        }
    }
}
