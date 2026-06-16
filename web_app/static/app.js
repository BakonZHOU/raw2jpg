const API_BASE = 'http://127.0.0.1:5000/api';
const IMAGE_BASE = 'http://127.0.0.1:5000/images';

let appState = {
    imageFiles: [],
    currentIdx: 0,
    states: {},
    jpgDir: '',
    rawDir: '',
    destDir: '',
    rawExt: '.CR3'
};

// DOM 元素
const elements = {
    lblJpgPath: document.getElementById('lbl-jpg-path'),
    lblRawPath: document.getElementById('lbl-raw-path'),
    lblDestPath: document.getElementById('lbl-dest-path'),
    selectRawExt: document.getElementById('select-raw-ext'),
    infoLabel: document.getElementById('info-label'),
    mainImage: document.getElementById('main-image'),
    mainImagePlaceholder: document.getElementById('main-image-placeholder'),
    thumbnailBar: document.getElementById('thumbnail-bar'),
    confirmModal: document.getElementById('confirm-modal'),
    confirmText: document.getElementById('confirm-text'),
    resultModal: document.getElementById('result-modal'),
    resultText: document.getElementById('result-text'),
    btnConfirmCopy: document.getElementById('btn-confirm-copy'),
    btnCancelCopy: document.getElementById('btn-cancel-copy'),
    btnCloseResult: document.getElementById('btn-close-result')
};

// API 请求函数
async function apiRequest(endpoint, method = 'GET', data = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json'
        }
    };
    if (data) {
        options.body = JSON.stringify(data);
    }
    const response = await fetch(`${API_BASE}${endpoint}`, options);
    return await response.json();
}

// UI 更新函数
function updateInfoBar() {
    if (!appState.imageFiles.length) {
        elements.infoLabel.textContent = '请点击上方按钮导入JPG文件夹开始筛选';
        return;
    }
    const currentFile = appState.imageFiles[appState.currentIdx];
    const total = appState.imageFiles.length;
    const passCount = Object.values(appState.states).filter(v => v === 1).length;
    elements.infoLabel.textContent = `${currentFile}  |  当前第 ${appState.currentIdx + 1} 张 / 总共 ${total} 张  |  已入选：${passCount} 张`;
}

function showMainImage() {
    if (!appState.imageFiles.length) {
        elements.mainImage.classList.add('hidden');
        elements.mainImagePlaceholder.classList.remove('hidden');
        return;
    }
    const filename = appState.imageFiles[appState.currentIdx];
    elements.mainImage.src = `${IMAGE_BASE}/${encodeURIComponent(filename)}`;
    elements.mainImage.classList.remove('hidden');
    elements.mainImagePlaceholder.classList.add('hidden');
}

function drawThumbnails() {
    elements.thumbnailBar.innerHTML = '';
    if (!appState.imageFiles.length) return;

    const visibleCount = 15;
    const halfVisible = Math.floor(visibleCount / 2);
    let startIdx = Math.max(0, appState.currentIdx - halfVisible);
    let endIdx = Math.min(appState.imageFiles.length, startIdx + visibleCount);

    if (endIdx - startIdx < visibleCount && startIdx > 0) {
        startIdx = Math.max(0, endIdx - visibleCount);
    }

    for (let i = startIdx; i < endIdx; i++) {
        const filename = appState.imageFiles[i];
        const state = appState.states[filename];
        const isCurrent = i === appState.currentIdx;

        const thumb = document.createElement('div');
        thumb.className = 'thumbnail';
        if (state === 1) thumb.classList.add('pass');
        if (state === -1) thumb.classList.add('reject');
        if (isCurrent) thumb.classList.add('current');

        const statusBar = document.createElement('div');
        statusBar.className = 'status-bar';
        thumb.appendChild(statusBar);

        const img = document.createElement('img');
        img.src = `${IMAGE_BASE}/${encodeURIComponent(filename)}`;
        img.loading = 'lazy';
        thumb.appendChild(img);

        thumb.addEventListener('click', () => goTo(i));
        elements.thumbnailBar.appendChild(thumb);
    }

    // 滚动到当前缩略图
    const currentThumb = elements.thumbnailBar.querySelector('.current');
    if (currentThumb) {
        currentThumb.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
    }
}

function updateView() {
    updateInfoBar();
    showMainImage();
    drawThumbnails();
}

// 操作函数
async function browseFolder() {
    const result = await apiRequest('/browse-folder', 'POST');
    if (result.success) {
        return result.folder_path;
    } else if (result.error) {
        alert('选择文件夹失败: ' + result.error);
    }
    return null;
}

async function selectJpgDir() {
    const directory = await browseFolder();
    if (directory) {
        const result = await apiRequest('/select_jpg_dir', 'POST', { directory });
        if (result.success) {
            elements.lblJpgPath.textContent = result.directory;
            appState.jpgDir = directory;
            await refreshState();
        } else {
            alert('路径无效，请检查后重试');
        }
    }
}

async function selectRawDir() {
    const directory = await browseFolder();
    if (directory) {
        const result = await apiRequest('/set_raw_dir', 'POST', { directory });
        if (result.success) {
            elements.lblRawPath.textContent = result.directory;
            appState.rawDir = directory;
        }
    }
}

