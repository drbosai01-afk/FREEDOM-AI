package ai.freedom.core

/**
 * FREEDOM owns decisions; third-party apps/models are optional, explicitly enabled tools.
 * This interface grants no Android permissions and executes no device actions by itself.
 */
data class ToolCall(
    val toolId: String,
    val operation: String,
    val argument: String = "",
    val highImpact: Boolean = false
)

sealed class ToolResult {
    data class Success(val output: String) : ToolResult()
    data class Denied(val reason: String) : ToolResult()
}

interface FreedomTool {
    val id: String
    fun execute(operation: String, argument: String): ToolResult
}

/**
 * Minimal, fail-closed dispatcher for approved tools.
 * Real Android permissions and identity checks must also be validated by adapters.
 */
class ToolOrchestrator(
    tools: List<FreedomTool>,
    private val enabledToolIds: Set<String>
) {
    private val registered = tools.associateBy { it.id }

    init {
        require(tools.all { it.id.isNotBlank() })
        require(registered.size == tools.size) { "Duplicate tool ID" }
    }

    fun dispatch(call: ToolCall, userConfirmedThisAction: Boolean = false): ToolResult {
        if (call.toolId !in enabledToolIds) {
            return ToolResult.Denied("Tool not enabled by the user")
        }
        val tool = registered[call.toolId]
            ?: return ToolResult.Denied("Unknown tool")
        if (call.highImpact && !userConfirmedThisAction) {
            return ToolResult.Denied("Explicit confirmation required")
        }
        return tool.execute(call.operation, call.argument)
    }
}
