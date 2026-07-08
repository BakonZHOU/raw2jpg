const API_BASE = 'http://127.0.0.1:5000/api';
const IMAGE_BASE = 'http://127.0.0.1:5000/images';

let appState = {
    imageFiles: [],
    currentIdx: 0,
    states: {},
    jpgDir: '',
    rawDir: '',
    destDir: '',
    rawExt: '.CR2',
    lastRightPressTime: 0,
    DOUBLE_PRESS_THRESHOLD: 200,
    imageCache: new Map()
};

const elements = {
    lblJpgPath: document.getElementById('lbl-jpg-path'),
    lblRawPath: document.getElementById('lbl-raw-path'),
    lblDestPath: document.getElementById('lbl-dest-path'),
    lblRawExt: document.getElementById('lbl-raw-ext'),
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
    btnCloseResult: document.getElementById('btn-close-result'),
    zoomModal: document.getElementById('zoom-modal'),
    zoomImage: document.getElementById('zoom-image'),
    zoomClose: document.getElementById('zoom-close'),
    zoomIn: document.getElementById('zoom-in'),
    zoomOut: document.getElementById('zoom-out'),
    zoomReset: document.getElementById('zoom-reset'),
    zoomLevel: document.getElementById('zoom-level'),
    zoomContent: document.getElementById('zoom-content'),
    resizeHandle: document.getElementById('resize-handle'),
    dragHint: document.getElementById('drag-hint')
};

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

function updateInfoBar() {
    if (!appState.imageFiles.length) {
        elements.infoLabel.textContent = '请先导入JPG文件夹开始筛选';
        return;
    }
    const currentFile = appState.imageFiles[appState.currentIdx];
    const total = appState.imageFiles.length;
    const passCount = Object.values(appState.states).filter(v => v === 1).length;
    elements.infoLabel.textContent = `${currentFile}  |  当前第 ${appState.currentIdx + 1} 张 / 总共 ${total} 张  |  已入选：${passCount} 张`;
}

function preloadImages() {
    const preloadCount = 3;
    const startIdx = Math.max(0, appState.currentIdx - 1);
    const endIdx = Math.min(appState.imageFiles.length, appState.currentIdx + preloadCount);
    
    for (let i = startIdx; i < endIdx; i++) {
        const filename = appState.imageFiles[i];
        if (!appState.imageCache.has(filename)) {
            const img = new Image();
            img.src = `${IMAGE_BASE}/${encodeURIComponent(filename)}?w=1920`;
            appState.imageCache.set(filename, img);
        }
    }
}

function showMainImage() {
    if (!appState.imageFiles.length) {
        elements.mainImage.classList.add('hidden');
        elements.mainImagePlaceholder.classList.remove('hidden');
        return;
    }
    const filename = appState.imageFiles[appState.currentIdx];
    elements.mainImage.src = `${IMAGE_BASE}/${encodeURIComponent(filename)}?w=1920`;
    elements.mainImage.classList.remove('hidden');
    elements.mainImagePlaceholder.classList.add('hidden');
    
    preloadImages();
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
        img.src = `${IMAGE_BASE}/${encodeURIComponent(filename)}?w=200`;
        img.loading = 'lazy';
        thumb.appendChild(img);

        thumb.addEventListener('click', () => goTo(i));
        elements.thumbnailBar.appendChild(thumb);
    }

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

async function browseFolder(initialPath = null) {
    const result = await apiRequest('/browse-folder', 'POST', { initial_path: initialPath });
    if (result.success) {
        return result.folder_path;
    } else if (result.error) {
        alert('选择文件夹失败: ' + result.error);
    }
    return null;
}

async function selectJpgDir(initialPath = null) {
    const directory = await browseFolder(initialPath);
    if (directory) {
        const result = await apiRequest('/select-jpg-dir', 'POST', { directory });
        if (result.success) {
            elements.lblJpgPath.textContent = result.directory;
            appState.jpgDir = directory;
            await refreshState();
        } else {
            alert('路径无效，请检查后重试');
        }
    }
}

