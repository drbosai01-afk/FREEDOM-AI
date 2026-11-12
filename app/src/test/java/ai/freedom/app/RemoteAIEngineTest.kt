package ai.freedom.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

/**
 * Security boundary tests. These never send data or require a live API key.
 */
class RemoteAIEngineTest {
    private val endpoint = "https://api.openai.com/v1/chat/completions"

    @Test fun acceptsHttpsApiEndpoint() {
        val engine = RemoteAIEngine(endpoint, "test-model", "test-only-key")
        assertEquals(true, engine.sendsDataOffDevice)
    }

    @Test fun rejectsPlainHttp() {
        assertThrows(IllegalArgumentException::class.java) {
            RemoteAIEngine("http://api.example.org/chat", "test-model", "test-only-key")
        }
    }

    @Test fun rejectsCredentialsEmbeddedInUrl() {
        assertThrows(IllegalArgumentException::class.java) {
            RemoteAIEngine("https://alice:password@api.example.org/chat", "test-model", "test-only-key")
        }
    }

    @Test fun rejectsUrlQueryParameters() {
        assertThrows(IllegalArgumentException::class.java) {
            RemoteAIEngine("https://api.example.org/chat?secret=key", "test-model", "test-only-key")
        }
    }

    @Test fun rejectsNonstandardPorts() {
        assertThrows(IllegalArgumentException::class.java) {
            RemoteAIEngine("https://api.example.org:8443/chat", "test-model", "test-only-key")
        }
    }

    @Test fun rejectsBlankApiKey() {
        assertThrows(IllegalArgumentException::class.java) {
            RemoteAIEngine(endpoint, "test-model", "  ".trim())
        }
    }

    @Test fun rejectsBlankModel() {
        assertThrows(IllegalArgumentException::class.java) {
            RemoteAIEngine(endpoint, "", "test-only-key")
        }
    }
}
