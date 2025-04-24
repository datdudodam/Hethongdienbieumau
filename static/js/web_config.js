document.addEventListener('DOMContentLoaded', function() {
    // Handle layout option selection
    const layoutOptions = document.querySelectorAll('.layout-option');
    const layoutTypeInput = document.getElementById('layout_type');
    
    layoutOptions.forEach(option => {
        option.addEventListener('click', function() {
            // Remove active class from all options
            layoutOptions.forEach(opt => opt.classList.remove('active'));
            
            // Add active class to clicked option
            this.classList.add('active');
            
            // Update hidden input value based on which option was clicked
            if (this.querySelector('.layout-content-wide')) {
                layoutTypeInput.value = 'wide';
            } else if (this.querySelector('.layout-content-centered')) {
                layoutTypeInput.value = 'centered';
            } else if (this.querySelector('.layout-content-split')) {
                layoutTypeInput.value = 'sidebar';
            }
        });
    });
    
    // Sync color input with text input
    const colorPicker = document.querySelector('input[type="color"]');
    const colorText = document.querySelector('input[type="text"][name="primary_color"]');
    
    if (colorPicker && colorText) {
        colorPicker.addEventListener('input', function() {
            colorText.value = this.value;
        });
        
        colorText.addEventListener('input', function() {
            // Ensure value is a valid hex color
            if (/^#[0-9A-F]{6}$/i.test(this.value)) {
                colorPicker.value = this.value;
            }
        });
    }
    
    // Preview changes in real-time
    const previewChanges = function() {
        const primaryColor = document.querySelector('input[name="primary_color"]').value;
        const fontFamily = document.querySelector('select[name="font_family"]').value;
        const displayMode = document.querySelector('input[name="display_mode"]:checked').value;
        
        // Update CSS variables for preview
        document.documentElement.style.setProperty('--primary', primaryColor);
        document.documentElement.style.setProperty('--primary-hover', adjustColor(primaryColor, -20));
        
        // Update font family
        document.body.style.fontFamily = `'${fontFamily}', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`;
        
        // Update display mode
        if (displayMode === 'dark') {
            document.documentElement.style.setProperty('--bg', '#1e293b');
            document.documentElement.style.setProperty('--bg-secondary', '#0f172a');
            document.documentElement.style.setProperty('--text', '#f8fafc');
            document.documentElement.style.setProperty('--text-secondary', '#cbd5e1');
            document.documentElement.style.setProperty('--border', '#334155');
        } else {
            document.documentElement.style.setProperty('--bg', '#ffffff');
            document.documentElement.style.setProperty('--bg-secondary', '#f8fafc');
            document.documentElement.style.setProperty('--text', '#1e293b');
            document.documentElement.style.setProperty('--text-secondary', '#64748b');
            document.documentElement.style.setProperty('--border', '#e2e8f0');
        }
    };
    
    // Helper function to adjust color brightness
    function adjustColor(color, amount) {
        return '#' + color.replace(/^#/, '').replace(/../g, color => {
            return ('0' + Math.min(255, Math.max(0, parseInt(color, 16) + amount)).toString(16)).substr(-2);
        });
    }
    
    // Add event listeners for real-time preview
    const colorInputs = document.querySelectorAll('input[name="primary_color"]');
    const fontSelect = document.querySelector('select[name="font_family"]');
    const displayModeInputs = document.querySelectorAll('input[name="display_mode"]');
    
    colorInputs.forEach(input => input.addEventListener('input', previewChanges));
    if (fontSelect) fontSelect.addEventListener('change', previewChanges);
    displayModeInputs.forEach(input => input.addEventListener('change', previewChanges));
    
    // Initialize preview
    previewChanges();
});