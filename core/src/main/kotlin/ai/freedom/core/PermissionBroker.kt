package ai.freedom.core

/** Safety-critical controls are outside any model-editable memory or prompt. */
enum class Capability {
    READ_SELECTED_FILES,
    READ_CONTACTS,
    READ_CALENDAR,
    MICROPHONE,
    SEND_MESSAGE,
    SHARE_FILE,
    DELETE_FILE
}

data class ActionRequest(
    val capability: Capability,
    val explanation: String,
    val target: String? = null
)

/** A grant only enables consideration; high-impact actions always need per-action approval. */
class PermissionBroker(
    private val grantedCapabilities: Set<Capability>
) {
    private val highImpact = setOf(
        Capability.SEND_MESSAGE,
        Capability.SHARE_FILE,
        Capability.DELETE_FILE
    )

    fun isAllowed(request: ActionRequest, userConfirmedThisAction: Boolean): Boolean {
        if (request.explanation.isBlank()) return false
        if (request.capability !in grantedCapabilities) return false
        if (request.capability in highImpact && !userConfirmedThisAction) return false
        return true
    }
}
