package ai.freedom.core

import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class PermissionBrokerTest {
    @Test fun deniesMissingGrant() {
        val broker = PermissionBroker(emptySet())
        assertFalse(broker.isAllowed(ActionRequest(Capability.MICROPHONE, "Record voice command"), true))
    }

    @Test fun requiresConfirmationForHighImpactAction() {
        val broker = PermissionBroker(setOf(Capability.SEND_MESSAGE))
        val action = ActionRequest(Capability.SEND_MESSAGE, "Send user-approved reply")
        assertFalse(broker.isAllowed(action, false))
        assertTrue(broker.isAllowed(action, true))
    }

    @Test fun deniesBlankExplanation() {
        val broker = PermissionBroker(setOf(Capability.READ_SELECTED_FILES))
        assertFalse(broker.isAllowed(ActionRequest(Capability.READ_SELECTED_FILES, ""), true))
    }
}
