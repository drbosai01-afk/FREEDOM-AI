package ai.freedom.core

/**
 * A model may suggest a call, but cannot declare its own operation safe.
 * All allowed operations and confirmation requirements are registered by the app owner.
 */
data class ToolCall(
    val toolId: String,
    val operation: String,
    val argument: String = "",
    // Kept for source compatibility; never used to waive an operation's policy.
    val highImpact: Boolean = false
)

data class ToolPermission(
    val toolId: String,
    val operation: String,
    val requiresConfirmation: Boolean
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
 * Deny-by-default tool boundary.
 *
 * Operation allowlisting is independent of model-generated ToolCall.highImpact.
 * Confirmation must be supplied by trusted UI code for the exact proposed action.
 * Runtime Android permissions and authentication are checked separately by adapters.
 */
class ToolOrchestrator(
    tools: List<FreedomTool>,
    private val enabledToolIds: Set<String>,
    permissions: List<ToolPermission> = emptyList()
) {
    private val registered = tools.associateBy { it.id }
    private val policies = permissions.associateBy { it.toolId to it.operation }

    init {
        require(tools.all { it.id.isNotBlank() })
        require(registered.size == tools.size) { "Duplicate tool ID" }
        require(permissions.all { it.toolId.isNotBlank() && it.operation.isNotBlank() })
        require(policies.size == permissions.size) { "Duplicate operation policy" }
    }

    fun dispatch(call: ToolCall, userConfirmedThisAction: Boolean = false): ToolResult {
        if (call.toolId !in enabledToolIds) {
            return ToolResult.Denied("Tool not enabled by the user")
        }
        val tool = registered[call.toolId]
            ?: return ToolResult.Denied("Unknown tool")
        val policy = policies[call.toolId to call.operation]
            ?: return ToolResult.Denied("Operation not allowlisted")
        if ((policy.requiresConfirmation || call.highImpact) && !userConfirmedThisAction) {
            return ToolResult.Denied("Explicit confirmation required")
        }
        return tool.execute(call.operation, call.argument)
    }
}
