document.addEventListener("DOMContentLoaded", () => {
    console.log("🚀 OLabs Collab Loaded!");

    // Add smooth fade-in animation to elements
    document.body.style.opacity = 1;
    
    // AI Chatbot Functionality
    const chatInput = document.getElementById("user-input");
    const chatBox = document.getElementById("chat-box");

    if (chatInput) {
        chatInput.addEventListener("keypress", (event) => {
            if (event.key === "Enter") {
                sendMessage();
            }
        });
    }

    function sendMessage() {
        let userMessage = chatInput.value.trim();
        if (userMessage === "") return;

        chatBox.innerHTML += `<p><strong>You:</strong> ${userMessage}</p>`;
        chatInput.value = "";

        fetch("/chatbot", {
            method: "POST",
            body: JSON.stringify({ message: userMessage }),
            headers: { "Content-Type": "application/json" }
        })
        .then(response => response.json())
        .then(data => {
            chatBox.innerHTML += `<p><strong>Bot:</strong> ${data.reply}</p>`;
            chatBox.scrollTop = chatBox.scrollHeight; // Auto-scroll to latest message
        });
    }

    // Collaborative Code Editor
    const codeEditor = document.getElementById("code-editor");
    if (codeEditor) {
        codeEditor.addEventListener("input", () => {
            localStorage.setItem("code", codeEditor.value);
        });

        // Load previous code
        const savedCode = localStorage.getItem("code");
        if (savedCode) {
            codeEditor.value = savedCode;
        }
    }

    // Button Effects
    const buttons = document.querySelectorAll("button");
    buttons.forEach(button => {
        button.addEventListener("mouseenter", () => {
            button.style.transform = "scale(1.05)";
        });

        button.addEventListener("mouseleave", () => {
            button.style.transform = "scale(1)";
        });
    });

    // Smooth Page Navigation
    const links = document.querySelectorAll("a");
    links.forEach(link => {
        link.addEventListener("click", (event) => {
            event.preventDefault();
            document.body.style.opacity = 0;
            setTimeout(() => {
                window.location.href = link.href;
            }, 300);
        });
    });
});

