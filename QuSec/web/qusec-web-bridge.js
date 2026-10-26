/**
 * QuSec Web Bridge SDK for Social Media Platforms
 * -----------------------------------------------
 * Connects any web-based social media chat or messaging platform to the local
 * QuSec Quantum Security Node running in the terminal.
 *
 * Usage:
 *   const qusec = new QuSecBridge("http://localhost:8765");
 *   qusec.onMessage((msg) => {
 *     console.log("Received quantum message:", msg.text, "via", msg.mode);
 *     renderChatBubble(msg);
 *   });
 *   qusec.onStatus((status) => updateSecurityBadges(status));
 *   qusec.start();
 *
 *   // To send:
 *   await qusec.sendMessage("Hello via Quantum Teleportation!", "teleportation");
 */

class QuSecBridge {
  constructor(gatewayUrl = "http://localhost:8765") {
    this.gatewayUrl = gatewayUrl.replace(/\/$/, "");
    this.statusListeners = [];
    this.messageListeners = [];
    this.eventListeners = [];
    this.eventSource = null;
    this.pollInterval = null;
    this.isConnected = false;
    this.nodeRole = null;
    this.peerRole = null;
  }

  /** Register listener for node status changes (fibre, ESP32, key pool, QBER) */
  onStatus(callback) {
    this.statusListeners.push(callback);
  }

  /** Register listener for incoming quantum decrypted messages */
  onMessage(callback) {
    this.messageListeners.push(callback);
  }

  /** Register listener for all low-level quantum pipeline events */
  onEvent(callback) {
    this.eventListeners.push(callback);
  }

  /** Start listening to QuSec node via SSE stream and status polling */
  async start() {
    await this.fetchStatus();
    this.startEventStream();
    this.pollInterval = setInterval(() => this.fetchStatus(), 3000);
  }

  /** Stop listeners */
  stop() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
    this.isConnected = false;
  }

  /** Fetch live status from local QuSec node */
  async fetchStatus() {
    try {
      const res = await fetch(`${this.gatewayUrl}/api/status`);
      if (res.ok) {
        const data = await res.json();
        this.isConnected = true;
        this.nodeRole = data.role;
        this.peerRole = data.peer_role;
        this.statusListeners.forEach((cb) => cb(data));
        return data;
      }
    } catch (err) {
      this.isConnected = false;
      this.statusListeners.forEach((cb) =>
        cb({ status: "OFFLINE", error: "Cannot connect to local QuSec node at " + this.gatewayUrl })
      );
    }
    return null;
  }

  /** Subscribe to Server-Sent Events (SSE) stream for real-time messages */
  startEventStream() {
    if (this.eventSource) this.eventSource.close();

    try {
      this.eventSource = new EventSource(`${this.gatewayUrl}/api/events`);

      this.eventSource.onmessage = (e) => {
        try {
          const packet = JSON.parse(e.data);
          this.eventListeners.forEach((cb) => cb(packet));

          if (packet.event === "message_received" && packet.data) {
            this.messageListeners.forEach((cb) => cb(packet.data));
          } else if (packet.event === "session_established") {
            this.fetchStatus();
          }
        } catch (err) {
          // Heartbeat or raw text
        }
      };

      this.eventSource.onerror = () => {
        // Retry connection after brief backoff
        setTimeout(() => {
          if (this.isConnected) this.startEventStream();
        }, 3000);
      };
    } catch (err) {
      console.warn("SSE stream failed, falling back to message polling:", err);
    }
  }

  /**
   * Send a chat message over the quantum link.
   * @param {string} text - Message plaintext to transmit
   * @param {string} mode - 'teleportation' (state teleportation) or 'otp' (One-Time-Pad)
   */
  async sendMessage(text, mode = "teleportation") {
    const payload = {
      to: this.peerRole || "Receiver",
      message: text,
      mode: mode,
    };

    const res = await fetch(`${this.gatewayUrl}/api/send`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `Failed to send message: ${res.statusText}`);
    }

    return await res.json();
  }

  /** Trigger quantum session initialization and key pool generation */
  async initSession() {
    const res = await fetch(`${this.gatewayUrl}/api/session/init`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    return await res.json();
  }

  /** Fetch past message history */
  async getMessages() {
    const res = await fetch(`${this.gatewayUrl}/api/messages`);
    if (res.ok) {
      const data = await res.json();
      return data.messages || [];
    }
    return [];
  }
}

// Export for ES modules and browser window
if (typeof module !== "undefined" && module.exports) {
  module.exports = { QuSecBridge };
}
if (typeof window !== "undefined") {
  window.QuSecBridge = QuSecBridge;
}
