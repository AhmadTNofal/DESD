function toggleLike(postId, btn) {
    fetch("{% url 'toggle_like' %}", {
        method: "POST",
        headers: {
            "X-CSRFToken": "{{ csrf_token }}",
            "Content-Type": "application/x-www-form-urlencoded"
        },
        body: `post_id=${postId}`
    })
    .then(response => response.json())
    .then(data => {
        const icon = btn.querySelector("i");
        const count = btn.querySelector(".like-count");
        icon.classList.toggle("fa-solid", data.liked);
        icon.classList.toggle("fa-regular", !data.liked);
        count.textContent = data.like_count;
    });
}