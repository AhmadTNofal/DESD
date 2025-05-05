document.addEventListener('DOMContentLoaded', function() {
    // These variables will be set in notifications.html
    const userId = window.userId;
    const markNotificationReadUrl = window.markNotificationReadUrl;
    const csrfToken = window.csrfToken;

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

    // Make markAsRead available globally
    window.markAsRead = function(notificationId) {
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
        fetch(markNotificationReadUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': csrfToken,
            },
            body: `notification_id=${notificationId}`
        })
        .then(response => {
            if (!response.ok) {
                // Log the response text if it's not OK
                return response.text().then(text => {
                    throw new Error(`HTTP error! Status: ${response.status}, Response: ${text}`);
                });
            }
            return response.json();
        })
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
    };
});