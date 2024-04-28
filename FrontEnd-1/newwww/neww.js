document.getElementById('loginForm').addEventListener('submit', async function (event) {
    event.preventDefault(); // Prevent form submission

    // Fetch form data
    const formData = new FormData(event.target);

    // Send form data to server using fetch API
    await fetch('login.php', {
        method: 'POST',
        body: formData
    })
        .then(response => {
            if (response.ok) {
                // Redirect to dashboard or another page upon successful login
                window.location.href = 'dashboard.php';
            } else {
                // Handle login error (e.g., display error message)
                alert('Invalid email or password. Please try again.');
            }
        })
        .catch(error => {
            console.error('Error:', error);
        });
});
