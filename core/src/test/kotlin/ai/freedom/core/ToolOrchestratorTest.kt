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

    private val allowed = listOf(
        ToolPermission("fake", "read", requiresConfirmation = false),
        ToolPermission("fake", "delete", requiresConfirmation = true)
    )

    @Test fun disabledToolCannotRun() {
        val fake = FakeTool()
        val result = ToolOrchestrator(listOf(fake), emptySet(), allowed)
            .dispatch(ToolCall("fake", "read"))
        assertIs<ToolResult.Denied>(result)
        assertEquals(0, fake.calls)
    }

    @Test fun modelCannotMarkDeletionLowRisk() {
        val fake = FakeTool()
        val orchestrator = ToolOrchestrator(listOf(fake), setOf("fake"), allowed)
        assertIs<ToolResult.Denied>(
            orchestrator.dispatch(ToolCall("fake", "delete", highImpact = false))
        )
        assertEquals(0, fake.calls)
        assertIs<ToolResult.Success>(
            orchestrator.dispatch(ToolCall("fake", "delete"), userConfirmedThisAction = true)
        )
        assertEquals(1, fake.calls)
    }

    @Test fun enabledHarmlessActionRuns() {
        val fake = FakeTool()
        val result = ToolOrchestrator(listOf(fake), setOf("fake"), allowed)
            .dispatch(ToolCall("fake", "read", "document"))
        assertEquals(ToolResult.Success("read:document"), result)
    }

    @Test fun unlistedOperationIsDenied() {
        val fake = FakeTool()
        val result = ToolOrchestrator(listOf(fake), setOf("fake"), allowed)
            .dispatch(ToolCall("fake", "send-money"), userConfirmedThisAction = true)
        assertIs<ToolResult.Denied>(result)
        assertEquals(0, fake.calls)
    }

    @Test fun noPolicyMeansNoAccess() {
        val fake = FakeTool()
        val result = ToolOrchestrator(listOf(fake), setOf("fake"))
            .dispatch(ToolCall("fake", "read"))
        assertIs<ToolResult.Denied>(result)
        assertEquals(0, fake.calls)
    }
}
