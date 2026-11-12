package ai.freedom.core

/**
 * Explicit conversation boundary between FREEDOM's UI and a selected model.
 * Implementations must not silently switch between local and remote inference.
 */
data class ChatMessage(val role: Role, val text: String) {
    enum class Role { SYSTEM, USER, ASSISTANT }
    init { require(text.isNotBlank()) { "Empty chat message" } }
}

sealed class AIResponse {
    data class Reply(val text: String) : AIResponse()
    data class Unavailable(val reason: String) : AIResponse()
}

interface AIEngine {
    val name: String
    val sendsDataOffDevice: Boolean
    fun generate(history: List<ChatMessage>): AIResponse
}

/**
 * Fail closed until a trusted model adapter is explicitly configured.
 * This is deliberately NOT represented as a real AI model.
 */
class UnconfiguredAIEngine : AIEngine {
    override val name = "Не подключено"
    override val sendsDataOffDevice = false
    override fun generate(history: List<ChatMessage>): AIResponse =
        AIResponse.Unavailable("ИИ ещё не подключён. Выбери проверенный локальный или сетевой движок.")
}

class AIEngineRouter(
    private val engines: Map<String, AIEngine>,
    private val enabledEngines: Set<String>,
    private val remoteConsent: Boolean
) {
    fun generate(engineId: String, history: List<ChatMessage>): AIResponse {
        if (engineId !in enabledEngines) {
            return AIResponse.Unavailable("Модель не разрешена пользователем")
        }
        val engine = engines[engineId]
            ?: return AIResponse.Unavailable("Модель не найдена")
        if (engine.sendsDataOffDevice && !remoteConsent) {
            return AIResponse.Unavailable("Для передачи сообщений в интернет требуется согласие")
        }
        if (history.isEmpty() || history.last().role != ChatMessage.Role.USER) {
            return AIResponse.Unavailable("Ожидается сообщение пользователя")
        }
        return engine.generate(history)
    }
}