async function selectRawDir(initialPath = null) {
    const directory = await browseFolder(initialPath);
    if (directory) {
        const result = await apiRequest('/set-raw-dir', 'POST', { directory });
        if (result.success) {
            elements.lblRawPath.textContent = result.directory;
            appState.rawDir = directory;
            // 更新 RAW 后缀显示
            if (result.raw_ext) {
                appState.rawExt = result.raw_ext;
                elements.lblRawExt.textContent = result.raw_ext;
            }
        }
    }
}

async function selectDestDir(initialPath = null) {
    const directory = await browseFolder(initialPath);
    if (directory) {
        const result = await apiRequest('/set-dest-dir', 'POST', { directory });
        if (result.success) {
            elements.lblDestPath.textContent = result.directory;
            appState.destDir = directory;
        }
    }
}

async function refreshState() {
    const result = await apiRequest('/get-images');
    appState.imageFiles = result.files || [];
    appState.currentIdx = result.current_idx || 0;
    appState.states = result.states || {};
    // 更新 RAW 后缀
    if (result.raw_ext) {
        appState.rawExt = result.raw_ext;
        elements.lblRawExt.textContent = result.raw_ext;
    }
    updateView();
}

async function markPass() {
    const result = await apiRequest('/mark-pass', 'POST');
    if (result.success) {
        appState.currentIdx = result.current_idx;
        appState.states = result.states;
        updateView();
    }
}

async function markReject() {
    const result = await apiRequest('/mark-reject', 'POST');
    if (result.success) {
        appState.currentIdx = result.current_idx;
        appState.states = result.states;
        updateView();
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
    const result = await apiRequest('/go-prev', 'POST');
    if (result.success) {
        appState.currentIdx = result.current_idx;
        updateView();
    }
}

async function goNext() {
    if (!appState.imageFiles.length) return;
    
    const isLast = appState.currentIdx === appState.imageFiles.length - 1;
    
    if (!isLast) {
        const result = await apiRequest('/go-next', 'POST');
        if (result.success) {
            appState.currentIdx = result.current_idx;
            updateView();
        }
    } else {
        const currentTime = Date.now();
        if (currentTime - appState.lastRightPressTime <= appState.DOUBLE_PRESS_THRESHOLD) {
            appState.lastRightPressTime = 0;
            showConfirmModal();
        } else {
            appState.lastRightPressTime = currentTime;
        }
    }
}

async function goTo(idx) {
    const result = await apiRequest('/go-to', 'POST', { idx });
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
    const result = await apiRequest('/copy-raw', 'POST');
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
    try {
        await apiRequest('/shutdown', 'POST');
        alert('服务器已终止！页面将自动关闭。');
        setTimeout(() => {
            window.close();
        }, 1000);
    } catch (e) {
        alert('服务器已终止！页面将自动关闭。');
        setTimeout(() => {
            window.close();
        }, 1000);
    }
}

async function extractFolderPathFromDataTransfer(dataTransfer) {
    try {
        const items = dataTransfer.items;
        
        if (!items || items.length === 0) {
            return null;
        }

        for (let i = 0; i < items.length; i++) {
            const item = items[i];
            
            if (item.kind === 'file') {
                const entry = item.webkitGetAsEntry();
                
                if (entry) {
                    if (entry.isDirectory) {
                        return entry.name;
                    } else {
                        return entry.name;
                    }
                }
            }
        }
        
        return null;
    } catch (e) {
        console.error('提取文件夹路径失败:', e);
        return null;
    }
}

function setupDragAndDrop() {
    const dropZones = document.querySelectorAll('.drop-zone');
    
    dropZones.forEach(zone => {
        zone.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            zone.classList.add('drag-over');
            
            if (zone.id === 'main-drop-zone') {
                elements.dragHint.classList.remove('hidden');
            }
        });
        
        zone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            e.stopPropagation();
            zone.classList.remove('drag-over');
            
            if (zone.id === 'main-drop-zone') {
                elements.dragHint.classList.add('hidden');
            }
        });
        
        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            zone.classList.remove('drag-over');
            
            if (zone.id === 'main-drop-zone') {
                elements.dragHint.classList.add('hidden');
            }
            
            const type = zone.dataset.type;
            
            if (type === 'jpg') {
                selectJpgDir(appState.jpgDir);
            } else if (type === 'raw') {
                selectRawDir(appState.rawDir);
            } else if (type === 'dest') {
                selectDestDir(appState.destDir);
            } else if (type === 'multi') {
                (async () => {
                    await selectJpgDir(appState.jpgDir);
                    await selectRawDir(appState.rawDir);
                    await selectDestDir(appState.destDir);
                })();
            }
        });
    });
}