async function selectDestDir() {
    const directory = await browseFolder();
    if (directory) {
        const result = await apiRequest('/set_dest_dir', 'POST', { directory });
        if (result.success) {
            elements.lblDestPath.textContent = result.directory;
            appState.destDir = directory;
        }
    }
}

async function refreshState() {
    const result = await apiRequest('/get_images');
    appState.imageFiles = result.files || [];
    appState.currentIdx = result.current_idx || 0;
    appState.states = result.states || {};
    updateView();
}

async function markPass() {
    const result = await apiRequest('/mark_pass', 'POST');
    if (result.success) {
        appState.currentIdx = result.current_idx;
        appState.states = result.states;
        updateView();
        if (result.done) {
            showConfirmModal();
        }
    }
}

async function markReject() {
    const result = await apiRequest('/mark_reject', 'POST');
    if (result.success) {
        appState.currentIdx = result.current_idx;
        appState.states = result.states;
        updateView();
        if (result.done) {
            showConfirmModal();
        }
    }
}

async function undo() {
    const result = await apiRequest('/undo', 'POST');
    if (result.success) {
        appState.currentIdx = result.current_idx;
        appState.states = result.states;
        updateView();
    }
}

async function goPrev() {
    const result = await apiRequest('/go_prev', 'POST');
    if (result.success) {
        appState.currentIdx = result.current_idx;
        updateView();
    }
}

async function goNext() {
    const result = await apiRequest('/go_next', 'POST');
    if (result.success) {
        appState.currentIdx = result.current_idx;
        updateView();
        if (result.done) {
            showConfirmModal();
        }
    }
}

async function goTo(idx) {
    const result = await apiRequest('/go_to', 'POST', { idx });
    if (result.success) {
        appState.currentIdx = result.current_idx;
        updateView();
    }
}

function showConfirmModal() {
    if (!appState.rawDir || !appState.destDir) {
        alert('尚未配置【RAW目录】或【导出目录】！请在界面最上方完成选择。');
        return;
    }
    elements.confirmText.textContent = `全部筛选完毕！即将匹配后辍为 [${appState.rawExt}] 的原图。是否开始批量复制到导出目录？`;
    elements.confirmModal.classList.remove('hidden');
}

async function executeCopy() {
    elements.confirmModal.classList.add('hidden');
    const result = await apiRequest('/copy_raw', 'POST');
    if (result.success) {
        let msg = `🎉 复制完成！成功复制 RAW 文件：${result.success_count} 张`;
        if (result.missing_files && result.missing_files.length > 0) {
            msg += `\n缺失/失败文件数量：${result.missing_files.length} 张`;
            console.log('--- 以下为未找到的RAW文件名单 ---');
            result.missing_files.forEach(m => console.log(m));
        }
        elements.resultText.textContent = msg;
        elements.resultModal.classList.remove('hidden');
    } else {
        alert(result.error || '复制失败');
    }
}

async function shutdownServer() {
    if (confirm('确定要终止服务器吗？')) {
        try {
            await apiRequest('/shutdown', 'POST');
            alert('服务器已终止！请关闭此页面。');
        } catch (e) {
            alert('服务器已终止！');
        }
    }
}

// 事件绑定
document.getElementById('btn-select-jpg').addEventListener('click', selectJpgDir);
document.getElementById('btn-select-raw').addEventListener('click', selectRawDir);
document.getElementById('btn-select-dest').addEventListener('click', selectDestDir);
document.getElementById('btn-shutdown').addEventListener('click', shutdownServer);

elements.selectRawExt.addEventListener('change', (e) => {
    const selectedText = e.target.value;
    appState.rawExt = selectedText.split(' ')[0].trim();
    apiRequest('/set_raw_ext', 'POST', { ext: appState.rawExt });
});

document.getElementById('btn-prev').addEventListener('click', goPrev);
document.getElementById('btn-pass').addEventListener('click', markPass);
document.getElementById('btn-reject').addEventListener('click', markReject);
document.getElementById('btn-undo').addEventListener('click', undo);
document.getElementById('btn-next').addEventListener('click', goNext);

elements.btnConfirmCopy.addEventListener('click', executeCopy);
elements.btnCancelCopy.addEventListener('click', () => {
    elements.confirmModal.classList.add('hidden');
});
elements.btnCloseResult.addEventListener('click', () => {
    elements.resultModal.classList.add('hidden');
});

// 键盘快捷键
document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    switch (e.code) {
        case 'Space':
        case 'Enter':
            e.preventDefault();
            markPass();
            break;
        case 'Delete':
        case 'Backspace':
            e.preventDefault();
            markReject();
            break;
        case 'ArrowLeft':
            e.preventDefault();
            goPrev();
            break;
        case 'ArrowRight':
            e.preventDefault();
            goNext();
            break;
        case 'KeyZ':
            if (e.ctrlKey || e.metaKey) {
                e.preventDefault();
                undo();
            }
            break;
    }
});

// 初始化
refreshState();
