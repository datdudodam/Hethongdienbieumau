/**
 * Responsive JavaScript for updatelan5
 * Xử lý các tính năng responsive như menu toggle trên thiết bị di động
 */

document.addEventListener('DOMContentLoaded', function() {
    // Thêm nút toggle menu cho thiết bị di động
    addMenuToggleButton();
    
    // Xử lý sự kiện click cho nút toggle menu
    setupMenuToggle();
});

/**
 * Thêm nút toggle menu vào DOM nếu chưa tồn tại
 */
function addMenuToggleButton() {
    // Kiểm tra xem nút toggle đã tồn tại chưa
    if (!document.querySelector('.menu-toggle')) {
        const toggleButton = document.createElement('button');
        toggleButton.className = 'menu-toggle';
        toggleButton.setAttribute('aria-label', 'Toggle Menu');
        toggleButton.innerHTML = '<i class="fas fa-bars"></i>';
        document.body.appendChild(toggleButton);
    }
}

/**
 * Thiết lập sự kiện click cho nút toggle menu
 */
function setupMenuToggle() {
    // Lấy các phần tử cần thiết
    const toggleButton = document.querySelector('.menu-toggle');
    const sidebar = document.querySelector('.sidebar');
    
    // Nếu có cả nút toggle và sidebar
    if (toggleButton && sidebar) {
        // Xử lý sự kiện click
        toggleButton.addEventListener('click', function() {
            // Toggle class 'show' cho sidebar
            sidebar.classList.toggle('show');
            
            // Thay đổi icon của nút toggle
            const icon = toggleButton.querySelector('i');
            if (sidebar.classList.contains('show')) {
                icon.className = 'fas fa-times';
            } else {
                icon.className = 'fas fa-bars';
            }
        });
        
        // Đóng sidebar khi click bên ngoài
        document.addEventListener('click', function(event) {
            // Nếu click không phải vào sidebar hoặc nút toggle và sidebar đang hiển thị
            if (!sidebar.contains(event.target) && 
                !toggleButton.contains(event.target) && 
                sidebar.classList.contains('show')) {
                // Đóng sidebar
                sidebar.classList.remove('show');
                // Đổi lại icon
                toggleButton.querySelector('i').className = 'fas fa-bars';
            }
        });
    }
}