document.getElementById('btn-select-jpg').addEventListener('click', selectJpgDir);
document.getElementById('btn-select-raw').addEventListener('click', selectRawDir);
document.getElementById('btn-select-dest').addEventListener('click', selectDestDir);
document.getElementById('btn-shutdown').addEventListener('click', shutdownServer);

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

let zoomState = {
    scale: 1,
    translateX: 0,
    translateY: 0,
    isDragging: false,
    startX: 0,
    startY: 0
};

function openZoomModal() {
    if (!appState.imageFiles.length) return;
    const filename = appState.imageFiles[appState.currentIdx];
    elements.zoomImage.src = `${IMAGE_BASE}/${encodeURIComponent(filename)}`;
    zoomState.scale = 1;
    zoomState.translateX = 0;
    zoomState.translateY = 0;
    updateZoomTransform();
    elements.zoomModal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function closeZoomModal() {
    elements.zoomModal.classList.add('hidden');
    document.body.style.overflow = '';
}

function updateZoomTransform() {
    elements.zoomImage.style.transform = `translate(${zoomState.translateX}px, ${zoomState.translateY}px) scale(${zoomState.scale})`;
    elements.zoomLevel.textContent = `${Math.round(zoomState.scale * 100)}%`;
}

function zoomIn() {
    zoomState.scale = Math.min(zoomState.scale * 1.2, 10);
    updateZoomTransform();
}

function zoomOut() {
    zoomState.scale = Math.max(zoomState.scale / 1.2, 0.1);
    updateZoomTransform();
}

function resetZoom() {
    zoomState.scale = 1;
    zoomState.translateX = 0;
    zoomState.translateY = 0;
    updateZoomTransform();
}

elements.mainImage.addEventListener('click', () => {
    openZoomModal();
});

elements.zoomClose.addEventListener('click', closeZoomModal);
elements.zoomIn.addEventListener('click', zoomIn);
elements.zoomOut.addEventListener('click', zoomOut);
elements.zoomReset.addEventListener('click', resetZoom);

document.addEventListener('keydown', (e) => {
    if (e.code === 'Escape' && !elements.zoomModal.classList.contains('hidden')) {
        closeZoomModal();
    }
});

elements.zoomModal.addEventListener('wheel', (e) => {
    e.preventDefault();
    if (e.deltaY < 0) {
        zoomIn();
    } else {
        zoomOut();
    }
}, { passive: false });

elements.zoomImage.addEventListener('mousedown', (e) => {
    zoomState.isDragging = true;
    zoomState.startX = e.clientX - zoomState.translateX;
    zoomState.startY = e.clientY - zoomState.translateY;
});

document.addEventListener('mousemove', (e) => {
    if (!zoomState.isDragging) return;
    zoomState.translateX = e.clientX - zoomState.startX;
    zoomState.translateY = e.clientY - zoomState.startY;
    updateZoomTransform();
});

document.addEventListener('mouseup', () => {
    zoomState.isDragging = false;
});

elements.zoomImage.addEventListener('dblclick', resetZoom);

let isResizing = false;
let startY = 0;
let startHeight = 0;
const MIN_THUMBNAIL_HEIGHT = 80;
const MAX_THUMBNAIL_HEIGHT = 400;

elements.resizeHandle.addEventListener('mousedown', (e) => {
    isResizing = true;
    startY = e.clientY;
    startHeight = elements.thumbnailBar.offsetHeight;
    document.body.style.cursor = 'ns-resize';
    document.body.style.userSelect = 'none';
});

document.addEventListener('mousemove', (e) => {
    if (!isResizing) return;
    const deltaY = startY - e.clientY;
    let newHeight = startHeight + deltaY;
    newHeight = Math.max(MIN_THUMBNAIL_HEIGHT, Math.min(MAX_THUMBNAIL_HEIGHT, newHeight));
    elements.thumbnailBar.style.height = `${newHeight}px`;
});

document.addEventListener('mouseup', () => {
    if (isResizing) {
        isResizing = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
    }
});

setupDragAndDrop();
refreshState();
