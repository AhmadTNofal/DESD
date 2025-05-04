// Pass user_id to JavaScript
const userId = "{{ user_id }}";
// Determine WebSocket protocol based on page protocol
const protocol = window.location.protocol === "https:" ? "wss://" : "ws://";
const wsUrl = `${protocol}${window.location.host}/ws/notifications/${userId}/`;
const ws = new WebSocket(wsUrl);

ws.onopen = function(event) {
    console.log("WebSocket connection established for notifications");
};

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    // Generate a unique ID for the new notification (since it's not in the database yet)
    const tempId = 'temp-' + Date.now();
    const notificationList = document.querySelector('.notification-list');
    const newNotification = document.createElement('div');
    newNotification.classList.add('notification', 'unread');
    newNotification.setAttribute('data-notification-id', tempId);
    newNotification.innerHTML = `
        <div class="notification-message">
            ${data.message} (${new Date().toLocaleString()})
        </div>
        <div class="notification-actions">
            <button onclick="markAsRead('${tempId}')">Mark as Read</button>
        </div>
    `;
    notificationList.insertBefore(newNotification, notificationList.children[1]); // Insert after the <h1>
};

ws.onclose = function(event) {
    console.log("WebSocket connection closed:", event);
};

ws.onerror = function(error) {
    console.error("WebSocket error:", error);
};

// Function to mark a notification as read
function markAsRead(notificationId) {
    // If it's a temporary ID (from WebSocket), just update the UI
    if (notificationId.startsWith('temp-')) {
        const notificationDiv = document.querySelector(`.notification[data-notification-id="${notificationId}"]`);
        if (notificationDiv) {
            notificationDiv.classList.remove('unread');
            notificationDiv.classList.add('read');
            notificationDiv.querySelector('.notification-actions').remove();
        }
        return;
    }

    // For database notifications, make an API call
    fetch("{% url 'mark_notification_read' %}", {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': getCsrfToken(),
        },
        body: `notification_id=${notificationId}`
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const notificationDiv = document.querySelector(`.notification[data-notification-id="${notificationId}"]`);
            notificationDiv.classList.remove('unread');
            notificationDiv.classList.add('read');
            notificationDiv.querySelector('.notification-actions').remove();
        } else {
            console.error("Failed to mark notification as read:", data.error);
        }
    })
    .catch(error => console.error("Error:", error));
}

// Helper function to get CSRF token
function getCsrfToken() {
    const tokenElement = document.querySelector('[name=csrfmiddlewaretoken]');
    if (!tokenElement) {
        console.error("CSRF token not found in the page");
        return '';
    }
    return tokenElement.value;
}