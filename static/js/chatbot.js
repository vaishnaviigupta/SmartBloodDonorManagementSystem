async function sendMessage() {
    const input = document.getElementById("chat-input");
    const message = input.value.trim();

    if (message === "") {
        return;
    }

    // Display user's message
    addMessage(message, "user");
    input.value = "";

    // Display loading message
    const loadingMessage = addMessage("AI is thinking...", "bot");

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: message
            })
        });

        const data = await response.json();

        if (!response.ok) {
            loadingMessage.innerText =
                data.reply || "AI service mein error aaya.";
            return;
        }

        loadingMessage.innerText =
            data.reply || "Sorry, mujhe reply nahi mila.";

    } catch (error) {
        console.error("Chatbot error:", error);

        loadingMessage.innerText =
            "AI se connection nahi ho paaya. Please try again.";
    }
}


// Display messages in chatbot
function addMessage(message, sender) {
    const chatBody = document.getElementById("chat-body");

    const messageDiv = document.createElement("div");
    messageDiv.classList.add("chat-message", sender);
    messageDiv.innerText = message;

    chatBody.appendChild(messageDiv);
    chatBody.scrollTop = chatBody.scrollHeight;

    return messageDiv;
}


// Open or close chatbot
function toggleChatbot() {
    const chatbot = document.getElementById("chatbot");

    chatbot.classList.toggle("chatbot-hidden");
}