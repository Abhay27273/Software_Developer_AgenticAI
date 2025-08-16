let ws = null;

function connectWebSocket() {
    ws = new WebSocket('ws://' + window.location.host + '/ws');
    
    ws.onmessage = function(event) {
        const message = JSON.parse(event.data);
        const outputContainer = document.getElementById('output');
        
        if (message.type === 'update') {
            // Append new content
            outputContainer.innerHTML += message.content;
            // Auto-scroll to bottom
            outputContainer.scrollTop = outputContainer.scrollHeight;
        } else if (message.type === 'clear') {
            // Clear the output container
            outputContainer.innerHTML = '';
        }
    };

    ws.onclose = function(event) {
        console.log('WebSocket connection closed');
        // Attempt to reconnect after a delay
        setTimeout(connectWebSocket, 2000);
    };

    ws.onerror = function(error) {
        console.error('WebSocket error:', error);
    };
}

// Initial connection
connectWebSocket();

// Function to send a command to the server
function sendCommand(command) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ command: command }));
    } else {
        console.error('WebSocket is not connected');
    }
}
