// Public Grievance AI Assistant - Chat Interface
document.addEventListener("DOMContentLoaded", function () {
  const chatMessages = document.getElementById("chat-messages");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const micButton = document.getElementById("mic-btn");
  const langMeta = document.documentElement.lang || "en";

  if (!chatForm || !chatInput || !chatMessages) return;

  // 1. Web Speech API feature detection
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognition = null;
  let isListening = false;

  if (SpeechRecognition && micButton) {
    micButton.style.display = "inline-flex";
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;

    // Set recognition language
    if (langMeta === "hi") {
      recognition.lang = "hi-IN";
    } else if (langMeta === "te") {
      recognition.lang = "te-IN";
    } else {
      recognition.lang = "en-IN";
    }

    recognition.onstart = function () {
      isListening = true;
      micButton.classList.add("listening");
      micButton.setAttribute("aria-label", "Listening... Speak now");
      chatInput.placeholder = "Listening... Speak clearly into your microphone";
    };

    recognition.onresult = function (event) {
      const transcript = event.results[0][0].transcript;
      chatInput.value = transcript;
    };

    recognition.onerror = function (event) {
      console.warn("Speech recognition error:", event.error);
      stopListening();
    };

    recognition.onend = function () {
      stopListening();
    };

    micButton.addEventListener("click", function () {
      if (!isListening) {
        try {
          recognition.start();
        } catch (e) {
          console.error(e);
        }
      } else {
        recognition.stop();
        stopListening();
      }
    });

    function stopListening() {
      isListening = false;
      micButton.classList.remove("listening");
      micButton.setAttribute("aria-label", "Start voice input");
      chatInput.placeholder = "Type your civic question...";
    }
  } else if (micButton) {
    // Hide mic button if Web Speech API unsupported
    micButton.style.display = "none";
  }

  // 2. Quick suggestion chips
  document.querySelectorAll(".chat-chip").forEach(chip => {
    chip.addEventListener("click", function () {
      const text = this.textContent.trim();
      chatInput.value = text;
      submitUserQuery(text);
    });
  });

  // 3. Form submission
  chatForm.addEventListener("submit", function (e) {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;
    submitUserQuery(message);
  });

  async function submitUserQuery(query) {
    // Truncate to 500 chars
    const trimmed = query.slice(0, 500);
    chatInput.value = "";
    appendUserBubble(trimmed);

    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Show typing loader
    const loaderId = appendLoaderBubble();
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed, language: langMeta })
      });

      removeLoader(loaderId);

      if (res.status === 429) {
        appendBotBubble({
          answer: "Rate limit reached (max 20 requests per minute). Please wait a moment before sending another query.",
          confidence: "low",
          sources: [],
          suggested_action: null
        });
        return;
      }

      if (!res.ok) {
        throw new Error("Server responded with error status " + res.status);
      }

      const data = await res.json();
      appendBotBubble(data);

    } catch (err) {
      removeLoader(loaderId);
      console.error(err);
      appendBotBubble({
        answer: "An error occurred while connecting to the assistant. Please try again or check the Services Directory.",
        confidence: "low",
        sources: [],
        suggested_action: { label: "Explore Services", url: "/services" }
      });
    }

    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function appendUserBubble(text) {
    const bubble = document.createElement("div");
    bubble.className = "chat-bubble user";
    bubble.textContent = text;
    chatMessages.appendChild(bubble);
  }

  function appendLoaderBubble() {
    const id = "loader-" + Date.now();
    const bubble = document.createElement("div");
    bubble.id = id;
    bubble.className = "chat-bubble bot loader-bubble";
    bubble.innerHTML = "<em>Analyzing civic knowledge base...</em>";
    chatMessages.appendChild(bubble);
    return id;
  }

  function removeLoader(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function formatAnswerText(text) {
    const safe = escapeHtml(text);
    return safe.replace(/\n\n/g, "<br><br>").replace(/\n/g, "<br>");
  }

  function appendBotBubble(data) {
    const bubble = document.createElement("div");
    bubble.className = "chat-bubble bot";
    bubble.setAttribute("aria-live", "polite");

    let confidenceClass = "badge-priority-low";
    if (data.confidence === "high") confidenceClass = "badge-status-resolved";
    else if (data.confidence === "medium") confidenceClass = "badge-priority-medium";

    let html = `<div style="margin-bottom: 8px;">
      <span class="badge ${confidenceClass}">${data.confidence ? data.confidence.toUpperCase() : 'INFO'} CONFIDENCE</span>
    </div>`;

    html += `<div>${formatAnswerText(data.answer)}</div>`;

    if (data.sources && data.sources.length > 0) {
      html += `<div class="chat-sources-card"><strong>Sources:</strong><ul style="margin: 4px 0 0; padding-left: 18px;">`;
      data.sources.forEach(s => {
        html += `<li><a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(s.title || s.source_name)}</a> (Reviewed: ${escapeHtml(s.last_reviewed)})</li>`;
      });
      html += `</ul></div>`;
    }

    if (data.suggested_action) {
      html += `<div style="margin-top: 12px;">
        <a href="${escapeHtml(data.suggested_action.url)}" class="btn btn-sm btn-primary">${escapeHtml(data.suggested_action.label)} &rarr;</a>
      </div>`;
    }

    html += `<div class="chat-disclaimer">Disclaimer: This is general guidance, not an official legal or administrative decision.</div>`;

    bubble.innerHTML = html;
    chatMessages.appendChild(bubble);
  }
});
