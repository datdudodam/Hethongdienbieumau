function saveAndGenerateDocx(event) {
    event.preventDefault();
    const button = event.target.closest('button');
    const originalContent = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<svg class="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg><span class="ml-2">Đang xử lý...</span>';

    const form = document.querySelector('form');
    const formData = new FormData(form);
    
    // Thêm document_name nếu có
    const docNameInput = form.querySelector('input[name="document_name"]');
    if (docNameInput && docNameInput.value) {
        formData.append('document_name', docNameInput.value);
    }

    fetch('/save-and-generate-docx', {
        method: 'POST',
        body: formData
    })
    .then(async response => {
        const contentType = response.headers.get('content-type');
        
        // Nếu là file docx
        if (contentType.includes('application/vnd.openxmlformats-officedocument.wordprocessingml.document')) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            
            // Lấy tên file từ header
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = 'document.docx';
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="?(.+?)"?(;|$)/i);
                if (filenameMatch && filenameMatch[1]) {
                    filename = filenameMatch[1];
                }
            }
            
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            showToast('Tài liệu đã được lưu và tải xuống thành công!', 'success');
        } 
        // Nếu là JSON (lỗi)
        else if (contentType.includes('application/json')) {
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Có lỗi xảy ra khi xử lý yêu cầu');
            }
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showToast(error.message || 'Có lỗi xảy ra. Vui lòng thử lại.', 'error');
    })
    .finally(() => {
        button.disabled = false;
        button.innerHTML = originalContent;
    });
}