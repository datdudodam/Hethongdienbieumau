/**
 * AI Form Suggestions Module
 * Cung cấp chức năng gợi ý thông minh dựa trên lịch sử biểu mẫu
 */
const AISuggestions = {
    /**
     * Lấy gợi ý cho biểu mẫu dựa trên loại biểu mẫu
     * @param {string} formType - Loại biểu mẫu cần gợi ý
     * @param {number} maxHistory - Số lượng biểu mẫu lịch sử tối đa để phân tích
     * @returns {Promise} - Promise chứa dữ liệu gợi ý
     */
    getFormSuggestions: async function(formType, maxHistory = 3) {
        try {
            const response = await fetch('/api/ai/form-suggestions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    form_type: formType,
                    max_history: maxHistory
                })
            });
            
            if (!response.ok) {
                throw new Error(`Lỗi HTTP: ${response.status}`);
            }
            
            const data = await response.json();
            return data;
        } catch (error) {
            console.error('Lỗi khi lấy gợi ý AI:', error);
            return {
                success: false,
                message: `Lỗi khi lấy gợi ý: ${error.message}`
            };
        }
    },
    
    /**
     * Áp dụng gợi ý vào biểu mẫu
     * @param {Object} suggestions - Dữ liệu gợi ý từ AI
     * @param {string} formSelector - CSS selector cho biểu mẫu
     */
    applyFormSuggestions: function(suggestions, formSelector) {
        if (!suggestions || !suggestions.success || !suggestions.suggestions) {
            console.warn('Không có gợi ý hợp lệ để áp dụng');
            return;
        }
        
        const form = document.querySelector(formSelector);
        if (!form) {
            console.error(`Không tìm thấy biểu mẫu với selector: ${formSelector}`);
            return;
        }
        
        // Áp dụng các gợi ý vào các trường trong biểu mẫu
        const suggestedData = suggestions.suggestions;
        
        for (const fieldName in suggestedData) {
            const input = form.querySelector(`[name="${fieldName}"]`);
            if (input) {
                // Xử lý các loại input khác nhau
                if (input.type === 'checkbox' || input.type === 'radio') {
                    input.checked = Boolean(suggestedData[fieldName]);
                } else if (input.tagName === 'SELECT') {
                    input.value = suggestedData[fieldName];
                } else if (input.tagName === 'TEXTAREA') {
                    input.value = suggestedData[fieldName];
                    // Kích hoạt sự kiện để cập nhật các thành phần UI khác nếu cần
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                } else {
                    input.value = suggestedData[fieldName];
                }
            }
        }
    },
    
    /**
     * Thêm nút gợi ý AI vào biểu mẫu
     * @param {string} formSelector - CSS selector cho biểu mẫu
     * @param {string} formType - Loại biểu mẫu
     */
    addSuggestionButton: function(formSelector, formType) {
        const form = document.querySelector(formSelector);
        if (!form) return;
        
        // Tạo container cho nút
        const buttonContainer = document.createElement('div');
        buttonContainer.className = 'ai-suggestion-container mb-3';
        
        // Tạo nút gợi ý
        const suggestionButton = document.createElement('button');
        suggestionButton.type = 'button';
        suggestionButton.className = 'btn btn-primary ai-suggestion-btn';
        suggestionButton.innerHTML = '<i class="fas fa-magic"></i> Gợi ý thông minh';
        
        // Thêm sự kiện click
        suggestionButton.addEventListener('click', async () => {
            // Hiển thị trạng thái đang tải
            suggestionButton.disabled = true;
            suggestionButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Đang phân tích...';
            
            try {
                // Lấy gợi ý từ API
                const suggestions = await this.getFormSuggestions(formType);
                
                // Áp dụng gợi ý vào biểu mẫu
                if (suggestions.success) {
                    this.applyFormSuggestions(suggestions, formSelector);
                    // Hiển thị thông báo thành công
                    this.showNotification('Đã áp dụng gợi ý thông minh!', 'success');
                } else {
                    // Hiển thị thông báo lỗi
                    this.showNotification(suggestions.message || 'Không thể lấy gợi ý', 'error');
                }
            } catch (error) {
                console.error('Lỗi khi xử lý gợi ý:', error);
                this.showNotification('Đã xảy ra lỗi khi xử lý gợi ý', 'error');
            } finally {
                // Khôi phục trạng thái nút
                suggestionButton.disabled = false;
                suggestionButton.innerHTML = '<i class="fas fa-magic"></i> Gợi ý thông minh';
            }
        });
        
        // Thêm nút vào container
        buttonContainer.appendChild(suggestionButton);
        
        // Thêm container vào đầu biểu mẫu
        form.insertBefore(buttonContainer, form.firstChild);
    },
    
    /**
     * Hiển thị thông báo
     * @param {string} message - Nội dung thông báo
     * @param {string} type - Loại thông báo (success, error, warning, info)
     */
    showNotification: function(message, type = 'info') {
        // Kiểm tra xem đã có container thông báo chưa
        let notificationContainer = document.querySelector('.ai-notification-container');
        
        if (!notificationContainer) {
            // Tạo container nếu chưa có
            notificationContainer = document.createElement('div');
            notificationContainer.className = 'ai-notification-container';
            document.body.appendChild(notificationContainer);
            
            // Thêm CSS cho container
            const style = document.createElement('style');
            style.textContent = `
                .ai-notification-container {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    z-index: 9999;
                }
                .ai-notification {
                    padding: 15px;
                    margin-bottom: 10px;
                    border-radius: 4px;
                    color: white;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                    animation: fadeIn 0.3s, fadeOut 0.3s 2.7s;
                    opacity: 0;
                    max-width: 300px;
                }
                .ai-notification.success { background-color: #28a745; }
                .ai-notification.error { background-color: #dc3545; }
                .ai-notification.warning { background-color: #ffc107; color: #212529; }
                .ai-notification.info { background-color: #17a2b8; }
                
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(-20px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                @keyframes fadeOut {
                    from { opacity: 1; transform: translateY(0); }
                    to { opacity: 0; transform: translateY(-20px); }
                }
            `;
            document.head.appendChild(style);
        }
        
        // Tạo thông báo
        const notification = document.createElement('div');
        notification.className = `ai-notification ${type}`;
        notification.textContent = message;
        
        // Thêm thông báo vào container
        notificationContainer.appendChild(notification);
        
        // Hiệu ứng hiển thị
        setTimeout(() => {
            notification.style.opacity = '1';
        }, 10);
        
        // Tự động xóa thông báo sau 3 giây
        setTimeout(() => {
            notification.style.opacity = '0';
            setTimeout(() => {
                notification.remove();
            }, 300);
        }, 3000);
    }
};

// Khởi tạo chức năng gợi ý khi trang đã tải xong
document.addEventListener('DOMContentLoaded', function() {
    // Tìm tất cả các biểu mẫu có thuộc tính data-form-type
    const forms = document.querySelectorAll('form[data-form-type]');
    
    forms.forEach(form => {
        const formType = form.getAttribute('data-form-type');
        if (formType) {
            // Thêm nút gợi ý vào mỗi biểu mẫu
            AISuggestions.addSuggestionButton(`form[data-form-type="${formType}"]`, formType);
        }
    });
});