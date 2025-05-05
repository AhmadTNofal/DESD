document.addEventListener("DOMContentLoaded", function () {
    const searchInput = document.querySelector('input[name="q"]');
    const searchTypeSelect = document.getElementById("searchType");
    const searchForm = document.getElementById("searchForm");
    const suggestionsContainer = document.createElement("div");
    suggestionsContainer.className = "suggestions-container";
    searchInput.parentElement.appendChild(suggestionsContainer);
    const input = document.getElementById("liveSearchInput");
    const resultsBox = document.getElementById("liveSearchResults");

    async function fetchResults(query) {
        try {
            const response = await fetch(`/search/suggestions?q=${encodeURIComponent(query)}&type=users`);
            const data = await response.json();

            resultsBox.innerHTML = "";

            if (data.suggestions.length === 0) {
                resultsBox.innerHTML = "<div class='result-item'>No results found.</div>";
                return;
            }

            data.suggestions.forEach(user => {
                const item = document.createElement("div");
                item.classList.add("result-item");

                item.innerHTML = `
                    <img src="${user.profile_picture || '/static/accounts/images/default-profile.png'}" alt="User">
                    <div class="text">
                        <div class="name">${user.name}</div>
                        <div class="interests">${user.interests || "No interests listed"}</div>
                    </div>
                `;

                item.addEventListener("click", () => {
                    window.location.href = `/accounts/profile/${user.id}/`;
                });

                resultsBox.appendChild(item);
            });

        } catch (err) {
            console.error("Live search error:", err);
        }
    }

    let debounceTimer;
    input.addEventListener("input", function () {
        const query = this.value.trim();
        clearTimeout(debounceTimer);
        if (query.length > 0) {
            debounceTimer = setTimeout(() => fetchResults(query), 300);
        } else {
            resultsBox.innerHTML = "";
        }
    });
    // Update form action when search type changes
    function updateFormAction() {
        let searchType = searchTypeSelect.value;
        if (searchType === "users") {
            searchForm.action = searchUrls.users;
        } else if (searchType === "communities") {
            searchForm.action = searchUrls.communities;
        } else if (searchType === "events") {
            searchForm.action = searchUrls.events;
        }
    }

    // Fetch suggestions via AJAX
    function fetchSuggestions(query, searchType) {
        fetch(`${searchUrls.suggestions}?q=${encodeURIComponent(query)}&type=${searchType}`)
            .then(response => response.json())
            .then(data => {
                suggestionsContainer.innerHTML = ""; // Clear previous suggestions
                if (data.suggestions.length > 0) {
                    const ul = document.createElement("ul");
                    data.suggestions.forEach(suggestion => {
                        const li = document.createElement("li");
                        const a = document.createElement("a");
                        a.textContent = suggestion.name;

                        // Set the href based on the search type using the base URLs
                        if (searchType === "users") {
                            a.href = `${searchUrls.profile}${suggestion.id}/`;
                        } else if (searchType === "communities") {
                            a.href = `${searchUrls.community}${suggestion.id}/`;
                        } else if (searchType === "events") {
                            a.href = `${searchUrls.event}${suggestion.id}/`;
                        }

                        li.appendChild(a);
                        ul.appendChild(li);
                    });
                    suggestionsContainer.appendChild(ul);
                    suggestionsContainer.style.display = "block";
                } else {
                    suggestionsContainer.style.display = "none";
                }
            })
            .catch(error => {
                console.error("Error fetching suggestions:", error);
                suggestionsContainer.style.display = "none";
            });
    }

    // Debounce function to limit the rate of API calls
    function debounce(func, delay) {
        let timeoutId;
        return function (...args) {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => func.apply(this, args), delay);
        };
    }

    // Handle input changes for live suggestions
    const debouncedFetchSuggestions = debounce(fetchSuggestions, 300);
    searchInput.addEventListener("input", function () {
        const query = this.value.trim();
        const searchType = searchTypeSelect.value;
        if (query.length > 0) {
            debouncedFetchSuggestions(query, searchType);
        } else {
            suggestionsContainer.style.display = "none";
        }
    });

    // Hide suggestions when clicking outside
    document.addEventListener("click", function (event) {
        if (!suggestionsContainer.contains(event.target) && event.target !== searchInput) {
            suggestionsContainer.style.display = "none";
        }
    });

    // Update form action on page load and when search type changes
    updateFormAction();
    searchTypeSelect.addEventListener("change", updateFormAction);
});