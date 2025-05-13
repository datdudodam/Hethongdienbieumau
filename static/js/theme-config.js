/**
 * Theme configuration script
 * Handles theme preferences and UI customization
 */

document.addEventListener('DOMContentLoaded', function() {
    // Theme configuration variables
    const defaultTheme = 'light';
    const storageKey = 'app_theme_preference';
    
    // Function to set theme
    function setTheme(themeName) {
        localStorage.setItem(storageKey, themeName);
        document.documentElement.setAttribute('data-theme', themeName);
    }
    
    // Function to toggle theme
    function toggleTheme() {
        const currentTheme = localStorage.getItem(storageKey) || defaultTheme;
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        setTheme(newTheme);
    }
    
    // Initialize theme from saved preference
    function initTheme() {
        const savedTheme = localStorage.getItem(storageKey);
        if (savedTheme) {
            setTheme(savedTheme);
        } else {
            // Check for system preference
            if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
                setTheme('dark');
            } else {
                setTheme(defaultTheme);
            }
        }
    }
    
    // Initialize theme on page load
    initTheme();
    
    // Add event listener for theme toggle button if it exists
    const themeToggleBtn = document.getElementById('theme-toggle');
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', toggleTheme);
    }
});