/**
 * Field Editor
 * Cho phép người dùng chỉnh sửa tên trường trên giao diện
 */

document.addEventListener('DOMContentLoaded', function() {
    // Thêm nút chỉnh sửa cho mỗi label trường
    addEditButtonsToLabels();
});

// Thêm nút chỉnh sửa cho mỗi label
function addEditButtonsToLabels() {
    document.querySelectorAll('.form-input-group').forEach(group => {
        const label = group.querySelector('label');
        const input = group.querySelector('input[type="text"]');
        
        if (label && input && input.id) {
            // Kiểm tra nếu đã có nút chỉnh sửa thì không thêm nữa
            if (label.querySelector('.edit-field-button')) return;
            
            // Tạo nút chỉnh sửa
            const editButton = document.createElement('button');
            editButton.type = 'button';
            editButton.className = 'edit-field-button ml-2 text-indigo-600 hover:text-indigo-800';
            editButton.innerHTML = '<i class="fas fa-edit"></i>';
            editButton.setAttribute('data-field-code', input.id);
            editButton.setAttribute('aria-label', 'Chỉnh sửa tên trường');
            editButton.onclick = (e) => {
                e.stopPropagation();
                openEditFieldNameModal(input.id, label.textContent.trim());
            };
            
            // Thêm nút vào label
            label.appendChild(editButton);
        }
    });
}

// Mở modal chỉnh sửa tên trường
function openEditFieldNameModal(fieldCode, currentFieldName) {
    // Đóng modal nếu đang mở
    const existingModal = document.getElementById('edit-field-name-modal');
    if (existingModal) {
        existingModal.remove();
    }

    // Tạo modal mới
    const modal = document.createElement('div');
    modal.id = 'edit-field-name-modal';
    modal.className = 'fixed inset-0 bg-gray-600 bg-opacity-50 flex items-center justify-center z-50 animate__animated animate__fadeIn';
    modal.innerHTML = `
        <div class="bg-white rounded-lg shadow-xl p-6 w-96 animate__animated animate__fadeInDown">
            <h3 class="text-lg font-semibold mb-4">Chỉnh sửa tên trường</h3>
            <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 mb-1">Tên trường mới:</label>
                <input type="text" id="new-field-name" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500" value="${currentFieldName}">
            </div>
            <div class="flex justify-end space-x-3">
                <button type="button" id="cancel-edit" class="px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300">Hủy</button>
                <button type="button" id="save-field-name" class="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700">Lưu</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Thêm sự kiện cho nút hủy
    document.getElementById('cancel-edit').addEventListener('click', () => {
        modal.classList.add('animate__fadeOutUp');
        setTimeout(() => {
            modal.remove();
        }, 300);
    });
    
    // Thêm sự kiện cho nút lưu
    document.getElementById('save-field-name').addEventListener('click', () => {
        saveFieldName(fieldCode);
    });
    
    // Focus vào input và chọn toàn bộ text
    const nameInput = document.getElementById('new-field-name');
    nameInput.focus();
    nameInput.select();
    
    // Đóng modal khi click ra ngoài
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.add('animate__fadeOutUp');
            setTimeout(() => {
                modal.remove();
            }, 300);
        }
    });
}

// Lưu tên trường mới
function saveFieldName(fieldCode) {
    const modal = document.getElementById('edit-field-name-modal');
    const newFieldName = document.getElementById('new-field-name').value.trim();
    
    if (!newFieldName) {
        showToast('Tên trường không được để trống', 'error');
        return;
    }
    
    // Hiển thị thông báo đang xử lý
    const loadingToast = showToast('Đang cập nhật tên trường...', 'info', 0);
    
    // Gọi API để cập nhật tên trường
    fetch('/update_field_name', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            field_code: fieldCode,
            new_field_name: newFieldName
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        // Ẩn thông báo đang xử lý
        hideToast(loadingToast);
        
        if (data.success) {
            // Cập nhật label trên giao diện
            const group = document.querySelector(`input[id="${fieldCode}"]`)?.closest('.form-input-group');
            if (group) {
                const label = group.querySelector('label');
                if (label) {
                    // Giữ lại nút chỉnh sửa
                    const editButton = label.querySelector('.edit-field-button');
                    label.innerHTML = newFieldName;
                    if (editButton) {
                        label.appendChild(editButton);
                    }
                }
            }
            
            // Đóng modal
            modal.classList.add('animate__fadeOutUp');
            setTimeout(() => {
                modal.remove();
            }, 300);
            
            // Hiển thị thông báo thành công
            showToast('Đã cập nhật tên trường thành công', 'success');
        } else {
            showToast(data.error || 'Có lỗi xảy ra khi cập nhật tên trường', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        hideToast(loadingToast);
        showToast('Có lỗi xảy ra khi cập nhật tên trường', 'error');
    });
}

// Hiển thị thông báo
function showToast(message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `fixed bottom-4 right-4 px-4 py-2 rounded-lg shadow-lg animate__animated animate__fadeInUp z-50 ${
        type === 'error' ? 'bg-red-500 text-white' : 
        type === 'success' ? 'bg-green-500 text-white' : 
        'bg-blue-500 text-white'
    }`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    if (duration > 0) {
        setTimeout(() => {
            hideToast(toast);
        }, duration);
    }
    
    return toast;
}

// Ẩn thông báo
function hideToast(toast) {
    if (toast && document.body.contains(toast)) {
        toast.classList.remove('animate__fadeInUp');
        toast.classList.add('animate__fadeOutDown');
        setTimeout(() => {
            if (document.body.contains(toast)) {
                document.body.removeChild(toast);
            }
        }, 300);
    }
}