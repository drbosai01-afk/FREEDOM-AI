package ai.freedom.core

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs

class AIEngineTest {
    private class RecordingEngine(
        override val sendsDataOffDevice: Boolean
    ) : AIEngine {
        override val name = "Test engine"
        var calls = 0
        override fun generate(history: List<ChatMessage>): AIResponse {
            calls++
            return AIResponse.Reply("Hello")
        }
    }

    private val history = listOf(ChatMessage(ChatMessage.Role.USER, "Привет"))

    @Test fun disabledModelDoesNotRun() {
        val engine = RecordingEngine(false)
        val router = AIEngineRouter(mapOf("local" to engine), emptySet(), false)
        assertIs<AIResponse.Unavailable>(router.generate("local", history))
        assertEquals(0, engine.calls)
    }

    @Test fun remoteModelRequiresConsent() {
        val engine = RecordingEngine(true)
        val router = AIEngineRouter(mapOf("remote" to engine), setOf("remote"), false)
        assertIs<AIResponse.Unavailable>(router.generate("remote", history))
        assertEquals(0, engine.calls)
    }

    @Test fun permittedLocalModelMayRespond() {
        val engine = RecordingEngine(false)
        val router = AIEngineRouter(mapOf("local" to engine), setOf("local"), false)
        assertEquals(AIResponse.Reply("Hello"), router.generate("local", history))
        assertEquals(1, engine.calls)
    }

    @Test fun remoteModelWithConsentMayRespond() {
        val engine = RecordingEngine(true)
        val router = AIEngineRouter(mapOf("remote" to engine), setOf("remote"), true)
        assertIs<AIResponse.Reply>(router.generate("remote", history))
        assertEquals(1, engine.calls)
    }

    @Test fun invalidConversationDoesNotReachModel() {
        val engine = RecordingEngine(false)
        val router = AIEngineRouter(mapOf("local" to engine), setOf("local"), false)
        assertIs<AIResponse.Unavailable>(router.generate("local", emptyList()))
        assertEquals(0, engine.calls)
    }

    @Test fun unconfiguredEngineIsNotPresentedAsAI() {
        val engine = UnconfiguredAIEngine()
        assertIs<AIResponse.Unavailable>(engine.generate(history))
        assertEquals(false, engine.sendsDataOffDevice)
    }
}
