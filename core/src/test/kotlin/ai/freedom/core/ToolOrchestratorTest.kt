package ai.freedom.core

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs

class ToolOrchestratorTest {
    private class FakeTool : FreedomTool {
        override val id = "fake"
        var calls = 0
        override fun execute(operation: String, argument: String): ToolResult {
            calls++
            return ToolResult.Success("$operation:$argument")
        }
    }

    @Test fun disabledToolCannotRun() {
        val fake = FakeTool()
        val result = ToolOrchestrator(listOf(fake), emptySet())
            .dispatch(ToolCall("fake", "read"))
        assertIs<ToolResult.Denied>(result)
        assertEquals(0, fake.calls)
    }

    @Test fun importantActionNeedsConfirmation() {
        val fake = FakeTool()
        val orchestrator = ToolOrchestrator(listOf(fake), setOf("fake"))
        assertIs<ToolResult.Denied>(
            orchestrator.dispatch(ToolCall("fake", "delete", highImpact = true))
        )
        assertEquals(0, fake.calls)
        assertIs<ToolResult.Success>(
            orchestrator.dispatch(
                ToolCall("fake", "delete", highImpact = true),
                userConfirmedThisAction = true
            )
        )
        assertEquals(1, fake.calls)
    }

    @Test fun enabledNonCriticalActionRuns() {
        val fake = FakeTool()
        val result = ToolOrchestrator(listOf(fake), setOf("fake"))
            .dispatch(ToolCall("fake", "summarize", "document"))
        assertEquals(ToolResult.Success("summarize:document"), result)
    }
}
